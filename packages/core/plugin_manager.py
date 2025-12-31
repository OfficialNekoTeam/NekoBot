"""插件管理器"""

import os
import re
import sys
import importlib
import shutil
import zipfile
import aiohttp
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional, Type
from loguru import logger
from ..plugins.base import BasePlugin, create_plugin_decorator
from ..plugins.plugin_data_manager import PluginDataManager
from .hot_reload_manager import HotReloadManager


class PluginManager:
    """插件管理器，负责加载、启用、禁用、重载插件以及分发消息和命令"""

    def __init__(self, plugin_dir: str = "data/plugins"):
        self.plugin_dir = Path(plugin_dir)
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self.plugins: Dict[str, BasePlugin] = {}
        self.enabled_plugins: List[str] = []
        self.official_plugins: Dict[str, str] = {}
        self.platform_server = None
        self.plugin_data_manager = PluginDataManager()
        
        # 热重载管理器
        self.hot_reload_manager: Optional[HotReloadManager] = None
        self._hot_reload_enabled = False

    async def load_plugins(self) -> None:
        """加载所有插件（官方 + 用户）"""
        logger.info("开始加载插件...")
        await self._load_official_plugins()
        await self._load_user_plugins()
        logger.info(f"插件加载完成，共 {len(self.plugins)} 个插件已安装")

    async def _load_official_plugins(self) -> None:
        """加载官方插件"""
        for name, module_path in self.official_plugins.items():
            try:
                plugin = await self._load_plugin_from_module(module_path, name)
                if plugin:
                    self.plugins[name] = plugin
                    logger.debug(f"已加载官方插件: {name}")
            except Exception as e:
                logger.error(f"加载官方插件 {name} 失败: {e}")

    async def _load_user_plugins(self) -> None:
        """加载 data/plugins 目录下的用户插件"""
        if not self.plugin_dir.exists():
            return
        for entry in self.plugin_dir.iterdir():
            if entry.is_dir():
                if entry.name.lower() == "src":
                    continue
                if not (entry / "main.py").exists():
                    continue
                name = entry.name
                try:
                    # 将插件目录的父目录加入 sys.path 以便正确导入
                    parent_path = str(self.plugin_dir)
                    if parent_path not in sys.path:
                        sys.path.insert(0, parent_path)
                    module_path = f"{name}.main"
                    plugin = await self._load_plugin_from_module(
                        module_path, name, entry
                    )
                    if plugin:
                        self.plugins[name] = plugin
                        logger.debug(f"已加载用户插件: {name}")
                except Exception as e:
                    logger.error(f"加载用户插件 {name} 失败: {e}")

    async def _load_plugin_from_module(
        self, module_path: str, plugin_name: str, plugin_path: Optional[Path] = None
    ) -> Optional[BasePlugin]:
        """从指定模块导入插件类并实例化

        Args:
            module_path: 模块路径
            plugin_name: 插件名称
            plugin_path: 插件目录路径（用于加载配置 schema）
        
        Returns:
            插件实例
        """
        try:
            module = None
            try:
                spec = importlib.util.find_spec(module_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except AttributeError:
                module = importlib.import_module(module_path)
            if module is None:
                logger.error(f"找不到插件模块 {module_path}")
                return None
            # 在模块中寻找 BasePlugin 子类
            plugin_cls: Optional[Type[BasePlugin]] = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BasePlugin)
                    and attr is not BasePlugin
                ):
                    plugin_cls = attr
                    break
            if not plugin_cls:
                logger.error(f"插件 {plugin_name} 中未找到 BasePlugin 子类")
                return None
            # 实例化插件并处理装饰器
            plugin_instance = plugin_cls()
            create_plugin_decorator(plugin_instance)
            # 加载插件配置 schema
            if plugin_path:
                conf_schema = self.plugin_data_manager.load_conf_schema(plugin_path)
                if conf_schema:
                    # 将配置 schema 附加到插件实例
                    plugin_instance.conf_schema = conf_schema
                    logger.debug(f"已加载插件 {plugin_name} 的配置 schema")
            await plugin_instance.on_load()
            # 设置平台服务器引用
            if self.platform_server:
                plugin_instance.set_platform_server(self.platform_server)
            return plugin_instance
        except Exception as e:
            logger.error(f"从模块 {module_path} 加载插件 {plugin_name} 失败: {e}")
            return None

    async def enable_plugin(self, name: str) -> bool:
        """启用插件，调用其 on_enable 并标记为已启用"""
        if name not in self.plugins:
            logger.error(f"插件 {name} 不存在")
            return False
        if name in self.enabled_plugins:
            logger.warning(f"插件 {name} 已经启用")
            return True
        try:
            plugin = self.plugins[name]
            await plugin.on_enable()
            plugin.enabled = True
            self.enabled_plugins.append(name)
            # 确保插件有平台服务器引用
            if self.platform_server and not plugin.platform_server:
                plugin.set_platform_server(self.platform_server)
            logger.debug(f"已启用插件 {name}")
            return True
        except Exception as e:
            logger.error(f"启用插件 {name} 失败: {e}")
            return False

    async def disable_plugin(self, name: str) -> bool:
        """禁用插件，调用其 on_disable 并移除已启用列表"""
        if name not in self.plugins:
            logger.error(f"插件 {name} 不存在")
            return False
        if name not in self.enabled_plugins:
            logger.warning(f"插件 {name} 已经禁用")
            return True
        try:
            plugin = self.plugins[name]
            await plugin.on_disable()
            plugin.enabled = False
            self.enabled_plugins.remove(name)
            logger.info(f"已禁用插件 {name}")
            return True
        except Exception as e:
            logger.error(f"禁用插件 {name} 失败: {e}")
            return False

    async def reload_plugin(self, name: str) -> bool:
        """重载插件：先禁用再重新加载模块"""
        if name not in self.plugins:
            logger.error(f"插件 {name} 不存在")
            return False
        try:
            await self.disable_plugin(name)
            module_path = self.official_plugins.get(name, f"{name}.main")
            new_plugin = await self._load_plugin_from_module(module_path, name)
            if new_plugin:
                self.plugins[name] = new_plugin
                # 设置平台服务器引用
                if self.platform_server:
                    new_plugin.set_platform_server(self.platform_server)
                # 如果之前是启用状态，重新启用
                if name in self.enabled_plugins:
                    await new_plugin.on_enable()
                logger.debug(f"已重载插件 {name}")
                return True
            else:
                logger.error(f"重载插件 {name} 失败，未能创建新实例")
                return False
        except Exception as e:
            logger.error(f"重载插件 {name} 失败: {e}")
            return False

    def set_platform_server(self, platform_server):
        """设置平台服务器引用，供插件使用"""
        self.platform_server = platform_server
        logger.info("已设置平台服务器引用")

    def get_plugin_info(self, name: str) -> Optional[Dict[str, Any]]:
        """返回插件的基本信息字典"""
        plugin = self.plugins.get(name)
        if not plugin:
            logger.warning(f"Plugin {name} not found in plugins dict")
            return None
        info = {
            "name": plugin.name,
            "version": plugin.version,
            "description": plugin.description,
            "enabled": plugin.enabled,
            "commands": list(plugin.commands.keys()),
            "is_official": name in self.official_plugins,
        }
        logger.debug(f"Plugin info for {name}: {info}")
        return info

    def get_all_plugins_info(self) -> Dict[str, Dict[str, Any]]:
        """返回所有已加载插件的信息"""
        result = {}
        for name in self.plugins:
            info = self.get_plugin_info(name)
            if info:
                result[name] = info
        logger.debug(f"get_all_plugins_info returning {len(result)} plugins: {list(result.keys())}")
        return result

    async def handle_message(self, message: Any) -> None:
        """分发收到的消息给所有已启用插件的 on_message 方法"""
        for name in self.enabled_plugins:
            plugin = self.plugins[name]
            if hasattr(plugin, "on_message"):
                try:
                    await plugin.on_message(message)
                except Exception as e:
                    logger.error(f"插件 {name} 处理消息出错: {e}")

    async def execute_command(
        self, command: str, args: List[str], message: Any
    ) -> bool:
        """在已启用插件中查找并执行对应命令，返回是否成功执行"""
        for name in self.enabled_plugins:
            plugin = self.plugins[name]
            if command in plugin.commands:
                try:
                    await plugin.commands[command](args, message)
                    return True
                except Exception as e:
                    logger.error(f"插件 {name} 执行命令 {command} 出错: {e}")
        return False

    async def reload_plugin(self, name: str) -> bool:
        """重载插件（增强版，支持模块清理）
        
        Args:
            name: 插件名称
            
        Returns:
            重载是否成功
        """
        if name not in self.plugins:
            logger.error(f"插件 {name} 不存在")
            return False
        
        try:
            # 1. 获取插件模块路径
            plugin = self.plugins[name]
            module_path = None
            
            # 从插件实例获取模块信息
            if hasattr(plugin, '__module__'):
                module_path = plugin.__module__
            elif name in self.official_plugins:
                module_path = self.official_plugins[name]
            else:
                module_path = f"{name}.main"
            
            # 2. 清理相关模块缓存
            await self._cleanup_plugin_modules(module_path)
            
            # 3. 禁用插件
            was_enabled = name in self.enabled_plugins
            await self.disable_plugin(name)
            
            # 4. 重新加载模块
            spec = importlib.util.find_spec(module_path)
            if spec and spec.loader:
                # 如果模块已加载，先移除
                if module_path in sys.modules:
                    del sys.modules[module_path]
                    logger.debug(f"已移除模块 {module_path} from sys.modules")
                
                # 重新导入模块
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # 查找插件类
                plugin_cls: Optional[Type[BasePlugin]] = None
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BasePlugin)
                        and attr is not BasePlugin
                    ):
                        plugin_cls = attr
                        break
                
                if not plugin_cls:
                    logger.error(f"插件 {name} 中未找到 BasePlugin 子类")
                    return False
                
                # 5. 创建新插件实例
                new_plugin = plugin_cls()
                create_plugin_decorator(new_plugin)
                
                # 6. 加载插件配置
                plugin_path = self.plugin_dir / name
                if plugin_path.exists():
                    conf_schema = self.plugin_data_manager.load_conf_schema(plugin_path)
                    if conf_schema:
                        new_plugin.conf_schema = conf_schema
                
                # 7. 调用 on_load
                await new_plugin.on_load()
                
                # 8. 设置平台服务器引用
                if self.platform_server:
                    new_plugin.set_platform_server(self.platform_server)
                
                # 9. 替换插件实例
                self.plugins[name] = new_plugin
                
                # 10. 如果之前是启用状态，重新启用
                if was_enabled:
                    await new_plugin.on_enable()
                    new_plugin.enabled = True
                    self.enabled_plugins.append(name)
                
                logger.info(f"插件 {name} 重载成功")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"重载插件 {name} 失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def _cleanup_plugin_modules(self, module_path: str) -> None:
        """清理插件相关的模块
        
        Args:
            module_path: 模块路径
        """
        # 清理以插件路径开头的所有模块
        modules_to_remove = [
            mod_name for mod_name in sys.modules.keys()
            if mod_name.startswith(module_path.split('.')[0])
        ]
        
        for mod_name in modules_to_remove:
            if mod_name in sys.modules:
                del sys.modules[mod_name]
                logger.debug(f"已清理模块: {mod_name}")
    
    def enable_hot_reload(self) -> None:
        """启用插件热重载"""
        if self._hot_reload_enabled:
            logger.warning("热重载已启用")
            return
        
        try:
            from .hot_reload_manager import HotReloadManager
            
            config_dir = Path(__file__).parent.parent.parent / "data" / "config"
            
            self.hot_reload_manager = HotReloadManager(
                plugin_dir=self.plugin_dir,
                config_dir=config_dir,
                plugin_reload_callback=self.reload_plugin,
                config_reload_callback=lambda name: None  # 配置重载暂不处理
            )
            
            self._hot_reload_enabled = True
            logger.info("插件热重载已启用")
            
        except ImportError as e:
            logger.warning(f"无法启用热重载: {e}")
        except Exception as e:
            logger.error(f"启用热重载失败: {e}")
    
    def disable_hot_reload(self) -> None:
        """禁用插件热重载"""
        if not self._hot_reload_enabled:
            return
        
        if self.hot_reload_manager:
            import asyncio
            asyncio.create_task(self.hot_reload_manager.stop())
            self.hot_reload_manager = None
        
        self._hot_reload_enabled = False
        logger.info("插件热重载已禁用")
    
    def is_hot_reload_enabled(self) -> bool:
        """检查热重载是否启用"""
        return self._hot_reload_enabled

    async def unload_all(self) -> None:
        """卸载所有插件，调用 on_unload 并清空内部状态"""
        for name in list(self.enabled_plugins):
            await self.disable_plugin(name)
        for name, plugin in list(self.plugins.items()):
            try:
                await plugin.on_unload()
                # 注销插件的所有命令
                try:
                    from .command_management import unregister_plugin_commands
                    unregister_plugin_commands(name)
                    logger.info(f"已注销插件 {name} 的所有命令")
                except ImportError:
                    logger.warning("命令管理系统未导入，跳过命令注销")
            except Exception as e:
                    logger.error(f"插件 {name} 卸载时出错: {e}")
        self.plugins.clear()
        self.platform_server = None
        logger.info("所有插件已卸载")

    async def delete_plugin_data(self, plugin_name: str) -> bool:
        """删除插件数据"""
        return self.plugin_data_manager.delete_plugin_data(plugin_name)

    def get_plugin_data_dir(self, plugin_name: str) -> Path:
        """获取插件数据目录"""
        return self.plugin_data_manager.get_plugin_data_dir(plugin_name)

    def load_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """加载插件配置"""
        return self.plugin_data_manager.load_plugin_config(plugin_name)

    def save_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """保存插件配置"""
        return self.plugin_data_manager.save_plugin_config(plugin_name, config)

    def get_all_plugin_data_dirs(self) -> list[Path]:
        """获取所有插件数据目录"""
        return self.plugin_data_manager.get_all_plugin_data_dirs()

    def get_plugin_data_size(self, plugin_name: str) -> int:
        """获取插件数据目录大小"""
        return self.plugin_data_manager.get_plugin_data_size(plugin_name)

    def get_personality_prompt(self) -> str:
        """获取当前启用的人格提示词
        
        Returns:
            人格提示词内容，如果未设置则返回空字符串
        """
        try:
            from .prompt_manager import prompt_manager
            
            # 从 prompt_manager 获取所有启用的人格
            enabled_personalities = prompt_manager.get_enabled_personalities()
            if enabled_personalities:
                # 使用第一个启用的人格
                prompt = enabled_personalities[0]["prompt"]
                logger.debug(f"使用人格提示词: {enabled_personalities[0]['name']}")
                return prompt
            
            logger.warning("未找到启用的人格提示词，使用默认提示词")
            return ""
        except Exception as e:
            logger.error(f"获取人格提示词失败: {e}")
            return ""

    async def install_plugin_from_url(
        self, url: str, proxy: Optional[str] = None
    ) -> Dict[str, Any]:
        """从 URL 安装插件"""
        # 这里可以添加从 URL 安装插件的功能
        # 暂时返回未实现
        return {"success": False, "message": "从 URL 安装插件功能暂未实现"}

    async def delete_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """删除插件"""
        if plugin_name not in self.plugins:
            logger.error(f"插件 {plugin_name} 不存在")
            return {"success": False, "message": f"插件 {plugin_name} 不存在"}
        
        plugin = self.plugins[plugin_name]
        await plugin.on_disable()
        if plugin_name in self.enabled_plugins:
            self.enabled_plugins.remove(plugin_name)
        
        # 注销插件的所有命令
        try:
            from .command_management import unregister_plugin_commands
            unregister_plugin_commands(plugin_name)
            logger.info(f"已注销插件 {plugin_name} 的所有命令")
        except ImportError:
            logger.warning("命令管理系统未导入，跳过命令注销")
        except Exception as e:
            logger.error(f"插件 {plugin_name} 卸载时出错: {e}")
        
        # 从插件列表中移除
        del self.plugins[plugin_name]
        
        # 删除插件目录
        plugin_dir = self.plugin_dir / plugin_name
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
            logger.info(f"已删除插件目录: {plugin_dir}")
        
        # 删除插件数据
        self.delete_plugin_data(plugin_name)
        
        return {"success": True, "message": f"插件 {plugin_name} 删除成功"}

    def _parse_github_url(self, url: str) -> Optional[str]:
        """解析 GitHub URL 并返回下载链接"""
        # GitHub 仓库链接: https://github.com/user/repo
        repo_pattern = r"https?://github\.com/([^/]+)/([^/]+)/?$"
        match = re.match(repo_pattern, url)
        if match:
            user, repo = match.groups()
            return f"https://github.com/{user}/{repo}/archive/refs/heads/main.zip"
        # GitHub 分支链接: https://github.com/user/repo/tree/branch
        branch_pattern = r"https?://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/?$"
        match = re.match(branch_pattern, url)
        if match:
            user, repo, branch = match.groups()
            return f"https://github.com/{user}/{repo}/archive/refs/heads/{branch}.zip"
        # GitHub Release 链接: https://github.com/user/repo/releases/tag/v1.0.0
        release_pattern = (
            r"https?://github\.com/([^/]+)/([^/]+)/releases/tag/([^/]+)/?$"
        )
        match = re.match(release_pattern, url)
        if match:
            user, repo, tag = match.groups()
            return f"https://github.com/{user}/{repo}/archive/refs/tags/{tag}.zip"
        # GitHub Archive 链接: https://github.com/user/repo/archive/refs/heads/main.zip
        archive_pattern = r"https?://github\.com/([^/]+)/([^/]+)/archive/.*\.zip$"
        if re.match(archive_pattern, url):
            return url
        return None


# 创建全局插件管理器实例
plugin_manager = PluginManager()
