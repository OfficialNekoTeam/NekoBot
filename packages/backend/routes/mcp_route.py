"""MCP配置API

提供MCP组件的添加、更新、删除等功能
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any
from loguru import logger

from .route import Route, Response, RouteContext

MCP_PATH = Path(__file__).parent.parent.parent.parent / "data" / "mcp.json"


class McpRoute(Route):
    """MCP配置路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.mcp_path = MCP_PATH
        self.mcp_path.parent.mkdir(parents=True, exist_ok=True)
        self.routes = {
            "/api/mcp/list": ("GET", self.get_mcp_list),
            "/api/mcp/add": ("POST", self.add_mcp),
            "/api/mcp/update": ("POST", self.update_mcp),
            "/api/mcp/delete": ("POST", self.delete_mcp),
        }

    async def get_mcp_list(self) -> Dict[str, Any]:
        """获取MCP列表"""
        try:
            mcp_list = self._load_mcp()
            mcp_items = list(mcp_list.values())
            return Response().ok(data={"mcps": mcp_items}).to_dict()
        except Exception as e:
            logger.error(f"获取MCP列表失败: {e}")
            return Response().error(f"获取MCP列表失败: {str(e)}").to_dict()

    async def add_mcp(self) -> Dict[str, Any]:
        """添加MCP组件"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            is_valid, error_msg = await self.validate_required_fields(
                data, ["name", "type", "config"]
            )
            if not is_valid:
                return Response().error(error_msg).to_dict()

            mcp_list = self._load_mcp()
            mcp_id = str(uuid.uuid4())

            mcp_list[mcp_id] = {
                "id": mcp_id,
                "name": data["name"],
                "type": data["type"],
                "config": data["config"],
                "enabled": data.get("enabled", True),
                "created_at": self._get_current_timestamp(),
            }

            self._save_mcp(mcp_list)
            return Response().ok(data={"id": mcp_id}, message="MCP添加成功").to_dict()
        except Exception as e:
            logger.error(f"添加MCP失败: {e}")
            return Response().error(f"添加MCP失败: {str(e)}").to_dict()

    async def update_mcp(self) -> Dict[str, Any]:
        """更新MCP组件"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            mcp_id = data.get("id")
            if not mcp_id:
                return Response().error("缺少MCP ID").to_dict()

            mcp_list = self._load_mcp()
            if mcp_id not in mcp_list:
                return Response().error("MCP不存在").to_dict()

            mcp = mcp_list[mcp_id]
            if "name" in data:
                mcp["name"] = data["name"]
            if "type" in data:
                mcp["type"] = data["type"]
            if "config" in data:
                mcp["config"] = data["config"]
            if "enabled" in data:
                mcp["enabled"] = data["enabled"]

            mcp["updated_at"] = self._get_current_timestamp()
            self._save_mcp(mcp_list)
            return Response().ok(message="MCP更新成功").to_dict()
        except Exception as e:
            logger.error(f"更新MCP失败: {e}")
            return Response().error(f"更新MCP失败: {str(e)}").to_dict()

    async def delete_mcp(self) -> Dict[str, Any]:
        """删除MCP组件"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            mcp_id = data.get("id")
            if not mcp_id:
                return Response().error("缺少MCP ID").to_dict()

            mcp_list = self._load_mcp()
            if mcp_id not in mcp_list:
                return Response().error("MCP不存在").to_dict()

            del mcp_list[mcp_id]
            self._save_mcp(mcp_list)
            return Response().ok(message="MCP删除成功").to_dict()
        except Exception as e:
            logger.error(f"删除MCP失败: {e}")
            return Response().error(f"删除MCP失败: {str(e)}").to_dict()

    def _load_mcp(self) -> Dict[str, Any]:
        """加载所有MCP配置"""
        if not self.mcp_path.exists():
            return {}

        try:
            with open(self.mcp_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载MCP配置文件失败: {e}")
            return {}

    def _save_mcp(self, mcp_list: Dict[str, Any]) -> None:
        """保存MCP配置"""
        with open(self.mcp_path, "w", encoding="utf-8") as f:
            json.dump(mcp_list, f, indent=2, ensure_ascii=False)

    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime

        return datetime.now().isoformat()
