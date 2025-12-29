"""人设/提示词API

提供人设的创建、更新、删除等功能
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger

from .route import Route, Response, RouteContext

PERSONALITIES_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "personalities.json"
)


class PersonalityRoute(Route):
    """人设管理路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.personalities_path = PERSONALITIES_PATH
        self.personalities_path.parent.mkdir(parents=True, exist_ok=True)
        self.routes = {
            "/api/personalities/list": ("GET", self.get_personalities),
            "/api/personalities/create": ("POST", self.create_personality),
            "/api/personalities/update": ("POST", self.update_personality),
            "/api/personalities/delete": ("POST", self.delete_personality),
        }

    async def get_personalities(self) -> Dict[str, Any]:
        """获取所有人设列表"""
        try:
            personalities = self._load_personalities()
            personalities_list = list(personalities.values())
            return Response().ok(data={"personalities": personalities_list}).to_dict()
        except Exception as e:
            logger.error(f"获取人设列表失败: {e}")
            return Response().error(f"获取人设列表失败: {str(e)}").to_dict()

    async def create_personality(self) -> Dict[str, Any]:
        """创建新人设"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            is_valid, error_msg = await self.validate_required_fields(
                data, ["name", "description", "prompt"]
            )
            if not is_valid:
                return Response().error(error_msg).to_dict()

            personalities = self._load_personalities()
            personality_id = str(uuid.uuid4())

            personalities[personality_id] = {
                "id": personality_id,
                "name": data["name"],
                "description": data.get("description", ""),
                "prompt": data["prompt"],
                "enabled": data.get("enabled", True),
                "created_at": self._get_current_timestamp(),
            }

            self._save_personalities(personalities)
            return (
                Response()
                .ok(data={"id": personality_id}, message="人设创建成功")
                .to_dict()
            )
        except Exception as e:
            logger.error(f"创建人设失败: {e}")
            return Response().error(f"创建人设失败: {str(e)}").to_dict()

    async def update_personality(self) -> Dict[str, Any]:
        """更新人设"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            personality_id = data.get("id")
            if not personality_id:
                return Response().error("缺少人设ID").to_dict()

            personalities = self._load_personalities()
            if personality_id not in personalities:
                return Response().error("人设不存在").to_dict()

            personality = personalities[personality_id]
            if "name" in data:
                personality["name"] = data["name"]
            if "description" in data:
                personality["description"] = data["description"]
            if "prompt" in data:
                personality["prompt"] = data["prompt"]
            if "enabled" in data:
                personality["enabled"] = data["enabled"]

            personality["updated_at"] = self._get_current_timestamp()
            self._save_personalities(personalities)
            return Response().ok(message="人设更新成功").to_dict()
        except Exception as e:
            logger.error(f"更新人设失败: {e}")
            return Response().error(f"更新人设失败: {str(e)}").to_dict()

    async def delete_personality(self) -> Dict[str, Any]:
        """删除人设"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            personality_id = data.get("id")
            if not personality_id:
                return Response().error("缺少人设ID").to_dict()

            personalities = self._load_personalities()
            if personality_id not in personalities:
                return Response().error("人设不存在").to_dict()

            del personalities[personality_id]
            self._save_personalities(personalities)
            return Response().ok(message="人设删除成功").to_dict()
        except Exception as e:
            logger.error(f"删除人设失败: {e}")
            return Response().error(f"删除人设失败: {str(e)}").to_dict()

    def _load_personalities(self) -> Dict[str, Any]:
        """加载所有人设"""
        if not self.personalities_path.exists():
            return {}

        try:
            with open(self.personalities_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载人设文件失败: {e}")
            return {}

    def _save_personalities(self, personalities: Dict[str, Any]) -> None:
        """保存所有人设"""
        with open(self.personalities_path, "w", encoding="utf-8") as f:
            json.dump(personalities, f, indent=2, ensure_ascii=False)

    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime

        return datetime.now().isoformat()
