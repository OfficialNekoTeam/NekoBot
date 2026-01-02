"""NekoBot Pipeline 系统

实现洋葱模型，支持前置/后置处理
"""

from .scheduler_new import (
    BaseStage,
    SimpleStage,
    PipelineContext,
    PipelineScheduler,
    StagePriority,
    register_stage,
)

__all__ = [
    "BaseStage",
    "SimpleStage",
    "PipelineContext",
    "PipelineScheduler",
    "StagePriority",
    "register_stage",
]
