"""响应阶段

发送响应
"""

from typing import AsyncGenerator, Optional
from loguru import logger

from .stage import Stage, register_stage
from .context import PipelineContext


@register_stage
class RespondStage(Stage):
    """响应阶段"""

    async def initialize(self, ctx: PipelineContext) -> None:
        """初始化阶段"""
        logger.debug("RespondStage 初始化")

    async def process(
        self, event: dict, ctx: PipelineContext
    ) -> Optional[AsyncGenerator[None, None]]:
        """发送响应

        Args:
            event: 事件数据
            ctx: Pipeline 上下文

        Returns:
            None
        """
        # 获取响应结果
        response = event.get("_response", "")

        if not response:
            return None

        # 发送响应
        platform_id = event.get("platform_id", "onebot")
        message_type = event.get("message_type", "")
        target_id = None

        if message_type == "private":
            target_id = event.get("user_id")
        elif message_type == "group":
            target_id = event.get("group_id")

        if target_id:
            chat_type = "群聊" if message_type == "group" else "私聊"
            group_id = event.get("group_id", "N/A")
            group_name = event.get("group_name")
            group_disp = (
                f"{group_name}({group_id})"
                if (message_type == "group" and group_id)
                else ""
            )
            bot_id = event.get("self_id")
            bot_disp = f"猫猫({bot_id})" if bot_id else "猫猫"

            def _trim_text(t: str, n: int = 120) -> str:
                s = " ".join(t.splitlines())
                return s if len(s) <= n else s[: n - 3] + "..."

            log_text = _trim_text(response)
            if message_type == "group":
                logger.info(
                    f"猫猫 | 发送 -> {chat_type} [{group_disp}] [{bot_disp}] {log_text}"
                )
            else:
                logger.info(f"猫猫 | 发送 -> {chat_type} [{bot_disp}] {log_text}")
            await ctx.platform_manager.send_message(
                platform_id, message_type, target_id, response
            )

        return None
