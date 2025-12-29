"""命令管理路由

提供命令列表、切换、重命名等 API
"""

from quart import request

from .route import Response, Route, RouteContext
from ..core.command_management import (
    list_commands,
    list_command_conflicts,
    toggle_command,
    rename_command,
)


class CommandRoute(Route):
    """命令管理路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.routes = {
            "/commands": ("GET", self.get_commands),
            "/commands/conflicts": ("GET", self.get_conflicts),
            "/commands/toggle": ("POST", self.toggle_command),
            "/commands/rename": ("POST", self.rename_command),
        }
        self.register_routes()

    async def get_commands(self):
        """获取命令列表"""
        commands = list_commands()
        summary = {
            "total": len(commands),
            "disabled": len([cmd for cmd in commands if not cmd["enabled"]]),
            "conflicts": len([cmd for cmd in commands if cmd.get("has_conflict")]),
        }
        return Response().ok({"items": commands, "summary": summary}).__dict__

    async def get_conflicts(self):
        """获取命令冲突列表"""
        conflicts = list_command_conflicts()
        return Response().ok(conflicts).__dict__

    async def toggle_command(self):
        """切换命令启用状态"""
        data = await request.get_json()
        handler_full_name = data.get("handler_full_name")
        enabled = data.get("enabled")

        if handler_full_name is None or enabled is None:
            return Response().error("handler_full_name 与 enabled 均为必填。").__dict__

        if isinstance(enabled, str):
            enabled = enabled.lower() in ("1", "true", "yes", "on")

        try:
            toggle_command(handler_full_name, bool(enabled))
        except ValueError as exc:
            return Response().error(str(exc)).__dict__

        from ..core.command_management import get_command

        descriptor = get_command(handler_full_name)
        if descriptor:
            return (
                Response()
                .ok(
                    {
                        "handler_full_name": descriptor.handler_full_name,
                        "handler_name": descriptor.handler_name,
                        "plugin": descriptor.plugin_name,
                        "description": descriptor.description,
                        "effective_command": descriptor.effective_command,
                        "aliases": descriptor.aliases,
                        "permission": descriptor.permission,
                        "enabled": descriptor.enabled,
                    }
                )
                .__dict__
            )
        return Response().ok({}).__dict__

    async def rename_command(self):
        """重命名命令"""
        data = await request.get_json()
        handler_full_name = data.get("handler_full_name")
        new_name = data.get("new_name")
        aliases = data.get("aliases")

        if not handler_full_name or not new_name:
            return Response().error("handler_full_name 与 new_name 均为必填。").__dict__

        try:
            rename_command(handler_full_name, new_name, aliases=aliases)
        except ValueError as exc:
            return Response().error(str(exc)).__dict__

        from ..core.command_management import get_command

        descriptor = get_command(handler_full_name)
        if descriptor:
            return (
                Response()
                .ok(
                    {
                        "handler_full_name": descriptor.handler_full_name,
                        "handler_name": descriptor.handler_name,
                        "plugin": descriptor.plugin_name,
                        "description": descriptor.description,
                        "effective_command": descriptor.effective_command,
                        "aliases": descriptor.aliases,
                        "permission": descriptor.permission,
                        "enabled": descriptor.enabled,
                    }
                )
                .__dict__
            )
        return Response().ok({}).__dict__
