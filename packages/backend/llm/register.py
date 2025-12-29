"""LLM Provider 注册模块

提供 LLM 服务提供商的装饰器注册功能
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Any
from loguru import logger


class LLMProviderType(Enum):
    """LLM 服务提供商类型"""

    CHAT_COMPLETION = "chat_completion"
    EMBEDDING = "embedding"
    RERANK = "rerank"


@dataclass
class LLMProviderMetaData:
    """LLM 服务提供商元数据"""

    id: str
    model: Optional[str]
    type: str
    desc: str
    provider_type: LLMProviderType
    cls_type: type
    default_config_tmpl: Optional[dict] = None
    provider_display_name: Optional[str] = None


# 维护通过装饰器注册的 Provider
llm_provider_registry: list[LLMProviderMetaData] = []
# 维护 Provider 类型名称和 ProviderMetadata 的映射
llm_provider_cls_map: dict[str, LLMProviderMetaData] = {}


def register_llm_provider(
    provider_type_name: str,
    desc: str,
    provider_type: LLMProviderType = LLMProviderType.CHAT_COMPLETION,
    default_config_tmpl: Optional[dict] = None,
    provider_display_name: Optional[str] = None,
) -> Callable[[type], type]:
    """用于注册 LLM 服务提供商的带参装饰器

    Args:
        provider_type_name: 服务提供商类型名称
        desc: 服务提供商描述
        provider_type: 服务提供商类型
        default_config_tmpl: 默认配置模板
        provider_display_name: 服务提供商显示名称

    Returns:
        装饰器函数

    Raises:
        ValueError: 如果服务提供商类型名称已注册
    """

    def decorator(cls: type) -> type:
        if provider_type_name in llm_provider_cls_map:
            raise ValueError(
                f"检测到 LLM 服务提供商 {provider_type_name} 已经注册，可能发生了服务提供商类型命名冲突。"
            )

        # 添加必备选项
        if default_config_tmpl:
            if "type" not in default_config_tmpl:
                default_config_tmpl["type"] = provider_type_name
            if "enable" not in default_config_tmpl:
                default_config_tmpl["enable"] = False
            if "id" not in default_config_tmpl:
                default_config_tmpl["id"] = provider_type_name

        pm = LLMProviderMetaData(
            id="default",  # 实例化时会被替换
            model=None,
            type=provider_type_name,
            desc=desc,
            provider_type=provider_type,
            cls_type=cls,
            default_config_tmpl=default_config_tmpl,
            provider_display_name=provider_display_name,
        )
        llm_provider_registry.append(pm)
        llm_provider_cls_map[provider_type_name] = pm
        logger.debug(f"LLM 服务提供商 {provider_type_name} 已注册")
        return cls

    return decorator
