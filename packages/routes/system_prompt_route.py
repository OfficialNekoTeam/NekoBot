"""系统提示词API

提供系统提示词的创建、更新、删除等功能
"""

from typing import Dict, Any
from loguru import logger

from .route import Route, Response, RouteContext
from ..core.database import db_manager
from ..core.prompt_manager import prompt_manager


class SystemPromptRoute(Route):
    """系统提示词管理路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.routes = [
            ("/api/system-prompts/list", "GET", self.get_system_prompts),
            ("/api/system-prompts/create", "POST", self.create_system_prompt),
            ("/api/system-prompts/update", "POST", self.update_system_prompt),
            ("/api/system-prompts/delete", "POST", self.delete_system_prompt),
        ]

    async def get_system_prompts(self) -> Dict[str, Any]:
        """获取所有系统提示词列表"""
        try:
            # 从数据库获取所有系统提示词
            system_prompts = db_manager.get_all_system_prompts()
            return Response().ok(data={"system_prompts": system_prompts}).to_dict()
        except Exception as e:
            logger.error(f"获取系统提示词列表失败: {e}")
            return Response().error(f"获取系统提示词列表失败: {str(e)}").to_dict()

    async def create_system_prompt(self) -> Dict[str, Any]:
        """创建新系统提示词"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            is_valid, error_msg = await self.validate_required_fields(
                data, ["name", "prompt"]
            )
            if not is_valid:
                return Response().error(error_msg).to_dict()

            # 从请求数据中获取参数
            name = data["name"]
            prompt = data["prompt"]
            description = data.get("description", "")

            # 创建系统提示词
            success = db_manager.create_system_prompt(name, prompt, description)
            if not success:
                return Response().error("系统提示词名称已存在").to_dict()

            # 重新加载提示词
            prompt_manager.load_all_prompts()

            return (
                Response()
                .ok(data={"name": name}, message="系统提示词创建成功")
                .to_dict()
            )
        except Exception as e:
            logger.error(f"创建系统提示词失败: {e}")
            return Response().error(f"创建系统提示词失败: {str(e)}").to_dict()

    async def update_system_prompt(self) -> Dict[str, Any]:
        """更新系统提示词"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            name = data.get("name")
            if not name:
                return Response().error("缺少提示词名称").to_dict()

            # 检查系统提示词是否存在
            existing_prompt = db_manager.get_system_prompt(name)
            if not existing_prompt:
                return Response().error("系统提示词不存在").to_dict()

            # 准备更新参数
            prompt = data.get("prompt")
            description = data.get("description")

            # 更新系统提示词
            success = db_manager.update_system_prompt(name, prompt, description)
            if not success:
                return Response().error("系统提示词更新失败").to_dict()

            # 重新加载提示词
            prompt_manager.load_all_prompts()

            return Response().ok(message="系统提示词更新成功").to_dict()
        except Exception as e:
            logger.error(f"更新系统提示词失败: {e}")
            return Response().error(f"更新系统提示词失败: {str(e)}").to_dict()

    async def delete_system_prompt(self) -> Dict[str, Any]:
        """删除系统提示词"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            name = data.get("name")
            if not name:
                return Response().error("缺少提示词名称").to_dict()

            # 不能删除默认提示词
            if name == "default":
                return Response().error("不能删除默认系统提示词").to_dict()

            # 删除系统提示词
            success = db_manager.delete_system_prompt(name)
            if not success:
                return Response().error("系统提示词删除失败").to_dict()

            # 重新加载提示词
            prompt_manager.load_all_prompts()

            return Response().ok(message="系统提示词删除成功").to_dict()
        except Exception as e:
            logger.error(f"删除系统提示词失败: {e}")
            return Response().error(f"删除系统提示词失败: {str(e)}").to_dict()
