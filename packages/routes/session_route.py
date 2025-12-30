"""会话管理 API 路由

提供会话的获取、创建、删除、总结等功能
"""

from typing import Dict, Any
from loguru import logger

from .route import Route, Response, RouteContext
from ..core.database import get_db
from ..core.session_manager import SessionManager


class SessionRoute(Route):
    """会话管理路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.session_manager = SessionManager(get_db())
        self.routes = [
            ("/api/sessions", "GET", self.get_sessions),
            ("/api/sessions", "POST", self.create_session),
            ("/api/sessions/<session_id>", "GET", self.get_session),
            ("/api/sessions/<session_id>", "DELETE", self.delete_session),
            ("/api/sessions/<session_id>/summary", "PUT", self.update_summary),
        ]

    async def get_sessions(self) -> Dict[str, Any]:
        """获取所有会话"""
        try:
            user_id = self.request.args.get("user_id")
            platform_id = self.request.args.get("platform_id")

            if not user_id:
                return Response().error("缺少 user_id 参数").to_dict()

            sessions = self.session_manager.get_user_sessions(user_id, platform_id)
            return Response().ok(data={"sessions": sessions}).to_dict()
        except Exception as e:
            logger.error(f"获取会话列表失败: {e}")
            return Response().error(f"获取会话列表失败: {str(e)}").to_dict()

    async def create_session(self) -> Dict[str, Any]:
        """创建新会话"""
        try:
            user_id = self.request.args.get("user_id")
            platform_id = self.request.args.get("platform_id")
            summary = self.request.json.get("summary")
            metadata = self.request.json.get("metadata", {})

            if not user_id:
                return Response().error("缺少 user_id 参数").to_dict()

            session = self.session_manager.create_session(platform_id, user_id, summary, metadata)

            return Response().ok(data={"session_id": session.session_id, "messages": []}).to_dict()
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            return Response().error(f"创建会话失败: {str(e)}").to_dict()

    async def get_session(self) -> Dict[str, Any]:
        """获取单个会话详情"""
        try:
            session_id = self.request.path_params.get("session_id")

            if not session_id:
                return Response().error("缺少 session_id 参数").to_dict()

            session = self.session_manager.get_session(session_id)
            if not session:
                return Response().error("会话不存在").to_dict()

            return Response().ok(data=session.to_dict()).to_dict()
        except Exception as e:
            logger.error(f"获取会话详情失败: {e}")
            return Response().error(f"获取会话详情失败: {str(e)}").to_dict()

    async def delete_session(self) -> Dict[str, Any]:
        """删除会话"""
        try:
            session_id = self.request.path_params.get("session_id")

            if not session_id:
                return Response().error("缺少 session_id 参数").to_dict()

            success = self.session_manager.delete_session(session_id)

            if success:
                return Response().ok(message="会话已删除").to_dict()
            else:
                return Response().error("会话删除失败").to_dict()
        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            return Response().error(f"删除会话失败: {str(e)}").to_dict()

    async def update_summary(self) -> Dict[str, Any]:
        """更新会话总结"""
        try:
            session_id = self.request.path_params.get("session_id")
            summary = self.request.json.get("summary")

            if not session_id:
                return Response().error("缺少 session_id 参数").to_dict()

            success = self.session_manager.update_session_summary(session_id, summary)

            if success:
                return Response().ok(message="会话总结已更新").to_dict()
            else:
                return Response().error("更新会话总结失败").to_dict()
        except Exception as e:
            logger.error(f"更新会话总结失败: {e}")
            return Response().error(f"更新会话总结失败: {str(e)}").to_dict()
    async def get_context(self) -> Dict[str, Any]:
        """获取会话上下文"""
        try:
            session_id = self.request.path_params.get("session_id")
            limit = self.request.args.get("limit")

            if not session_id:
                return Response().error("缺少 session_id 参数").to_dict()

            context = self.session_manager.get_context(session_id, limit)

            return Response().ok(data={"context": context}).to_dict()
        except Exception as e:
            logger.error(f"获取会话上下文失败: {e}")
            return Response().error(f"获取会话上下文失败: {str(e)}").to_dict()
    async def get_stats(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        try:
            session_id = self.request.path_params.get("session_id")

            if not session_id:
                return Response().error("缺少 session_id 参数").to_dict()

            stats = self.session_manager.get_context_stats(session_id)

            return Response().ok(data=stats).to_dict()
        except Exception as e:
            logger.error(f"获取会话统计失败: {e}")
            return Response().error(f"获取会话统计失败: {str(e)}").to_dict()
    async def clear_context(self) -> Dict[str, Any]:
        """清除会话上下文"""
        try:
            session_id = self.request.path_params.get("session_id")

            if not session_id:
                return Response().error("缺少 session_id 参数").to_dict()

            self.session_manager.clear_context(session_id)

            return Response().ok(message="会话上下文已清除").to_dict()
        except Exception as e:
            logger.error(f"清除会话上下文失败: {e}")
            return Response().error(f"清除会话上下文失败: {str(e)}").to_dict()
