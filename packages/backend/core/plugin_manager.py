"""插件管理器"""

import os
import re
import sys
import importlib
import asyncio
import shutil
import zipfile
import aiohttp
from pathlib import Path
from typing import Dict, List, Any, Optional, Type
from loguru import logger
from ..plugins.base import BasePlugin, create_plugin_decorator
from ..plugins.plugin_data_manager import PluginDataManager


class PluginManager:
    """插件管理器，负责加载、启用、禁用、重载插件以及分发消息和命令"""

    def __init__(self, plugin_dir: str = "data/plugins"):
        self.plugin_dir = Path(plugin_dir)
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self.plugins: Dict[str, BasePlugin] = {}
        self.enabled_plugins: List[str] = []
        # 官方插件映射，key 为插件名，value 为模块路径
        self.official_plugins: Dict[str, str] = {}
        # 平台服务器引用，用于插件发送消息
        self.platform_server = None
        # 插件数据管理器
        self.plugin_data_manager = PluginDataManager()

    async def load_plugins(self) -> None:
        """加载所有插件（官方 + 用户）"""
        logger.info("开始加载插件...")
        await self._load_official_plugins()
        await self._load_user_plugins()
        logger.info(f"插件加载完成，共 {len(self.plugins)} 个插件")

    async def _load_official_plugins(self) -> None:
        """加载官方插件"""
        for name, module_path in self.official_plugins.items():
            try:
                plugin = await self._load_plugin_from_module(module_path, name)
                if plugin:
                    self.plugins[name] = plugin
                    logger.info(f"已加载官方插件: {name}")
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
                        logger.info(f"已加载用户插件: {name}")
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
                spec = importlib.util.find_spec(module_path)  # type: ignore[attr-defined]
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)  # type: ignore[attr-defined]
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
                logger.warning(f"插件 {plugin_name} 中未找到 BasePlugin 子类")
                return None
            # 实例化插件并处理装饰器
            plugin_instance = plugin_cls()
            create_plugin_decorator(plugin_instance)  # 注册装饰器中的命令/处理器

            # 加载插件配置 schema
            if plugin_path:
                conf_schema = self.plugin_data_manager.load_conf_schema(plugin_path)
                if conf_schema:
                    # 将配置 schema 附加到插件实例
                    plugin_instance.conf_schema = conf_schema
                    logger.info(f"已加载插件 {plugin_name} 的配置 schema")

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

            logger.info(f"已启用插件: {name}")
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
            logger.info(f"已禁用插件: {name}")
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
                    await self.enable_plugin(name)
                logger.info(f"已重载插件: {name}")
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
            return None
        return {
            "name": plugin.name,
            "version": plugin.version,
            "description": plugin.description,
            "author": plugin.author,
            "enabled": plugin.enabled,
            "commands": list(plugin.commands.keys()),
            "is_official": name in self.official_plugins,
        }

    def get_all_plugins_info(self) -> Dict[str, Dict[str, Any]]:
        """返回所有已加载插件的信息"""
        return {name: self.get_plugin_info(name) for name in self.plugins}

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
        self.enabled_plugins.clear()
        self.platform_server = None
        logger.info("所有插件已卸载")

    async def delete_plugin_data(self, plugin_name: str) -> bool:
        """删除插件数据

        Args:
            plugin_name: 插件名称

        Returns:
            是否删除成功
        """
        return self.plugin_data_manager.delete_plugin_data(plugin_name)

    def get_plugin_data_dir(self, plugin_name: str) -> Path:
        """获取插件数据目录

        Args:
            plugin_name: 插件名称

        Returns:
            插件数据目录路径
        """
        return self.plugin_data_manager.get_plugin_data_dir(plugin_name)

    def load_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """加载插件配置

        Args:
            plugin_name: 插件名称

        Returns:
            配置字典
        """
        return self.plugin_data_manager.load_plugin_config(plugin_name)

    def save_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """保存插件配置

        Args:
            plugin_name: 插件名称
            config: 配置字典

        Returns:
            是否保存成功
        """
        return self.plugin_data_manager.save_plugin_config(plugin_name, config)

    def get_all_plugin_data_dirs(self) -> list[Path]:
        """获取所有插件数据目录

        Returns:
            插件数据目录列表
        """
        return self.plugin_data_manager.get_all_plugin_data_dirs()

    def get_plugin_data_size(self, plugin_name: str) -> int:
        """获取插件数据目录大小

        Args:
            plugin_name: 插件名称

        Returns:
            数据目录大小（字节）
        """
        return self.plugin_data_manager.get_plugin_data_size(plugin_name)

    async def upload_plugin(self, zip_file_path: str) -> Dict[str, Any]:
        """上传并安装插件

        Args:
            zip_file_path: 上传的 zip 文件路径

        Returns:
            包含状态和消息的字典
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(zip_file_path):
                return {"success": False, "message": "文件不存在"}

            # 检查是否为 zip 文件
            if not zipfile.is_zipfile(zip_file_path):
                return {"success": False, "message": "文件不是有效的 zip 压缩包"}

            # 创建临时目录
            temp_dir = self.plugin_dir / "temp"
            temp_dir.mkdir(exist_ok=True)

            # 解压文件
            with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # 查找插件目录（假设插件在根目录下）
            plugin_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
            if not plugin_dirs:
                return {"success": False, "message": "压缩包中未找到插件目录"}

            # 获取第一个目录作为插件目录
            plugin_dir = plugin_dirs[0]
            plugin_name = plugin_dir.name

            # 检查插件是否已存在
            if plugin_name in self.plugins:
                return {"success": False, "message": f"插件 {plugin_name} 已存在"}

            # 检查插件是否包含 main.py
            if not (plugin_dir / "main.py").exists():
                return {"success": False, "message": "插件目录中未找到 main.py 文件"}

            # 移动插件到插件目录
            target_dir = self.plugin_dir / plugin_name
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.move(str(plugin_dir), str(target_dir))

            # 清理临时目录
            shutil.rmtree(temp_dir)

            # 加载插件
            module_path = f"{plugin_name}.main"
            plugin = await self._load_plugin_from_module(
                module_path, plugin_name, target_dir
            )
            if plugin:
                self.plugins[plugin_name] = plugin
                logger.info(f"已上传并加载插件: {plugin_name}")
                return {
                    "success": True,
                    "message": f"插件 {plugin_name} 上传成功",
                    "plugin_name": plugin_name,
                }
            else:
                return {"success": False, "message": "插件加载失败"}
        except Exception as e:
            logger.error(f"上传插件失败: {e}")
            return {"success": False, "message": f"上传插件失败: {str(e)}"}

    async def delete_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """删除插件

        Args:
            plugin_name: 插件名称

        Returns:
            包含状态和消息的字典
        """
        try:
            # 检查插件是否存在
            if plugin_name not in self.plugins:
                return {"success": False, "message": f"插件 {plugin_name} 不存在"}

            # 禁用插件
            if plugin_name in self.enabled_plugins:
                await self.disable_plugin(plugin_name)

            # 调用插件的 on_unload
            plugin = self.plugins[plugin_name]
            try:
                await plugin.on_unload()
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

            logger.info(f"已删除插件: {plugin_name}")
            return {"success": True, "message": f"插件 {plugin_name} 删除成功"}
        except Exception as e:
            logger.error(f"删除插件失败: {e}")
            return {"success": False, "message": f"删除插件失败: {str(e)}"}

    def _parse_github_url(self, url: str) -> Optional[str]:
        """解析 GitHub URL 并返回下载链接

        Args:
            url: GitHub URL

        Returns:
            下载链接，如果不是 GitHub URL 则返回 None
        """
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

    async def install_plugin_from_url(
        self, url: str, proxy: Optional[str] = None
    ) -> Dict[str, Any]:
        """从 URL 安装插件

        Args:
            url: 插件 URL（支持 GitHub 仓库链接、分支链接、Release 链接、Archive 链接、直接 zip 文件链接）
            proxy: 代理地址（可选）

        Returns:
            包含状态和消息的字典
        """
        try:
            # 检查 URL 格式
            if not url.startswith(("http://", "https://")):
                return {"success": False, "message": "URL 格式不正确"}

            # 解析 URL
            download_url = self._parse_github_url(url)
            if download_url is None:
                # 不是 GitHub URL，直接使用原 URL
                download_url = url

            # 创建临时目录
            temp_dir = self.plugin_dir / "temp"
            temp_dir.mkdir(exist_ok=True)

            # 下载文件
            zip_file_path = temp_dir / "plugin.zip"

            # 配置 aiohttp 客户端
            client_kwargs = {}
            if proxy:
                client_kwargs["proxy"] = proxy

            async with aiohttp.ClientSession() as session:
                async with session.get(download_url, **client_kwargs) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "message": f"下载失败，状态码: {response.status}",
                        }
                    with open(zip_file_path, "wb") as f:
                        f.write(await response.read())

            # 检查是否为有效的 zip 文件
            if not zipfile.is_zipfile(zip_file_path):
                return {"success": False, "message": "下载的文件不是有效的 zip 压缩包"}

            # 解压文件
            with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # 查找插件目录
            plugin_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
            if not plugin_dirs:
                return {"success": False, "message": "压缩包中未找到插件目录"}

            # 获取第一个目录作为插件目录
            plugin_dir = plugin_dirs[0]
            plugin_name = plugin_dir.name

            # 检查插件是否已存在
            if plugin_name in self.plugins:
                return {"success": False, "message": f"插件 {plugin_name} 已存在"}

            # 检查插件是否包含 main.py
            if not (plugin_dir / "main.py").exists():
                return {"success": False, "message": "插件目录中未找到 main.py 文件"}

            # 移动插件到插件目录
            target_dir = self.plugin_dir / plugin_name
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.move(str(plugin_dir), str(target_dir))

            # 清理临时目录
            shutil.rmtree(temp_dir)

            # 加载插件
            module_path = f"{plugin_name}.main"
            plugin = await self._load_plugin_from_module(
                module_path, plugin_name, target_dir
            )
            if plugin:
                self.plugins[plugin_name] = plugin
                logger.info(f"已从 URL 安装并加载插件: {plugin_name}")
                return {
                    "success": True,
                    "message": f"插件 {plugin_name} 安装成功",
                    "plugin_name": plugin_name,
                }
            else:
                return {"success": False, "message": "插件加载失败"}
        except Exception as e:
            logger.error(f"从 URL 安装插件失败: {e}")
            return {"success": False, "message": f"安装插件失败: {str(e)}"}


# 创建全局插件管理器实例
plugin_manager = PluginManager()
