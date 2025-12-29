"""Pipeline 上下文

提供 Pipeline 执行所需的上下文信息
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class PipelineContext:
    """Pipeline 上下文，包含执行 Pipeline 所需的所有信息"""

    # 配置信息
    config: Dict[str, Any]
    """NekoBot 配置"""

    # 平台管理器
    platform_manager: Any
    """平台管理器实例"""

    # 插件管理器
    plugin_manager: Any
    """插件管理器实例"""

    # LLM 管理器
    llm_manager: Any
    """LLM 管理器实例"""

    # 事件队列
    event_queue: Any
    """事件队列"""

    # 其他上下文数据
    extra: Dict[str, Any] = None
    """额外的上下文数据"""

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}

    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文数据"""
        return self.extra.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置上下文数据"""
        self.extra[key] = value
