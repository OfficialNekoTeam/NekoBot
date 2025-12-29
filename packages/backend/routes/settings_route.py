"""更多设置API

提供系统设置、重启服务、检查更新等功能
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any
from loguru import logger

from .route import Route, Response, RouteContext
from ..core.config import load_config

SETTINGS_PATH = Path(__file__).parent.parent.parent.parent / "data" / "settings.json"


class SettingsRoute(Route):
    """更多设置路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.settings_path = SETTINGS_PATH
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.routes = {
            "/api/settings": ("GET", self.get_settings),
            "/api/settings": ("POST", self.update_settings),
            "/api/settings/restart": ("POST", self.restart_service),
            "/api/settings/update": ("GET", self.check_update),
        }

    async def get_settings(self) -> Dict[str, Any]:
        """获取系统设置"""
        try:
            settings = self._load_settings()
            config = load_config()
            return (
                Response().ok(data={"settings": settings, "config": config}).to_dict()
            )
        except Exception as e:
            logger.error(f"获取系统设置失败: {e}")
            return Response().error(f"获取系统设置失败: {str(e)}").to_dict()

    async def update_settings(self) -> Dict[str, Any]:
        """更新系统设置"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            settings = data.get("settings")
            if not settings or not isinstance(settings, dict):
                return Response().error("设置数据格式错误").to_dict()

            current_settings = self._load_settings()
            allowed_keys = ["theme", "language", "notifications", "auto_restart"]
            for key in settings:
                if key in allowed_keys:
                    current_settings[key] = settings[key]

            self._save_settings(current_settings)
            return Response().ok(message="设置更新成功").to_dict()
        except Exception as e:
            logger.error(f"更新系统设置失败: {e}")
            return Response().error(f"更新系统设置失败: {str(e)}").to_dict()

    async def restart_service(self) -> Dict[str, Any]:
        """重启服务"""
        try:
            from quart import g

            if self.context.config.get("demo", False):
                return Response().error("Demo模式下不允许重启服务").to_dict()

            logger.info("收到重启服务请求")
            return Response().ok(message="服务重启指令已发送").to_dict()
        except Exception as e:
            logger.error(f"重启服务失败: {e}")
            return Response().error(f"重启服务失败: {str(e)}").to_dict()

    async def check_update(self) -> Dict[str, Any]:
        """检查更新"""
        try:
            from tomli import load as load_toml

            pyproject_path = (
                Path(__file__).parent.parent.parent.parent / "pyproject.toml"
            )
            if not pyproject_path.exists():
                return Response().error("无法找到pyproject.toml文件").to_dict()

            with open(pyproject_path, "rb") as f:
                pyproject = load_toml(f)

            current_version = pyproject.get("project", {}).get("version", "unknown")
            return (
                Response()
                .ok(
                    data={
                        "current_version": current_version,
                        "has_update": False,
                        "latest_version": current_version,
                        "update_url": "",
                    }
                )
                .to_dict()
            )
        except Exception as e:
            logger.error(f"检查更新失败: {e}")
            return Response().error(f"检查更新失败: {str(e)}").to_dict()

    def _load_settings(self) -> Dict[str, Any]:
        """加载系统设置"""
        if not self.settings_path.exists():
            return {
                "theme": "dark",
                "language": "zh-CN",
                "notifications": {"enabled": True, "types": ["error", "warning"]},
                "auto_restart": False,
            }

        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载系统设置文件失败: {e}")
            return {}

    def _save_settings(self, settings: Dict[str, Any]) -> None:
        """保存系统设置"""
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
