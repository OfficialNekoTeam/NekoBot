"""结果装饰阶段

装饰响应结果
"""

from typing import AsyncGenerator, Optional
from loguru import logger

from .stage import Stage, register_stage
from .context import PipelineContext


@register_stage
class ResultDecorateStage(Stage):
    """结果装饰阶段"""

    async def initialize(self, ctx: PipelineContext) -> None:
        """初始化阶段"""
        logger.debug("ResultDecorateStage 初始化")

    async def process(
        self, event: dict, ctx: PipelineContext
    ) -> Optional[AsyncGenerator[None, None]]:
        """装饰响应结果

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

        # 获取装饰配置
        config = ctx.config.get("result_decorate", {})
        enabled = config.get("enabled", False)
        prefix = config.get("prefix", "")
        suffix = config.get("suffix", "")

        if not enabled:
            return None

        # 装饰响应结果
        decorated_response = f"{prefix}{response}{suffix}"
        event["_response"] = decorated_response

        return None
