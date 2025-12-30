"""Pipeline 调度器

支持洋葱模型的流水线调度器，提供前置/后置处理能力
"""

import asyncio
from typing import List, Optional, AsyncGenerator
from loguru import logger

from .stage import Stage
from .context import PipelineContext
from .event_stopper import EventStopper


class PipelineScheduler:
    """管道调度器，支持洋葱模型的事件处理
    
    洋葱模型特点：
    - 支持 AsyncGenerator 实现 yield 暂停点
    - yield 之前是前置处理
    - yield 之后是后置处理
    - 支持事件传播控制
    """

    def __init__(self, stages: List[Stage], context: Optional[PipelineContext] = None):
        """初始化调度器
        
        Args:
            stages: 阶段列表（已按顺序排序）
            context: Pipeline 上下文
        """
        self.stages = stages
        self.context = context
        self._initialized = False

    async def execute(self, event: dict, ctx: Optional[PipelineContext] = None) -> None:
        """执行所有阶段（洋葱模型）
        
        Args:
            event: 事件数据
            ctx: Pipeline 上下文（如果提供，覆盖构造时的 context）
        """
        # 使用提供的 context 或构造时的 context
        pipeline_ctx = ctx or self.context
        
        # 首次执行时初始化所有阶段
        if not self._initialized:
            for stage in self.stages:
                try:
                    await stage.initialize(pipeline_ctx)
                    logger.debug(f"阶段 {stage.__class__.__name__} 已初始化")
                except Exception as e:
                    logger.error(f"阶段 {stage.__class__.__name__} 初始化失败: {e}")
            self._initialized = True

        # 检查事件中是否已有 EventStopper
        event_stopper = event.get("_stopper")
        if event_stopper is None:
            event["_stopper"] = EventStopper()

        try:
            # 开始执行流水线（从第 0 个阶段开始）
            await self._process_stages(event, pipeline_ctx, from_stage=0)
        except Exception as e:
            logger.error(f"流水线执行失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def _process_stages(
        self, event: dict, ctx: PipelineContext, from_stage: int = 0
    ) -> None:
        """依次执行各个阶段 - 洋葱模型实现
        
        Args:
            event: 事件数据
            ctx: Pipeline 上下文
            from_stage: 起始阶段索引
        """
        event_stopper = event.get("_stopper")
        
        for i in range(from_stage, len(self.stages)):
            # 检查事件是否已停止
            if event_stopper and event_stopper.is_stopped():
                logger.debug(
                    f"事件已停止: {event_stopper.reason}，终止流水线执行"
                )
                return
            
            stage = self.stages[i]
            
            try:
                # 调用阶段的 process 方法
                result = await stage.process(event, ctx)
                
                if result is None:
                    # 阶段返回 None，继续下一个阶段
                    logger.debug(f"阶段 {stage.__class__.__name__} 返回 None，继续下一个阶段")
                    continue
                
                # 检查是否是异步生成器（洋葱模型）
                if isinstance(result, AsyncGenerator):
                    logger.debug(f"阶段 {stage.__class__.__name__} 返回 AsyncGenerator，开始洋葱模型处理")
                    async for _ in result:
                        # 暂停点：前置处理已完成
                        
                        # 再次检查事件是否已停止
                        if event_stopper and event_stopper.is_stopped():
                            logger.debug(
                                f"事件已停止（前置处理后）: {event_stopper.reason}"
                            )
                            return
                        
                        # 递归处理后续阶段
                        await self._process_stages(event, ctx, i + 1)
                        
                        # 暂停点返回：后续阶段已完成，执行后置处理
                        
                        # 再次检查事件是否已停止
                        if event_stopper and event_stopper.is_stopped():
                            logger.debug(
                                f"事件已停止（后置处理后）: {event_stopper.reason}"
                            )
                            return
                else:
                    # 普通协程，等待完成
                    await result
                    logger.debug(f"阶段 {stage.__class__.__name__} 已完成")
                
                # 检查事件是否已停止
                if event_stopper and event_stopper.is_stopped():
                    logger.debug(
                        f"阶段 {stage.__class__.__name__} 处理后事件已停止: {event_stopper.reason}"
                    )
                    return
                
            except Exception as e:
                logger.error(f"阶段 {stage.__class__.__name__} 执行失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # 继续执行下一个阶段

    def stop_event(self, event: dict, reason: str = "") -> None:
        """停止事件传播
        
        Args:
            event: 事件数据
            reason: 停止原因
        """
        event_stopper = event.get("_stopper")
        if event_stopper:
            event_stopper.stop(reason)
            logger.debug(f"事件传播已停止: {reason}")

    def reset_event(self, event: dict) -> None:
        """重置事件停止状态
        
        Args:
            event: 事件数据
        """
        event_stopper = event.get("_stopper")
        if event_stopper:
            event_stopper.reset()
            logger.debug("事件停止状态已重置")

    def is_event_stopped(self, event: dict) -> bool:
        """检查事件是否已停止
        
        Args:
            event: 事件数据
            
        Returns:
            是否已停止
        """
        event_stopper = event.get("_stopper")
        if event_stopper:
            return event_stopper.is_stopped()
        return False

    async def initialize_stages(self, ctx: PipelineContext) -> None:
        """初始化所有阶段
        
        Args:
            ctx: Pipeline 上下文
        """
        for stage in self.stages:
            try:
                await stage.initialize(ctx)
                logger.debug(f"阶段 {stage.__class__.__name__} 已初始化")
            except Exception as e:
                logger.error(f"阶段 {stage.__class__.__name__} 初始化失败: {e}")
        self._initialized = True

    def get_stages(self) -> List[Stage]:
        """获取所有阶段
        
        Returns:
            阶段列表
        """
        return self.stages.copy()

    def get_stage_names(self) -> List[str]:
        """获取所有阶段名称
        
        Returns:
            阶段名称列表
        """
        return [stage.__class__.__name__ for stage in self.stages]
