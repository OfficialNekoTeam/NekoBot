"""Pipeline 调度器

负责调度各个阶段的执行
"""

import asyncio
from typing import List, Optional
from loguru import logger

from .stage import Stage
from .context import PipelineContext


class PipelineScheduler:
    """管道调度器，负责调度各个阶段的执行"""

    def __init__(self, stages: List[Stage]):
        """初始化调度器

        Args:
            stages: 阶段列表
        """
        self.stages = stages
        self._initialized = False

    async def execute(self, event: dict, ctx: PipelineContext) -> None:
        """执行所有阶段

        Args:
            event: 事件数据
            ctx: Pipeline 上下文
        """
        # 首次执行时初始化所有阶段
        if not self._initialized:
            for stage in self.stages:
                try:
                    await stage.initialize(ctx)
                except Exception as e:
                    logger.error(f"阶段 {stage.__class__.__name__} 初始化失败: {e}")
            self._initialized = True

        for stage in self.stages:
            try:
                # 处理事件
                coroutine = await stage.process(event, ctx)

                if coroutine is None:
                    # 阶段返回 None，继续下一个阶段
                    continue

                if asyncio.iscoroutine(coroutine):
                    # 普通协程，等待完成
                    await coroutine
                else:
                    # 异步生成器（洋葱模型）
                    async for _ in coroutine:
                        # 检查事件是否被停止
                        if self._is_event_stopped(event):
                            logger.debug("事件已被停止，终止 Pipeline 执行")
                            return
                        # 递归处理后续阶段
                        await self._process_stages(
                            event, ctx, from_stage=self.stages.index(stage) + 1
                        )

                        # 再次检查事件是否被停止
                        if self._is_event_stopped(event):
                            return

            except Exception as e:
                logger.error(f"阶段 {stage.__class__.__name__} 执行失败: {e}")
                # 继续执行下一个阶段

    async def _process_stages(
        self, event: dict, ctx: PipelineContext, from_stage: int = 0
    ) -> None:
        """依次执行各个阶段 - 洋葱模型实现

        Args:
            event: 事件数据
            ctx: Pipeline 上下文
            from_stage: 起始阶段索引
        """
        for i in range(from_stage, len(self.stages)):
            stage = self.stages[i]
            coroutine = await stage.process(event, ctx)

            if coroutine is None:
                continue

            if asyncio.iscoroutine(coroutine):
                await coroutine
            else:
                # 异步生成器
                async for _ in coroutine:
                    if self._is_event_stopped(event):
                        return
                    # 递归处理后续阶段
                    await self._process_stages(event, ctx, i + 1)
                    if self._is_event_stopped(event):
                        return

    def _is_event_stopped(self, event: dict) -> bool:
        """检查事件是否被停止

        Args:
            event: 事件数据

        Returns:
            是否被停止
        """
        return event.get("_stopped", False)


def register_stage(stage_cls: type) -> type:
    """注册 Stage 的装饰器

    Args:
        stage_cls: Stage 类

    Returns:
        Stage 类
    """
    return stage_cls
