"""_GroupMixin: group settings, blacklist/whitelist logic."""

from __future__ import annotations

from dataclasses import replace

from loguru import logger

from ..conversations.context import ConversationContext
from ..conversations.models import ConversationKey, IsolationMode
from ._types import (
    _PREF_BLACKLIST,
    _PREF_GROUP_ENABLED,
    _PREF_WHITELIST,
    _Ctx,
)


class _GroupMixin:
    def _group_settings_key(self, ctx: _Ctx) -> str:
        group_id = ctx.execution.group_id or "global"
        instance = ctx.execution.platform_instance_uuid or "default"
        return f"group_settings:{instance}:{group_id}"

    async def _load_group_settings(self, ctx: _Ctx) -> ConversationContext:
        group_id = ctx.execution.group_id or "global"
        key = self._group_settings_key(ctx)
        stored = await self.framework.conversation_store.get_conversation(key)  # type: ignore[attr-defined]
        if stored is not None:
            return stored
        return ConversationContext(
            isolation_mode=IsolationMode.SHARED_GROUP,
            conversation_key=ConversationKey(key),
            scope="group",
            chat_id=group_id,
        )

    async def _save_group_settings(
        self,
        ctx: _Ctx,
        existing: ConversationContext,
        prefs: dict[str, object],
    ) -> None:
        await self.framework.save_conversation_context(  # type: ignore[attr-defined]
            replace(existing, provider_preferences=prefs)
        )

    async def _is_group_reply_enabled(self, ctx: _Ctx) -> bool:
        if ctx.execution.group_id is None:
            return True
        gs = await self._load_group_settings(ctx)
        return bool(gs.provider_preferences.get(_PREF_GROUP_ENABLED, True))

    async def _is_user_allowed(self, ctx: _Ctx, user_id: str) -> bool:
        gs = await self._load_group_settings(ctx)
        prefs = gs.provider_preferences
        blacklist: list[object] = prefs.get(_PREF_BLACKLIST, [])  # type: ignore[assignment]
        if isinstance(blacklist, list) and user_id in blacklist:
            logger.debug("llm: user {} is blacklisted", user_id)
            return False
        whitelist: list[object] = prefs.get(_PREF_WHITELIST, [])  # type: ignore[assignment]
        if isinstance(whitelist, list) and whitelist and user_id not in whitelist:
            logger.debug("llm: user {} not in whitelist", user_id)
            return False
        return True
