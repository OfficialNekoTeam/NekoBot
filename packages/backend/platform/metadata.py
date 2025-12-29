"""平台适配器元数据"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PlatformMetadata:
    """平台适配器元数据"""

    name: str
    """平台名称（如 "onebot", "telegram"）"""

    description: str
    """平台描述"""

    id: str
    """平台 ID"""

    default_config_tmpl: Optional[dict[str, Any]] = None
    """默认配置模板"""

    adapter_display_name: Optional[str] = None
    """平台显示名称"""

    logo_path: Optional[str] = None
    """平台 logo 文件路径"""

    support_streaming_message: bool = True
    """是否支持流式消息"""

    cls: Optional[type] = field(default=None, compare=False)
    """平台适配器类"""
