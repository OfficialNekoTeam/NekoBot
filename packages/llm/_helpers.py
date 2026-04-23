"""_HelpersMixin: configuration and preference helpers."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from ._types import (
    _PREF_ENABLED,
    _PREF_MODEL,
    _PREF_PROVIDER,
    _Ctx,
)

if TYPE_CHECKING:
    from ..conversations.context import ConversationContext
    from ..runtime.context import ExecutionContext


class _HelpersMixin:
    def _check_permission(self, execution: ExecutionContext, *permissions: str) -> bool:
        engine = self.framework.permission_engine  # type: ignore[attr-defined]
        if engine is None:
            return True
        decision = engine.evaluate(
            permissions,
            execution.to_authorization_context(
                resource_kind="command",
                resource_name=permissions[0] if permissions else "",
            ),
            require_all=False,
        )
        return decision.allowed

    def _is_reply_enabled(self, ctx: _Ctx) -> bool:
        return bool(ctx.conversation.provider_preferences.get(_PREF_ENABLED, True))

    def _resolve_provider_name(self, ctx: _Ctx) -> str | None:
        pref = ctx.conversation.provider_preferences.get(_PREF_PROVIDER)
        if isinstance(pref, str) and pref:
            return pref
        return ctx.configuration.resolve_provider_name()

    def _resolve_model(self, ctx: _Ctx) -> str | None:
        pref = ctx.conversation.provider_preferences.get(_PREF_MODEL)
        return pref if isinstance(pref, str) and pref else None

    async def _save_prefs(self, ctx: _Ctx, prefs: dict[str, object]) -> ConversationContext:
        updated = replace(ctx.conversation, provider_preferences=prefs)
        return await self.framework.save_conversation_context(updated)  # type: ignore[attr-defined]

    def _get_command_prefix(self, ctx: _Ctx) -> str:
        val = ctx.configuration.framework_config.get("command_prefix")
        return val if isinstance(val, str) and val else "/"

    def _get_config_str(self, ctx: _Ctx, key: str, default: str) -> str:
        val = ctx.config.get(key)
        return val if isinstance(val, str) else default

    def _get_config_int(self, ctx: _Ctx, key: str, default: int) -> int:
        val = ctx.config.get(key)
        return val if isinstance(val, int) else default

    def _get_config_bool(self, ctx: _Ctx, key: str, default: bool) -> bool:
        val = ctx.config.get(key)
        return val if isinstance(val, bool) else default
