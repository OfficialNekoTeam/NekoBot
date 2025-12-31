"""人设/提示词API

提供人设的创建、更新、删除等功能
"""

from typing import Dict, Any
from loguru import logger

from .route import Route, Response, RouteContext
from packages.core.database import db_manager
from packages.core.prompt_manager import prompt_manager


class PersonalityRoute(Route):
    """人设管理路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.routes = [
            ("/api/personalities/list", "GET", self.get_personalities),
            ("/api/personalities/create", "POST", self.create_personality),
            ("/api/personalities/update", "POST", self.update_personality),
            ("/api/personalities/delete", "POST", self.delete_personality),
        ]

    async def get_personalities(self) -> Dict[str, Any]:
        """获取所有人设列表"""
        try:
            # 从数据库获取所有人格
            personalities = db_manager.get_all_personalities()
            return Response().ok(data={"personalities": personalities}).to_dict()
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

            # 从请求数据中获取参数
            name = data["name"]
            description = data.get("description", "")
            prompt = data["prompt"]
            enabled = data.get("enabled", True)

            # 创建人格
            success = db_manager.create_personality(name, prompt, description, enabled)
            if not success:
                return Response().error("人设名称已存在").to_dict()

            # 重新加载提示词
            prompt_manager.load_all_prompts()

            return (
                Response()
                .ok(data={"id": name}, message="人设创建成功")
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

            name = data.get("id") or data.get("name")
            if not name:
                return Response().error("缺少人设ID或名称").to_dict()

            # 检查人格是否存在
            existing_personality = db_manager.get_personality(name)
            if not existing_personality:
                return Response().error("人设不存在").to_dict()

            # 准备更新参数
            update_params = {}
            if "name" in data:
                update_params["name"] = data["name"]
            if "description" in data:
                update_params["description"] = data["description"]
            if "prompt" in data:
                update_params["prompt"] = data["prompt"]
            if "enabled" in data:
                update_params["enabled"] = data["enabled"]

            # 更新人格
            success = db_manager.update_personality(
                name,
                prompt=update_params.get("prompt"),
                description=update_params.get("description"),
                enabled=update_params.get("enabled")
            )
            if not success:
                return Response().error("人设更新失败").to_dict()

            # 重新加载提示词
            prompt_manager.load_all_prompts()

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

            name = data.get("id") or data.get("name")
            if not name:
                return Response().error("缺少人设ID或名称").to_dict()

            # 删除人格
            success = db_manager.delete_personality(name)
            if not success:
                return Response().error("人设删除失败").to_dict()

            # 重新加载提示词
            prompt_manager.load_all_prompts()

            return Response().ok(message="人设删除成功").to_dict()
        except Exception as e:
            logger.error(f"删除人设失败: {e}")
            return Response().error(f"删除人设失败: {str(e)}").to_dict()
