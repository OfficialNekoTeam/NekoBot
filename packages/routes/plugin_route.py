"""插件管理API

提供插件的启用、禁用、重载、上传、删除、配置编辑等功能
"""

import os
import tempfile
from typing import Dict, Any
from loguru import logger

from .route import Route, Response, RouteContext
from ..core.plugin_manager import plugin_manager, GITHUB_PROXIES, PIP_MIRRORS


class PluginRoute(Route):
    """插件管理路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.routes = [
            ("/api/plugins/list", "GET", self.get_plugins),
            ("/api/plugins/info", "GET", self.get_plugin_info),
            ("/api/plugins/enable", "POST", self.enable_plugin),
            ("/api/plugins/disable", "POST", self.disable_plugin),
            ("/api/plugins/reload", "POST", self.reload_plugin),
            ("/api/plugins/upload", "POST", self.upload_plugin),
            ("/api/plugins/delete", "POST", self.delete_plugin),
            ("/api/plugins/config", "GET", self.get_plugin_config),
            ("/api/plugins/config", "POST", self.update_plugin_config),
            ("/api/plugins/install", "POST", self.install_plugin),
            ("/api/plugins/install/git", "POST", self.install_plugin_from_git),
            ("/api/plugins/marketplace", "GET", self.get_marketplace_list),
            ("/api/plugins/proxies", "GET", self.get_proxies),
            ("/api/plugins/proxies/ping", "POST", self.ping_proxies),
            ("/api/plugins/readme", "GET", self.get_plugin_readme),
        ]

    async def get_plugins(self) -> Dict[str, Any]:
        """获取所有插件列表"""
        try:
            plugins_info = plugin_manager.get_all_plugins_info()
            logger.info(f"Plugin manager has {len(plugin_manager.plugins)} plugins")
            logger.info(f"Plugin manager enabled: {plugin_manager.enabled_plugins}")
            logger.info(f"Plugins info: {plugins_info}")
            return Response().ok(data=plugins_info).to_dict()
        except Exception as e:
            logger.error(f"获取插件列表失败: {e}")
            return Response().error(f"获取插件列表失败: {str(e)}").to_dict()

    async def get_plugin_info(self) -> Dict[str, Any]:
        """获取指定插件信息"""
        try:
            from quart import request

            plugin_name = request.args.get("name")
            if not plugin_name:
                return Response().error("缺少插件名称参数").to_dict()

            plugin_info = plugin_manager.get_plugin_info(plugin_name)
            if not plugin_info:
                return Response().error(f"插件 {plugin_name} 不存在").to_dict()

            return Response().ok(data=plugin_info).to_dict()
        except Exception as e:
            logger.error(f"获取插件信息失败: {e}")
            return Response().error(f"获取插件信息失败: {str(e)}").to_dict()

    async def enable_plugin(self) -> Dict[str, Any]:
        """启用插件"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            plugin_name = data.get("name")
            if not plugin_name:
                return Response().error("缺少插件名称").to_dict()

            success = await plugin_manager.enable_plugin(plugin_name)
            if success:
                return Response().ok(message=f"插件 {plugin_name} 已启用").to_dict()
            else:
                return Response().error(f"插件 {plugin_name} 启用失败").to_dict()
        except Exception as e:
            logger.error(f"启用插件失败: {e}")
            return Response().error(f"启用插件失败: {str(e)}").to_dict()

    async def disable_plugin(self) -> Dict[str, Any]:
        """禁用插件"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            plugin_name = data.get("name")
            if not plugin_name:
                return Response().error("缺少插件名称").to_dict()

            success = await plugin_manager.disable_plugin(plugin_name)
            if success:
                return Response().ok(message=f"插件 {plugin_name} 已禁用").to_dict()
            else:
                return Response().error(f"插件 {plugin_name} 禁用失败").to_dict()
        except Exception as e:
            logger.error(f"禁用插件失败: {e}")
            return Response().error(f"禁用插件失败: {str(e)}").to_dict()

    async def reload_plugin(self) -> Dict[str, Any]:
        """重载插件"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            plugin_name = data.get("name")
            if not plugin_name:
                return Response().error("缺少插件名称").to_dict()

            success = await plugin_manager.reload_plugin(plugin_name)
            if success:
                return Response().ok(message=f"插件 {plugin_name} 已重载").to_dict()
            else:
                return Response().error(f"插件 {plugin_name} 重载失败").to_dict()
        except Exception as e:
            logger.error(f"重载插件失败: {e}")
            return Response().error(f"重载插件失败: {str(e)}").to_dict()

    async def upload_plugin(self) -> Dict[str, Any]:
        """上传插件"""
        try:
            from quart import request

            # 检查是否有文件上传
            files = await request.files
            if "file" not in files:
                return Response().error("未找到上传文件").to_dict()

            file = files["file"]
            if not file.filename:
                return Response().error("文件名为空").to_dict()

            # 检查文件扩展名
            if not file.filename.endswith(".zip"):
                return Response().error("只支持 zip 格式的插件包").to_dict()

            # 保存到临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name

            # 调用插件管理器上传插件
            result = await plugin_manager.upload_plugin(temp_file_path)

            # 删除临时文件
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass

            if result.get("success"):
                return (
                    Response()
                    .ok(
                        message=result.get("message"),
                        data={"plugin_name": result.get("plugin_name")},
                    )
                    .to_dict()
                )
            else:
                return Response().error(result.get("message")).to_dict()
        except Exception as e:
            logger.error(f"上传插件失败: {e}")
            return Response().error(f"上传插件失败: {str(e)}").to_dict()

    async def delete_plugin(self) -> Dict[str, Any]:
        """删除插件"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            plugin_name = data.get("name")
            if not plugin_name:
                return Response().error("缺少插件名称").to_dict()

            result = await plugin_manager.delete_plugin(plugin_name)

            if result.get("success"):
                return Response().ok(message=result.get("message")).to_dict()
            else:
                return Response().error(result.get("message")).to_dict()
        except Exception as e:
            logger.error(f"删除插件失败: {e}")
            return Response().error(f"删除插件失败: {str(e)}").to_dict()

    async def get_plugin_config(self) -> Dict[str, Any]:
        """获取插件配置"""
        try:
            from quart import request

            plugin_name = request.args.get("name")
            if not plugin_name:
                return Response().error("缺少插件名称参数").to_dict()

            # 检查插件是否存在
            if plugin_name not in plugin_manager.plugins:
                return Response().error(f"插件 {plugin_name} 不存在").to_dict()

            # 加载插件配置
            config = plugin_manager.load_plugin_config(plugin_name)

            # 获取插件配置 schema
            plugin = plugin_manager.plugins[plugin_name]
            conf_schema = getattr(plugin, "conf_schema", None)

            return (
                Response().ok(data={"config": config, "schema": conf_schema}).to_dict()
            )
        except Exception as e:
            logger.error(f"获取插件配置失败: {e}")
            return Response().error(f"获取插件配置失败: {str(e)}").to_dict()

    async def update_plugin_config(self) -> Dict[str, Any]:
        """更新插件配置"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            plugin_name = data.get("name")
            config = data.get("config")

            if not plugin_name:
                return Response().error("缺少插件名称").to_dict()

            if config is None:
                return Response().error("缺少配置数据").to_dict()

            # 检查插件是否存在
            if plugin_name not in plugin_manager.plugins:
                return Response().error(f"插件 {plugin_name} 不存在").to_dict()

            # 保存插件配置
            success = plugin_manager.save_plugin_config(plugin_name, config)

            if success:
                return Response().ok(message=f"插件 {plugin_name} 配置已更新").to_dict()
            else:
                return Response().error(f"插件 {plugin_name} 配置更新失败").to_dict()
        except Exception as e:
            logger.error(f"更新插件配置失败: {e}")
            return Response().error(f"更新插件配置失败: {str(e)}").to_dict()

    async def install_plugin(self) -> Dict[str, Any]:
        """从 URL 安装插件

        请求参数:
            url: 插件 URL（必需）
            proxy: 代理 URL（可选）
            use_github_proxy: 是否使用预设 GitHub 代理（可选，默认 false）
            pip_mirror: pip 镜像源（可选，默认使用清华源）
        """
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            url = data.get("url")
            if not url:
                return Response().error("缺少 URL 参数").to_dict()

            proxy = data.get("proxy")
            use_github_proxy = data.get("use_github_proxy", False)
            pip_mirror = data.get("pip_mirror")

            # 调用插件管理器从 URL 安装插件
            result = await plugin_manager.install_plugin_from_url(
                url, proxy=proxy, use_github_proxy=use_github_proxy, pip_mirror=pip_mirror
            )

            if result.get("success"):
                return (
                    Response()
                    .ok(
                        message=result.get("message"),
                        data={"plugin_name": result.get("plugin_name")},
                    )
                    .to_dict()
                )
            else:
                return Response().error(result.get("message")).to_dict()
        except Exception as e:
            logger.error(f"从 URL 安装插件失败: {e}")
            return Response().error(f"从 URL 安装插件失败: {str(e)}").to_dict()

    async def install_plugin_from_git(self) -> Dict[str, Any]:
        """从 Git 仓库安装插件

        请求参数:
            url: Git 仓库 URL（必需）
            branch: 分支名称（可选，默认 main）
            pip_mirror: pip 镜像源（可选，默认使用清华源）
        """
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            git_url = data.get("url")
            if not git_url:
                return Response().error("缺少 Git URL 参数").to_dict()

            branch = data.get("branch", "main")
            pip_mirror = data.get("pip_mirror")

            # 调用插件管理器从 Git 安装插件
            result = await plugin_manager.install_plugin_from_git(git_url, branch, pip_mirror=pip_mirror)

            if result.get("success"):
                return (
                    Response()
                    .ok(
                        message=result.get("message"),
                        data={"plugin_name": result.get("plugin_name")},
                    )
                    .to_dict()
                )
            else:
                return Response().error(result.get("message")).to_dict()
        except Exception as e:
            logger.error(f"从 Git 安装插件失败: {e}")
            return Response().error(f"从 Git 安装插件失败: {str(e)}").to_dict()

    async def get_marketplace_list(self) -> Dict[str, Any]:
        """获取在线插件商店列表（示例实现）"""
        try:
            from quart import request

            # 这里可以调用远程 API 获取插件列表
            # 目前返回示例数据
            plugins = [
                {
                    "name": "NekoBot_Plugins_Example",
                    "version": "1.0.0",
                    "description": "NekoBot 示例插件",
                    "author": "NekoBotDevs",
                    "repository": "https://github.com/NekoBotDevs/NekoBot_Plugins_Example",
                    "downloads": 1000,
                    "stars": 50,
                }
            ]

            return Response().ok(data={"plugins": plugins}).to_dict()
        except Exception as e:
            logger.error(f"获取插件商店列表失败: {e}")
            return Response().error(f"获取插件商店列表失败: {str(e)}").to_dict()

    async def get_proxies(self) -> Dict[str, Any]:
        """获取可用的 GitHub 代理和 Pip 镜像源列表"""
        try:
            return Response().ok(data={
                "github_proxies": GITHUB_PROXIES,
                "pip_mirrors": PIP_MIRRORS,
            }).to_dict()
        except Exception as e:
            logger.error(f"获取代理列表失败: {e}")
            return Response().error(f"获取代理列表失败: {str(e)}").to_dict()

    async def ping_proxies(self) -> Dict[str, Any]:
        """测试 GitHub 代理可用性"""
        try:
            result = await plugin_manager.ping_github_proxies()
            return Response().ok(data=result).to_dict()
        except Exception as e:
            logger.error(f"测试代理失败: {e}")
            return Response().error(f"测试代理失败: {str(e)}").to_dict()

    async def get_plugin_readme(self) -> Dict[str, Any]:
        """获取插件 README 内容"""
        try:
            from quart import request

            plugin_name = request.args.get("name")
            if not plugin_name:
                return Response().error("缺少插件名称参数").to_dict()

            # 查找插件目录
            plugin_dir = plugin_manager.plugin_dir / plugin_name
            if not plugin_dir.exists():
                return Response().error(f"插件 {plugin_name} 不存在").to_dict()

            # 查找 README 文件
            readme_path = None
            for name in ["README.md", "readme.md", "README.txt", "readme.txt"]:
                potential_path = plugin_dir / name
                if potential_path.exists():
                    readme_path = potential_path
                    break

            if not readme_path:
                return Response().error("插件未提供 README 文件").to_dict()

            # 读取 README 内容
            with open(readme_path, 'r', encoding='utf-8') as f:
                readme_content = f.read()

            return Response().ok(data={
                "plugin_name": plugin_name,
                "readme": readme_content,
            }).to_dict()
        except Exception as e:
            logger.error(f"获取插件 README 失败: {e}")
            return Response().error(f"获取插件 README 失败: {str(e)}").to_dict()
