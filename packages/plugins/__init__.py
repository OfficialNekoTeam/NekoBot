"""NekoBot插件系统"""

from .base import (
    BasePlugin,
    register,
    unregister,
    reload_plugin,
    enable_plugin,
    disable_plugin,
    export_commands,
    on_message,
    on_private_message,
    on_group_message,
)
from .metadata import (
    PluginMetadata,
    MetadataLoader,
    MetadataRegistry,
)
from .filters import (
    HandlerFilter,
    PermissionFilter,
    PermissionType,
    PermissionError,
)

__all__ = [
    "BasePlugin",
    "register",
    "unregister",
    "reload_plugin",
    "enable_plugin",
    "disable_plugin",
    "export_commands",
    "on_message",
    "on_private_message",
    "on_group_message",
    "PluginMetadata",
    "MetadataLoader",
    "MetadataRegistry",
    "HandlerFilter",
    "PermissionFilter",
    "PermissionType",
    "PermissionError",
]
