"""工具提示词API

提供工具提示词的创建、更新、删除等功能
"""

from typing import Dict, Any
from loguru import logger

from .route import Route, Response, RouteContext
from ..core.database import db_manager
from ..core.prompt_manager import prompt_manager


class ToolPromptRoute(Route):
    """工具提示词管理路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.routes = [
            ("/api/tool-prompts/list", "GET", self.get_tool_prompts),
            ("/api/tool-prompts/create", "POST", self.create_tool_prompt),
            ("/api/tool-prompts/update", "POST", self.update_tool_prompt),
            ("/api/tool-prompts/delete", "POST", self.delete_tool_prompt),
        ]

    async def get_tool_prompts(self) -> Dict[str, Any]:
        """获取所有工具提示词列表"""
        try:
            # 从数据库获取所有工具提示词
            tool_prompts = db_manager.get_all_tool_prompts()
            return Response().ok(data={"tool_prompts": tool_prompts}).to_dict()
        except Exception as e:
            logger.error(f"获取工具提示词列表失败: {e}")
            return Response().error(f"获取工具提示词列表失败: {str(e)}").to_dict()

    async def create_tool_prompt(self) -> Dict[str, Any]:
        """创建新工具提示词"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            is_valid, error_msg = await self.validate_required_fields(
                data, ["tool_name", "prompt"]
            )
            if not is_valid:
                return Response().error(error_msg).to_dict()

            # 从请求数据中获取参数
            tool_name = data["tool_name"]
            prompt = data["prompt"]
            description = data.get("description", "")

            # 创建工具提示词
            success = db_manager.create_tool_prompt(tool_name, prompt, description)
            if not success:
                return Response().error("工具提示词名称已存在").to_dict()

            # 重新加载提示词
            prompt_manager.load_all_prompts()

            return (
                Response()
                .ok(data={"tool_name": tool_name}, message="工具提示词创建成功")
                .to_dict()
            )
        except Exception as e:
            logger.error(f"创建工具提示词失败: {e}")
            return Response().error(f"创建工具提示词失败: {str(e)}").to_dict()

    async def update_tool_prompt(self) -> Dict[str, Any]:
        """更新工具提示词"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            tool_name = data.get("tool_name")
            if not tool_name:
                return Response().error("缺少工具名称").to_dict()

            # 检查工具提示词是否存在
            existing_prompt = db_manager.get_tool_prompt(tool_name)
            if not existing_prompt:
                return Response().error("工具提示词不存在").to_dict()

            # 准备更新参数
            prompt = data.get("prompt")
            description = data.get("description")

            # 更新工具提示词
            success = db_manager.update_tool_prompt(tool_name, prompt, description)
            if not success:
                return Response().error("工具提示词更新失败").to_dict()

            # 重新加载提示词
            prompt_manager.load_all_prompts()

            return Response().ok(message="工具提示词更新成功").to_dict()
        except Exception as e:
            logger.error(f"更新工具提示词失败: {e}")
            return Response().error(f"更新工具提示词失败: {str(e)}").to_dict()

    async def delete_tool_prompt(self) -> Dict[str, Any]:
        """删除工具提示词"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            tool_name = data.get("tool_name")
            if not tool_name:
                return Response().error("缺少工具名称").to_dict()

            # 删除工具提示词
            success = db_manager.delete_tool_prompt(tool_name)
            if not success:
                return Response().error("工具提示词删除失败").to_dict()

            # 重新加载提示词
            prompt_manager.load_all_prompts()

            return Response().ok(message="工具提示词删除成功").to_dict()
        except Exception as e:
            logger.error(f"删除工具提示词失败: {e}")
            return Response().error(f"删除工具提示词失败: {str(e)}").to_dict()
