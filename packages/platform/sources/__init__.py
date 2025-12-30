"""平台适配器源码模块"""

# 导入所有平台适配器以自动注册
from . import (
    aiocqhttp,
    discord,
    telegram,
    lark,
    kook,
    qqchannel,
)

__all__ = []
