"""内容安全检查阶段

检查消息内容是否包含敏感词
"""

from typing import AsyncGenerator, Optional
from loguru import logger

from .stage import Stage, register_stage
from .context import PipelineContext


@register_stage
class ContentSafetyCheckStage(Stage):
    """内容安全检查阶段"""

    async def initialize(self, ctx: PipelineContext) -> None:
        """初始化阶段"""

    async def process(
        self, event: dict, ctx: PipelineContext
    ) -> Optional[AsyncGenerator[None, None]]:
        """检查内容安全

        Args:
            event: 事件数据
            ctx: Pipeline 上下文

        Returns:
            None
        """
        post_type = event.get("post_type")

        if post_type != "message":
            return None

        # 获取消息内容
        message = event.get("message", "")
        if isinstance(message, list):
            text = ""
            for seg in message:
                if seg.get("type") == "text":
                    text += seg.get("data", {}).get("text", "")
        elif isinstance(message, str):
            text = message
        else:
            text = ""

        # 获取敏感词配置
        config = ctx.config.get("content_safety", {})
        enabled = config.get("enabled", False)
        sensitive_words = config.get("sensitive_words", [])

        if not enabled or not sensitive_words:
            return None

        # 检查是否包含敏感词
        for word in sensitive_words:
            if word.lower() in text.lower():
                logger.warning(f"消息包含敏感词: {word}")
                event["_stopped"] = True
                return None

        return None
