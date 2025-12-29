"""白名单检查阶段

检查群聊/私聊白名单
"""

from typing import AsyncGenerator, Optional
from loguru import logger

from .stage import Stage, register_stage
from .context import PipelineContext


@register_stage
class WhitelistCheckStage(Stage):
    """白名单检查阶段"""

    async def initialize(self, ctx: PipelineContext) -> None:
        """初始化阶段"""
        logger.debug("WhitelistCheckStage 初始化")

    async def process(
        self, event: dict, ctx: PipelineContext
    ) -> Optional[AsyncGenerator[None, None]]:
        """检查白名单

        Args:
            event: 事件数据
            ctx: Pipeline 上下文

        Returns:
            None
        """
        post_type = event.get("post_type")

        if post_type != "message":
            return None

        message_type = event.get("message_type", "")
        user_id = event.get("user_id", "")
        group_id = event.get("group_id", "")

        # 获取白名单配置
        config = ctx.config.get("whitelist", {})
        enabled = config.get("enabled", False)

        if not enabled:
            # 白名单未启用，允许所有消息
            return None

        # 检查私聊白名单
        if message_type == "private":
            private_whitelist = config.get("private", [])
            if private_whitelist and str(user_id) not in private_whitelist:
                logger.debug(f"私聊用户 {user_id} 不在白名单中，忽略消息")
                event["_stopped"] = True
                return None

        # 检查群聊白名单
        elif message_type == "group":
            group_whitelist = config.get("group", [])
            if group_whitelist and str(group_id) not in group_whitelist:
                logger.debug(f"群聊 {group_id} 不在白名单中，忽略消息")
                event["_stopped"] = True
                return None

        return None
