"""平台适配器注册系统"""

from typing import Optional, Type
from loguru import logger

from .metadata import PlatformMetadata

platform_registry: list[PlatformMetadata] = []
"""维护了通过装饰器注册的平台适配器"""
platform_cls_map: dict[str, Type] = {}
"""维护了平台适配器名称和适配器类的映射"""


def register_platform_adapter(
    adapter_name: str,
    desc: str,
    default_config_tmpl: Optional[dict[str, any]] = None,
    adapter_display_name: Optional[str] = None,
    logo_path: Optional[str] = None,
    support_streaming_message: bool = True,
):
    """用于注册平台适配器的带参装饰器。

    Args:
        adapter_name: 平台适配器名称（如 "onebot", "telegram"）
        desc: 平台描述
        default_config_tmpl: 平台适配器的默认配置模板
        adapter_display_name: 平台显示名称
        logo_path: 平台logo文件路径
        support_streaming_message: 是否支持流式消息
    """

    def decorator(cls: Type) -> Type:
        if adapter_name in platform_cls_map:
            raise ValueError(
                f"平台适配器 {adapter_name} 已经注册过了，可能发生了适配器命名冲突。",
            )

        # 添加必备选项
        if default_config_tmpl:
            if "type" not in default_config_tmpl:
                default_config_tmpl["type"] = adapter_name
            if "enable" not in default_config_tmpl:
                default_config_tmpl["enable"] = False
            if "id" not in default_config_tmpl:
                default_config_tmpl["id"] = adapter_name

        platform_metadata = PlatformMetadata(
            name=adapter_name,
            description=desc,
            id=adapter_name,
            default_config_tmpl=default_config_tmpl,
            adapter_display_name=adapter_display_name,
            logo_path=logo_path,
            support_streaming_message=support_streaming_message,
            cls=cls,
        )
        platform_registry.append(platform_metadata)
        platform_cls_map[adapter_name] = cls
        logger.debug(f"平台适配器 {adapter_name} 已注册")
        return cls

    return decorator


def get_platform_adapter(adapter_name: str) -> Optional[Type]:
    """获取平台适配器类"""
    return platform_cls_map.get(adapter_name)


def get_all_platforms() -> list[PlatformMetadata]:
    """获取所有已注册的平台"""
    return platform_registry
