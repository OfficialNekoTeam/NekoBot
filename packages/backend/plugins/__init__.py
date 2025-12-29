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
]
