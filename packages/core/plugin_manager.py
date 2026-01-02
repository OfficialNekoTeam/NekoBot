"""插件管理器"""

import os
import re
import sys
import json
import asyncio
import tempfile
import subprocess
import importlib
import shutil
import zipfile
import aiohttp
import yaml
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional, Type
from loguru import logger
from ..plugins.base import BasePlugin, create_plugin_decorator
from ..plugins.plugin_data_manager import PluginDataManager
from .hot_reload_manager import HotReloadManager


# GitHub 代理列表
GITHUB_PROXIES = [
    "https://ghproxy.com",
    "https://edgeone.gh-proxy.com",
    "https://hk.gh-proxy.com",
    "https://gh.llkk.cc",
]

# Pip 镜像源列表
PIP_MIRRORS = [
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://pypi.mirrors.ustc.edu.cn/simple",
    "https://pypi.mirrors.aliyun.com/simple",
]


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
        self, url: str, proxy: Optional[str] = None, use_github_proxy: Optional[bool] = False,
        pip_mirror: Optional[str] = None
    ) -> Dict[str, Any]:
        """从 URL 安装插件（参考 AstrBot 实现）

        支持的 URL 格式:
            1. GitHub 仓库: https://github.com/user/repo
            2. GitHub 分支: https://github.com/user/repo/tree/branch
            3. GitHub Release: https://github.com/user/repo/releases/tag/v1.0.0
            4. GitHub Archive: https://github.com/user/repo/archive/refs/heads/main.zip
            5. Gitee 仓库: https://gitee.com/user/repo
            6. 直接 ZIP 链接: https://example.com/plugin.zip
            7. CDN 链接: https://cdn.example.com/files/plugin.zip

        Args:
            url: 插件 URL（支持 GitHub 仓库、直链 ZIP）
            proxy: 代理设置（可选）
            use_github_proxy: 是否使用 GitHub 代理（仅当 GitHub URL 时生效）
            pip_mirror: pip 镜像源（可选）

        Returns:
            安装结果
        """
        try:
            download_url = url
            is_github = False
            url_type = "未知"

            # 检查 URL 类型
            if "github.com" in url.lower():
                is_github = True
                # 检查是否已经是 ZIP 链接
                if url.endswith(".zip"):
                    url_type = "GitHub ZIP 直链"
                    download_url = url
                else:
                    # 尝试解析 GitHub 仓库链接
                    try:
                        author, repo, branch = self.parse_github_url(url)
                        url_type = f"GitHub 仓库: {author}/{repo}"
                        logger.info(f"检测到 GitHub 仓库: {author}/{repo}, 分支: {branch or '默认'}")

                        # 尝试获取 GitHub Releases
                        if not branch:
                            try:
                                releases_api = f"https://api.github.com/repos/{author}/{repo}/releases"
                                releases = await self._fetch_github_releases(releases_api)
                                if releases:
                                    download_url = releases[0]["zipball_url"]
                                    logger.info(f"使用 GitHub Release: {releases[0]['tag_name']}")
                                else:
                                    # 没有 Releases，使用默认分支
                                    download_url = f"https://github.com/{author}/{repo}/archive/refs/heads/main.zip"
                                    logger.info("未找到 Release，使用默认分支")
                            except Exception as e:
                                logger.warning(f"获取 GitHub Releases 失败: {e}，使用默认分支")
                                download_url = f"https://github.com/{author}/{repo}/archive/refs/heads/main.zip"
                        else:
                            # 指定了分支
                            download_url = f"https://github.com/{author}/{repo}/archive/refs/heads/{branch}.zip"
                    except ValueError:
                        # 无法解析，直接使用原 URL
                        url_type = "GitHub URL（直链）"
                        download_url = url

            elif "gitee.com" in url.lower():
                url_type = "Gitee 仓库"
                # Gitee 不自动处理，直接使用原 URL
                download_url = url

            elif url.endswith(".zip"):
                url_type = "ZIP 直链"
                download_url = url

            else:
                url_type = "其他 URL"
                download_url = url

            logger.info(f"URL 类型: {url_type}, 下载地址: {download_url}")

            # 下载插件
            temp_dir = Path(tempfile.gettempdir()) / "nekobot_plugins"
            temp_dir.mkdir(parents=True, exist_ok=True)
            zip_path = temp_dir / f"plugin_{asyncio.get_event_loop().time():.0f}.zip"

            success = False

            # 1. 优先使用用户指定的代理
            if proxy:
                logger.info(f"使用用户指定的代理: {proxy}")
                proxy = proxy.rstrip("/")
                if is_github:
                    # GitHub URL 使用代理前缀
                    proxied_url = f"{proxy}/{download_url}"
                    success = await self._download_file(proxied_url, zip_path, timeout=60)
                else:
                    # 非 GitHub URL，使用标准代理
                    success = await self._download_file(download_url, zip_path, proxy=proxy, timeout=60)

            # 2. 如果用户启用了 GitHub 代理且未指定代理（仅对 GitHub URL 有效）
            elif is_github and use_github_proxy:
                logger.info("使用 GitHub 代理下载")
                # 尝试使用 GitHub 代理列表
                for gh_proxy in GITHUB_PROXIES:
                    try:
                        proxied_url = f"{gh_proxy.rstrip('/')}/{download_url}"
                        success = await self._download_file(proxied_url, zip_path, timeout=30)
                        if success:
                            logger.info(f"使用代理 {gh_proxy} 下载成功")
                            break
                    except Exception as e:
                        logger.warning(f"代理 {gh_proxy} 下载失败: {e}")
                        continue

            # 3. 直连下载
            if not success:
                logger.info("尝试直连下载")
                success = await self._download_file(download_url, zip_path, timeout=60)

            if not success or not zip_path.exists():
                return {"success": False, "message": "下载插件失败"}

            # 解压并安装插件
            result = await self.upload_plugin(str(zip_path), pip_mirror=pip_mirror)

            # 删除临时文件
            try:
                zip_path.unlink()
            except Exception:
                pass

            return result

        except Exception as e:
            logger.error(f"从 URL 安装插件失败: {e}")
            return {"success": False, "message": f"安装失败: {str(e)}"}

    async def upload_plugin(self, zip_path: str, delete_data: bool = False, pip_mirror: Optional[str] = None) -> Dict[str, Any]:
        """上传并安装本地 ZIP 插件

        Args:
            zip_path: ZIP 文件路径
            delete_data: 是否删除已有数据
            pip_mirror: pip 镜像源（可选）

        Returns:
            安装结果
        """
        try:
            temp_dir = Path(tempfile.gettempdir()) / "nekobot_temp"
            temp_dir.mkdir(parents=True, exist_ok=True)

            # 解压 ZIP 文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # 查找插件目录
            plugin_dir = None
            plugin_name = None

            # 检查解压后的目录结构
            for item in temp_dir.iterdir():
                if item.is_dir():
                    # 检查是否是插件目录（包含 main.py）
                    if (item / "main.py").exists():
                        plugin_dir = item
                        plugin_name = item.name
                        break
                    # 检查是否有子目录是插件目录
                    for sub_item in item.iterdir():
                        if sub_item.is_dir() and (sub_item / "main.py").exists():
                            plugin_dir = sub_item
                            plugin_name = sub_item.name
                            break
                    if plugin_dir:
                        break

            if not plugin_dir or not plugin_name:
                # 清理临时目录
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {"success": False, "message": "未找到有效的插件目录（缺少 main.py）"}

            # 读取插件元数据
            metadata = self._load_plugin_metadata(plugin_dir)

            # 检查插件是否已存在
            target_dir = self.plugin_dir / plugin_name
            if target_dir.exists():
                # 备份现有插件
                backup_dir = self.plugin_dir / f"{plugin_name}_backup"
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                shutil.move(str(target_dir), str(backup_dir))

            try:
                # 移动插件到目标目录
                shutil.move(str(plugin_dir), str(target_dir))

                # 如果有 _conf_schema.json，创建数据库表
                conf_schema_path = target_dir / "_conf_schema.json"
                if conf_schema_path.exists():
                    with open(conf_schema_path, 'r', encoding='utf-8') as f:
                        conf_schema = json.load(f)
                    # 这里可以添加创建数据库表的逻辑
                    logger.info(f"插件 {plugin_name} 包含配置 schema")

                # 安装插件依赖
                requirements_path = target_dir / "requirements.txt"
                if requirements_path.exists():
                    await self._install_plugin_dependencies(requirements_path, pip_mirror=pip_mirror)

                # 清理临时目录
                shutil.rmtree(temp_dir, ignore_errors=True)

                # 删除备份
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)

                # 如果需要删除数据
                if delete_data:
                    self.delete_plugin_data(plugin_name)

                # 重新加载插件
                if plugin_name in self.plugins:
                    await self.reload_plugin(plugin_name)
                else:
                    # 加载新插件
                    await self._load_user_plugins()

                logger.info(f"插件 {plugin_name} 安装成功")
                return {
                    "success": True,
                    "message": f"插件 {plugin_name} 安装成功",
                    "plugin_name": plugin_name,
                    "metadata": metadata,
                }

            except Exception as e:
                # 恢复备份
                if backup_dir.exists():
                    shutil.move(str(backup_dir), str(target_dir))
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise e

        except Exception as e:
            logger.error(f"上传插件失败: {e}")
            return {"success": False, "message": f"上传插件失败: {str(e)}"}

    async def install_plugin_from_git(
        self, git_url: str, branch: str = "main", pip_mirror: Optional[str] = None
    ) -> Dict[str, Any]:
        """从 Git 仓库克隆并安装插件

        Args:
            git_url: Git 仓库 URL
            branch: 分支名称（默认 main）
            pip_mirror: pip 镜像源（可选）

        Returns:
            安装结果
        """
        try:
            import tempfile

            temp_dir = Path(tempfile.gettempdir()) / "nekobot_git_clone"
            temp_dir.mkdir(parents=True, exist_ok=True)

            clone_dir = temp_dir / f"repo_{asyncio.get_event_loop().time():.0f}"

            # 克隆仓库
            cmd = ["git", "clone", "-b", branch, git_url, str(clone_dir)]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"Git 克隆失败: {stderr.decode()}")
                return {"success": False, "message": f"Git 克隆失败: {stderr.decode()}"}

            # 查找插件目录
            plugin_dir = None
            for item in clone_dir.iterdir():
                if item.is_dir() and (item / "main.py").exists():
                    plugin_dir = item
                    break

            if not plugin_dir:
                return {"success": False, "message": "仓库中未找到有效的插件目录"}

            # 复制到插件目录
            plugin_name = plugin_dir.name
            target_dir = self.plugin_dir / plugin_name

            if target_dir.exists():
                shutil.rmtree(target_dir)

            shutil.move(str(plugin_dir), str(target_dir))

            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)

            # 安装依赖
            requirements_path = target_dir / "requirements.txt"
            if requirements_path.exists():
                await self._install_plugin_dependencies(requirements_path, pip_mirror=pip_mirror)

            # 加载插件
            await self._load_user_plugins()

            logger.info(f"从 Git 仓库安装插件 {plugin_name} 成功")
            return {
                "success": True,
                "message": f"插件 {plugin_name} 安装成功",
                "plugin_name": plugin_name,
            }

        except Exception as e:
            logger.error(f"从 Git 安装插件失败: {e}")
            return {"success": False, "message": f"安装失败: {str(e)}"}

    def _load_plugin_metadata(self, plugin_dir: Path) -> Dict[str, Any]:
        """加载插件元数据

        Args:
            plugin_dir: 插件目录

        Returns:
            元数据字典
        """
        metadata_path = plugin_dir / "metadata.yaml"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                logger.warning(f"加载插件元数据失败: {e}")

        # 返回默认元数据
        return {
            "name": plugin_dir.name,
            "version": "1.0.0",
            "description": "无描述",
            "author": "未知",
        }

    async def _fetch_github_releases(self, api_url: str) -> list[dict]:
        """获取 GitHub Releases 信息

        Args:
            api_url: GitHub API URL

        Returns:
            Releases 列表，每个元素包含 tag_name、zipball_url 等
        """
        try:
            kwargs = {"timeout": aiohttp.ClientTimeout(total=30)}
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, **kwargs) as response:
                    if response.status == 200:
                        releases = await response.json()
                        if isinstance(releases, list) and len(releases) > 0:
                            result = []
                            for release in releases[:5]:  # 只取前5个
                                result.append({
                                    "tag_name": release.get("tag_name"),
                                    "name": release.get("name"),
                                    "zipball_url": release.get("zipball_url"),
                                    "published_at": release.get("published_at"),
                                    "body": release.get("body"),
                                })
                            return result
                        return []
                    else:
                        logger.warning(f"获取 GitHub Releases 失败，状态码: {response.status}")
                        return []
        except Exception as e:
            logger.warning(f"获取 GitHub Releases 异常: {e}")
            return []

    async def _download_file(
        self,
        url: str,
        dest_path: Path,
        proxy: Optional[str] = None,
        timeout: int = 60
    ) -> bool:
        """下载文件

        Args:
            url: 下载 URL
            dest_path: 目标路径
            proxy: 代理设置
            timeout: 超时时间（秒）

        Returns:
            是否下载成功
        """
        try:
            import aiohttp

            kwargs = {"timeout": aiohttp.ClientTimeout(total=timeout)}
            if proxy:
                kwargs["proxy"] = proxy

            async with aiohttp.ClientSession() as session:
                async with session.get(url, **kwargs) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(dest_path, 'wb') as f:
                            f.write(content)
                        logger.info(f"文件下载成功: {dest_path}")
                        return True
                    else:
                        logger.error(f"下载失败，状态码: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            return False

    async def _install_plugin_dependencies(
        self, requirements_path: Path, pip_mirror: Optional[str] = None
    ) -> bool:
        """安装插件依赖

        Args:
            requirements_path: requirements.txt 文件路径
            pip_mirror: pip 镜像源（可选，如果未指定则使用清华源）

        Returns:
            是否安装成功
        """
        try:
            with open(requirements_path, 'r', encoding='utf-8') as f:
                requirements = f.read()

            # 检查是否使用 uv
            use_uv = shutil.which("uv") is not None

            if use_uv:
                cmd = ["uv", "pip", "install", "-r", str(requirements_path)]
            else:
                cmd = ["pip", "install", "-r", str(requirements_path)]

            # 添加镜像源
            if pip_mirror:
                cmd.extend(["-i", pip_mirror])
                logger.info(f"使用用户指定的 pip 镜像源: {pip_mirror}")
            else:
                # 默认使用清华源
                cmd.extend(["-i", PIP_MIRRORS[0]])
                logger.info(f"使用默认 pip 镜像源: {PIP_MIRRORS[0]}")

            logger.info(f"安装插件依赖: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"插件依赖安装成功")
                return True
            else:
                logger.error(f"插件依赖安装失败: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"安装插件依赖失败: {e}")
            return False

    async def ping_github_proxies(self) -> Dict[str, Any]:
        """测试 GitHub 代理可用性

        Returns:
            代理测试结果
        """
        results = []
        test_url = "https://github.com"

        for proxy in GITHUB_PROXIES:
            try:
                proxied_url = f"{proxy}/{test_url}"
                start = asyncio.get_event_loop().time()
                success = await self._download_file(
                    proxied_url,
                    Path(tempfile.gettempdir()) / "ping_test",
                    timeout=10
                )
                elapsed = asyncio.get_event_loop().time() - start

                results.append({
                    "proxy": proxy,
                    "available": success,
                    "latency": round(elapsed * 1000, 2),  # 转换为毫秒
                })

            except Exception as e:
                results.append({
                    "proxy": proxy,
                    "available": False,
                    "latency": -1,
                    "error": str(e),
                })

        return {"proxies": results}

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

    def parse_github_url(self, url: str) -> tuple[str, str, str | None]:
        """解析 GitHub 仓库 URL（参考 AstrBot 实现）

        Args:
            url: GitHub 仓库 URL

        Returns:
            (作者名, 仓库名, 分支名) 元组
            如果分支为 None，则应尝试从 Releases API 获取或使用默认分支

        Raises:
            ValueError: 如果 URL 格式不正确
        """
        cleaned_url = url.rstrip("/")
        # 支持: https://github.com/user/repo[.git][/tree/branch]
        pattern = r"^https?://github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)(\.git)?(?:/tree/([a-zA-Z0-9_-]+))?$"
        match = re.match(pattern, cleaned_url)

        if match:
            author = match.group(1)
            repo = match.group(2)
            branch = match.group(4)
            return author, repo, branch

        raise ValueError(f"无效的 GitHub URL: {url}")

    def format_plugin_name(self, name: str) -> str:
        """格式化插件名称（参考 AstrBot 实现）

        Args:
            name: 插件名称

        Returns:
            格式化后的名称（连字符转下划线，小写）
        """
        return name.replace("-", "_").lower()


# 创建全局插件管理器实例
plugin_manager = PluginManager()
