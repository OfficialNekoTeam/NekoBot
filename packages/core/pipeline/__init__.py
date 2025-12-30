"""Pipeline 系统

提供消息处理流水线功能，支持洋葱模型
"""

from .scheduler import PipelineScheduler
from .stage import Stage
from .context import PipelineContext
from .whitelist_check_stage import WhitelistCheckStage
from .content_safety_check_stage import ContentSafetyCheckStage
from .rate_limit_stage import RateLimitStage
from .session_status_check_stage import SessionStatusCheckStage
from .waking_check_stage import WakingCheckStage
from .process_stage import ProcessStage
from .result_decorate_stage import ResultDecorateStage
from .respond_stage import RespondStage
from ...llm import (
    ContextManager,
    ContextConfig,
    ContextCompressionStrategy,
    MessageRecord,
    llm_provider_cls_map,
    LLMProviderMetaData,
)

# 导出各个 stage 模块，支持外部导入
from . import (
    process_stage,
    whitelist_check_stage,
    content_safety_check_stage,
    rate_limit_stage,
    session_status_check_stage,
    waking_check_stage,
    result_decorate_stage,
    respond_stage,
)

__all__ = [
    "PipelineScheduler",
    "Stage",
    "PipelineContext",
    "WhitelistCheckStage",
    "ContentSafetyCheckStage",
    "RateLimitStage",
    "SessionStatusCheckStage",
    "WakingCheckStage",
    "ProcessStage",
    "ResultDecorateStage",
    "RespondStage",
]
