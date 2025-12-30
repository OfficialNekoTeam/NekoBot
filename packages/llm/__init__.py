"""LLM Provider 模块

提供 LLM 服务提供商的抽象接口和具体实现
"""

from .base import BaseLLMProvider
from .register import (
    register_llm_provider,
    llm_provider_registry,
    llm_provider_cls_map,
    LLMProviderMetaData,
    LLMProviderType,
)
from .entities import LLMResponse, TokenUsage
from .context_manager import LLMContextManager

# 导入所有 LLM 提供商以自动注册
from .sources import (
    openai_provider,
    gemini_provider,
    glm_provider,
    openai_compatible_provider,
    claude_provider,
    deepseek_provider,
    dashscope_provider,
    moonshot_provider,
    zhipu_provider,
)

__all__ = [
    "BaseLLMProvider",
    "register_llm_provider",
    "llm_provider_registry",
    "llm_provider_cls_map",
    "LLMProviderMetaData",
    "LLMProviderType",
    "LLMResponse",
    "TokenUsage",
    "LLMContextManager",
]
