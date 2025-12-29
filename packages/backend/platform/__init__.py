"""平台适配器系统"""

from .base import BasePlatform
from .metadata import PlatformMetadata
from .register import register_platform_adapter, get_platform_adapter, get_all_platforms
from .manager import PlatformManager

__all__ = [
    "BasePlatform",
    "PlatformMetadata",
    "register_platform_adapter",
    "get_platform_adapter",
    "get_all_platforms",
    "PlatformManager",
]
