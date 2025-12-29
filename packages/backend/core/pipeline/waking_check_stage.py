"""唤醒检查阶段

检查唤醒前缀
"""

from typing import AsyncGenerator, Optional
from loguru import logger

from .stage import Stage, register_stage
from .context import PipelineContext


@register_stage
class WakingCheckStage(Stage):
    """唤醒检查阶段"""

    async def initialize(self, ctx: PipelineContext) -> None:
        """初始化阶段"""
        logger.debug("WakingCheckStage 初始化")

    async def process(
        self, event: dict, ctx: PipelineContext
    ) -> Optional[AsyncGenerator[None, None]]:
        """检查唤醒前缀

        Args:
            event: 事件数据
            ctx: Pipeline 上下文

        Returns:
            None
        """
        post_type = event.get("post_type")

        if post_type != "message":
            return None

        # 获取唤醒配置
        config = ctx.config.get("waking", {})
        enabled = config.get("enabled", False)
        prefixes = config.get("prefixes", [])

        if not enabled or not prefixes:
            # 唤醒功能未启用，允许所有消息
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

        # 检查是否以唤醒前缀开头
        if not any(text.startswith(prefix) for prefix in prefixes):
            logger.debug(f"消息不包含唤醒前缀，忽略消息")
            event["_stopped"] = True
            return None

        return None
