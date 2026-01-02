"""NekoBot 配置管理

提供配置变更监听和持久化功能
"""

from .manager import (
    ConfigChangeType,
    ConfigChangeEvent,
    ConfigWatcher,
    ConfigManager,
    get_config_manager,
    config,
)

__all__ = [
    "ConfigChangeType",
    "ConfigChangeEvent",
    "ConfigWatcher",
    "ConfigManager",
    "get_config_manager",
    "config",
]
