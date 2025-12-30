"""平台适配器系统"""

from .base import BasePlatform
from .metadata import PlatformMetadata
from .register import register_platform_adapter, get_platform_adapter, get_all_platforms
from .manager import PlatformManager
# 导入平台适配器以触发注册
from .sources import aiocqhttp
from .sources import discord
from .sources import telegram

__all__ = [
    "BasePlatform",
    "PlatformMetadata",
    "register_platform_adapter",
    "get_platform_adapter",
    "get_all_platforms",
    "PlatformManager",
    "aiocqhttp",
    "discord",
    "telegram",
]
