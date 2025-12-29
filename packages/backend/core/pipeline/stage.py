"""Pipeline Stage 基类

定义 Pipeline 的某个阶段
"""

import abc
from typing import AsyncGenerator, Optional
from .context import PipelineContext


class Stage(abc.ABC):
    """描述一个 Pipeline 的某个阶段"""

    @abc.abstractmethod
    async def initialize(self, ctx: PipelineContext) -> None:
        """初始化阶段

        Args:
            ctx: Pipeline 上下文
        """
        pass

    @abc.abstractmethod
    async def process(
        self, event: dict, ctx: PipelineContext
    ) -> Optional[AsyncGenerator[None, None]]:
        """处理事件，返回 None 或异步生成器

        Args:
            event: 事件数据
            ctx: Pipeline 上下文

        Returns:
            None 或异步生成器（用于洋葱模型）
        """
        pass


def register_stage(stage_cls: type) -> type:
    """注册 Stage 的装饰器

    Args:
        stage_cls: Stage 类

    Returns:
        Stage 类
    """
    return stage_cls
