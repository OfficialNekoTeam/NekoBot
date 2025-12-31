"""Pipeline Stage 基类

定义 Pipeline 的某个阶段
"""

import abc
from typing import AsyncGenerator, Optional, Type, Dict
from loguru import logger
from .context import PipelineContext


# 全局 Stage 注册表
_stage_registry: Dict[str, Type["Stage"]] = {}
"""维护已注册的 Stage 类，按类名索引"""


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
    stage_name = stage_cls.__name__

    if stage_name in _stage_registry:
        logger.warning(
            f"Stage {stage_name} 已存在，将被覆盖。"
        )

    _stage_registry[stage_name] = stage_cls

    return stage_cls


def get_stage(stage_name: str) -> Optional[Type["Stage"]]:
    """获取已注册的 Stage 类

    Args:
        stage_name: Stage 类名

    Returns:
        Stage 类，如果未找到则返回 None
    """
    return _stage_registry.get(stage_name)


def list_stages() -> Dict[str, Type["Stage"]]:
    """列出所有已注册的 Stage

    Returns:
        Stage 名称到类的映射
    """
    return _stage_registry.copy()


def unregister_stage(stage_name: str) -> bool:
    """注销 Stage

    Args:
        stage_name: Stage 类名

    Returns:
        是否成功注销
    """
    if stage_name in _stage_registry:
        del _stage_registry[stage_name]
        return True
    return False
