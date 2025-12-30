"""会话总结阶段

定期对活跃会话进行总结
"""

from typing import AsyncGenerator, Optional
from loguru import logger
from .stage import Stage, register_stage
from .context import PipelineContext
from ..config import load_config


@register_stage
class SessionSummaryStage(Stage):
    """会话总结阶段"""

    async def initialize(self, ctx: PipelineContext) -> None:
        """初始化阶段"""
        logger.debug("SessionSummaryStage 初始化")
        self.session_manager = ctx.session_manager

    async def process(
        self, event: dict, ctx: PipelineContext
    ) -> Optional[AsyncGenerator[None, None]]:
        """处理消息事件，触发会话总结"""
        post_type = event.get("post_type")

        if post_type == "message":
            await self._process_message(event, ctx)
        else:
            return None

    async def _process_message(self, event: dict, ctx: PipelineContext) -> None:
        """处理消息事件"""
        message_type = event.get("message_type", "private")
        user_id = event.get("user_id", "unknown")
        group_id = event.get("group_id", "private")

        # 只在群聊消息后触发总结
        if message_type == "group":
            session_id = f"{group_id}:{user_id}"

            # 获取配置
            config = load_config()
            session_config = config.get("session_summary", {})
            enabled = session_config.get("enabled", False)
            message_threshold = session_config.get("message_threshold", 10)

            if not enabled:
                return

            # 获取会话消息数量
            messages = self.session_manager.get_session_messages(session_id)
            user_messages = [m for m in messages if m["role"] == "user"]

            # 如果消息数量达到阈值，触发总结
            if len(user_messages) >= message_threshold:
                try:
                    logger.info(f"触发会话总结: {session_id}, 消息数: {len(user_messages)}")
                    await self._summarize_session(session_id, user_messages, session_config)
                except Exception as e:
                    logger.error(f"会话总结失败: {e}")

    async def _summarize_session(
        self,
        session_id: str,
        messages: list,
        session_config: dict
    ) -> None:
        """对会话进行总结"""
        # 提取用户消息内容
        "\n".join([m["content"] for m in messages if m["role"] == "user"])

        # 这里可以调用 LLM 来生成总结
        # 暂时简单返回消息数量
        summary = f"本次会话包含 {len(messages)} 条消息"

        # 更新会话总结
        await self.session_manager.update_session_summary(session_id, summary)

        logger.info(f"会话总结完成: {session_id}")
