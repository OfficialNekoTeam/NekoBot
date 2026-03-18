from __future__ import annotations


class ScopeName:
    GLOBAL = "global"
    PLATFORM = "platform"
    PRIVATE = "private"
    GROUP = "group"
    CONVERSATION = "conversation"


class PermissionName:
    COMMAND_INVOKE = "command.invoke"
    PLUGIN_INVOKE = "plugin.invoke"
    PLUGIN_MANAGE = "plugin.manage"
    PROVIDER_USE = "provider.use"
    PROVIDER_MANAGE = "provider.manage"
    TOOL_USE = "tool.use"
    SYSTEM_CONFIGURE = "system.configure"
    KB_READ = "kb.read"
    KB_WRITE = "kb.write"


BUILTIN_ROLES = (
    "owner",
    "super_admin",
    "admin",
    "platform_admin",
    "group_owner",
    "group_admin",
    "member",
)
