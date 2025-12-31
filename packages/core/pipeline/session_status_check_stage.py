"""会话状态检查阶段

检查会话是否启用
"""

from typing import AsyncGenerator, Optional
from loguru import logger

from .stage import Stage, register_stage
from .context import PipelineContext


@register_stage
class SessionStatusCheckStage(Stage):
    """会话状态检查阶段"""

    async def initialize(self, ctx: PipelineContext) -> None:
        """初始化阶段"""

    async def process(
        self, event: dict, ctx: PipelineContext
    ) -> Optional[AsyncGenerator[None, None]]:
        """检查会话状态

        Args:
            event: 事件数据
            ctx: Pipeline 上下文

        Returns:
            None
        """
        post_type = event.get("post_type")

        if post_type != "message":
            return None

        # 获取会话配置
        config = ctx.config.get("session", {})
        enabled = config.get("enabled", False)

        if not enabled:
            # 会话功能未启用，允许所有消息
            return None

        # 获取会话 ID
        message_type = event.get("message_type", "")
        user_id = event.get("user_id", "")
        group_id = event.get("group_id", "")

        if message_type == "private":
            session_id = f"private:{user_id}"
        elif message_type == "group":
            session_id = f"group:{group_id}"
        else:
            return None

        # 检查会话是否启用
        enabled_sessions = config.get("enabled_sessions", [])
        if enabled_sessions and session_id not in enabled_sessions:
            logger.debug(f"会话 {session_id} 未启用，忽略消息")
            event["_stopped"] = True
            return None

        return None
