"""限流检查阶段

检查用户/群组的消息频率
"""

import time
from typing import AsyncGenerator, Optional, Dict
from collections import defaultdict
from loguru import logger

from .stage import Stage, register_stage
from .context import PipelineContext


@register_stage
class RateLimitStage(Stage):
    """限流检查阶段"""

    def __init__(self):
        """初始化限流检查阶段"""
        self.message_timestamps: Dict[str, list] = defaultdict(list)

    async def initialize(self, ctx: PipelineContext) -> None:
        """初始化阶段"""
        logger.debug("RateLimitStage 初始化")

    async def process(
        self, event: dict, ctx: PipelineContext
    ) -> Optional[AsyncGenerator[None, None]]:
        """检查限流

        Args:
            event: 事件数据
            ctx: Pipeline 上下文

        Returns:
            None
        """
        post_type = event.get("post_type")

        if post_type != "message":
            return None

        # 获取限流配置
        config = ctx.config.get("rate_limit", {})
        enabled = config.get("enabled", False)
        max_messages = config.get("max_messages", 10)
        time_window = config.get("time_window", 60)  # 秒

        if not enabled:
            return None

        # 获取用户/群组 ID
        message_type = event.get("message_type", "")
        user_id = event.get("user_id", "")
        group_id = event.get("group_id", "")

        if message_type == "private":
            key = f"private:{user_id}"
        elif message_type == "group":
            key = f"group:{group_id}"
        else:
            return None

        # 获取当前时间戳
        current_time = time.time()

        # 清理过期的消息时间戳
        self.message_timestamps[key] = [
            ts for ts in self.message_timestamps[key] if current_time - ts < time_window
        ]

        # 检查是否超过限流阈值
        if len(self.message_timestamps[key]) >= max_messages:
            logger.warning(f"用户/群组 {key} 超过限流阈值")
            event["_stopped"] = True
            return None

        # 记录当前消息时间戳
        self.message_timestamps[key].append(current_time)

        return None
