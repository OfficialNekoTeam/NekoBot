"""NekoBot Pipeline 系统

实现洋葱模型，支持前置/后置处理
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
from enum import Enum
from loguru import logger

from ..types import MessageEvent


# ============== Pipeline 阶段基类 ==============

class BaseStage(ABC):
    """Pipeline 阶段基类

    所有 Pipeline Stage 都应该继承此类
    """

    @property
    def name(self) -> str:
        """阶段名称"""
        return self.__class__.__name__

    async def initialize(self, context: "PipelineContext") -> None:
        """初始化阶段

        在 Pipeline 启动时调用，用于初始化资源
        """
        pass

    @abstractmethod
    async def process(
        self,
        event: MessageEvent
    ) -> AsyncGenerator[None, None]:
        """处理事件

        使用异步生成器实现洋葱模型:
        - yield 之前: 前置处理
        - yield: 暂停，执行后续阶段
        - yield 之后: 后置处理

        示例:
        ```python
        async def process(self, event: MessageEvent):
            # 前置处理
            logger.debug(f"Before: {event.message}")

            yield  # 暂停，执行后续阶段

            # 后置处理
            logger.debug(f"After: {event.message}")
        ```
        """
        yield


# ============== 简单阶段基类 ==============

class SimpleStage(BaseStage):
    """简单阶段基类

    用于不需要前置/后置处理的阶段
    """

    @abstractmethod
    async def handle(self, event: MessageEvent) -> None:
        """实际的处理逻辑

        子类实现此方法来处理事件
        """
        pass

    async def process(self, event: MessageEvent) -> AsyncGenerator[None, None]:
        """处理事件（不使用 yield）"""
        await self.handle(event)
        yield  # 保持生成器接口一致性


# ============== Pipeline 上下文 ==============

@dataclass
class PipelineContext:
    """Pipeline 上下文

    包含 Pipeline 执行所需的所有资源
    """
    agent_executor: "AgentExecutor"  # type: ignore
    platform_manager: "PlatformManager"  # type: ignore
    plugin_manager: "PluginManager"  # type: ignore
    conversation_manager: "ConversationManager"  # type: ignore
    config_manager: "ConfigManager"  # type: ignore
    event_bus: "EventBus"  # type: ignore
    metadata: dict[str, Any] = field(default_factory=dict)


# ============== Pipeline 阶段优先级 ==============

@dataclass
class StagePriority:
    """阶段优先级

    数值越小，优先级越高（越早执行）
    """
    WAKING_CHECK = 0
    WHITELIST_CHECK = 100
    SESSION_STATUS_CHECK = 200
    CONTENT_SAFETY_CHECK = 300
    COMMAND_PARSE = 400
    PLUGIN_DISPATCH = 500
    AGENT_PROCESS = 600
    RATE_LIMIT = 700
    RESULT_DECORATE = 800
    RESPONSE = 900


# ============== Pipeline 调度器 ==============

class PipelineScheduler:
    """Pipeline 调度器

    实现洋葱模型的调度逻辑
    """

    def __init__(self, context: PipelineContext, stages: list[type[BaseStage]]):
        """初始化调度器

        Args:
            context: Pipeline 上下文
            stages: 阶段类列表
        """
        self.context = context
        self.stages: list[BaseStage] = []

        # 按优先级排序并实例化阶段
        sorted_stages = sorted(
            stages,
            key=lambda s: self._get_stage_priority(s)
        )

        for stage_cls in sorted_stages:
            stage = stage_cls()
            self.stages.append(stage)

    def _get_stage_priority(self, stage_cls: type[BaseStage]) -> int:
        """获取阶段优先级"""
        # 尝试从类属性获取优先级
        if hasattr(stage_cls, 'priority'):
            return stage_cls.priority

        # 从 StagePriority 枚举获取
        priority_name = stage_cls.__name__.upper()
        if hasattr(StagePriority, priority_name):
            return getattr(StagePriority, priority_name)

        # 默认最低优先级
        return 999

    async def initialize(self) -> None:
        """初始化所有阶段"""
        for stage in self.stages:
            await stage.initialize(self.context)

    async def execute(self, event: MessageEvent) -> None:
        """执行 Pipeline

        Args:
            event: 消息事件
        """
        await self._process_stages(event, from_stage=0)

    async def _process_stages(
        self,
        event: MessageEvent,
        from_stage: int = 0
    ) -> None:
        """递归执行阶段（洋葱模型）

        Args:
            event: 消息事件
            from_stage: 起始阶段索引
        """
        for i in range(from_stage, len(self.stages)):
            stage = self.stages[i]

            # 检查事件是否被终止
            if event.is_stopped():
                logger.debug(f"Event stopped at stage: {stage.name}")
                break

            # 执行阶段
            try:
                coroutine = stage.process(event)

                if hasattr(coroutine, '__aiter__'):
                    # 异步生成器 - 洋葱模型
                    async for _ in coroutine:
                        # yield 点 - 执行后续阶段
                        if event.is_stopped():
                            logger.debug(f"Event stopped after yield at: {stage.name}")
                            break

                        # 递归执行后续阶段
                        await self._process_stages(event, i + 1)

                        # 返回到 yield 点 - 执行后置处理
                        if event.is_stopped():
                            break
                else:
                    # 普通 async 函数 - 直接执行
                    await coroutine

                    if event.is_stopped():
                        break

            except Exception as e:
                logger.error(f"Error in stage {stage.name}: {e}")
                # 阶段错误不应该中断整个 Pipeline
                # 继续执行下一个阶段
                continue

    def add_stage(self, stage: BaseStage, priority: int | None = None) -> None:
        """动态添加阶段"""
        if priority is None:
            priority = self._get_stage_priority(type(stage))

        # 找到插入位置
        insert_index = 0
        for i, s in enumerate(self.stages):
            s_priority = self._get_stage_priority(type(s))
            if priority < s_priority:
                insert_index = i
                break
            insert_index = i + 1

        self.stages.insert(insert_index, stage)

    def remove_stage(self, stage_name: str) -> bool:
        """移除阶段"""
        for i, stage in enumerate(self.stages):
            if stage.name == stage_name:
                del self.stages[i]
                return True
        return False

    def list_stages(self) -> list[str]:
        """列出所有阶段名称"""
        return [s.name for s in self.stages]

    def __len__(self) -> int:
        return len(self.stages)


# ============== 阶段装饰器 ==============

def register_stage(priority: int = 999):
    """注册阶段装饰器

    使用方式:
    ```python
    @register_stage(priority=500)
    class MyCustomStage(SimpleStage):
        async def handle(self, event: MessageEvent):
            print(f"Processing: {event.message}")
    ```
    """
    def decorator(cls: type[BaseStage]) -> type[BaseStage]:
        cls.priority = priority
        return cls
    return decorator


# ============== 导出 ==============

__all__ = [
    "BaseStage",
    "SimpleStage",
    "PipelineContext",
    "PipelineScheduler",
    "StagePriority",
    "register_stage",
]
