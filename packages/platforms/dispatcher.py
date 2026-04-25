from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, cast

from loguru import logger

from ..app import NekoBotFramework
from ..conversations.context import ConfigurationContext
from ..plugins.base import BasePlugin
from ..runtime.context import ExecutionContext, PluginContext
from ..runtime.dispatch_registry import EventHandlerEntry
from .types import EventType, PlatformEvent, Scene, SegmentType

if TYPE_CHECKING:
    from ..llm.handler import LLMHandler


class BaseDispatcher(ABC):
    """Platform-agnostic event dispatcher.

    Contains all generic routing logic (command → event-handler → on_event fallback
    → LLM).  Subclasses supply platform-specific callables (reply, recall,
    send_voice) and any extra payload data needed by the LLM handler.

    Minimal subclass contract
    ─────────────────────────
    Required (abstract):
        _make_reply_callable(event)       → ReplyCallable
        _make_recall_callable(event)      → RecallCallable

    Optional (provide a noop default):
        _make_send_voice_callable(event)  → SendVoiceCallable
        _get_llm_extra_payload(event, execution, configuration) → dict
    """

    def __init__(
        self,
        framework: NekoBotFramework,
        *,
        llm_handler: LLMHandler | None = None,
    ) -> None:
        self.framework = framework
        self.llm_handler = llm_handler

    # ------------------------------------------------------------------
    # Abstract interface — subclasses must implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _make_reply_callable(
        self, event: PlatformEvent
    ) -> Callable[[str], Awaitable[str | None]]:
        """Return a callable that sends a text reply and returns message_id."""
        ...

    @abstractmethod
    def _make_recall_callable(
        self, event: PlatformEvent
    ) -> Callable[[str], Awaitable[None]]:
        """Return a callable that deletes/recalls a message by message_id."""
        ...

    # ------------------------------------------------------------------
    # Optional hooks — subclasses may override
    # ------------------------------------------------------------------

    def _make_send_voice_callable(
        self, event: PlatformEvent
    ) -> Callable[[bytes, str], Awaitable[str | None]]:
        """Return a callable that sends audio.  Default is a no-op."""

        async def _noop(audio_bytes: bytes, mime_type: str) -> str | None:
            _ = audio_bytes, mime_type
            return None

        return _noop

    async def _get_llm_extra_payload(
        self,
        event: PlatformEvent,
        execution: ExecutionContext,
        configuration: ConfigurationContext,
    ) -> dict[str, object]:
        """Return extra key/values merged into the LLM handler payload.

        Override to inject image URLs, quoted text, STT transcription, etc.
        """
        return {}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def dispatch_event(
        self,
        event: PlatformEvent,
        configuration: ConfigurationContext | None = None,
    ) -> list[PluginContext]:
        execution = self.build_execution_context(event)
        cfg = configuration or self.framework.build_configuration_context()
        conversation = await self.framework.build_conversation_context(execution, cfg)
        bindings = self.framework.resolve_effective_plugin_bindings(cfg, execution=execution)

        logger.debug(
            "Dispatching {} event: event_name={} scope={} bindings={}",
            event.platform,
            event.event_name,
            execution.scope,
            len(bindings),
        )

        enabled = {b.plugin_name: b for b in bindings}
        reply_callable = self._make_reply_callable(event)
        recall_callable = self._make_recall_callable(event)
        send_voice_callable = self._make_send_voice_callable(event)
        contexts: list[PluginContext] = []
        handled_plugins: set[str] = set()
        payload = self._build_payload(event)

        async def _build_ctx(plugin_name: str) -> PluginContext:
            binding = enabled[plugin_name]
            ctx = await self.framework.build_plugin_context(
                plugin_name=plugin_name,
                execution=execution,
                configuration=cfg,
                conversation=conversation,
                binding=binding,
                reply_callable=reply_callable,
                recall_callable=recall_callable,
                send_voice_callable=send_voice_callable,
            )
            contexts.append(ctx)
            return ctx

        def _instantiate(plugin_name: str, ctx: PluginContext) -> BasePlugin:
            registered = self.framework.runtime_registry.plugins[plugin_name]
            plugin_class = cast(type[BasePlugin], registered.plugin_class)
            return plugin_class(ctx, schema_registry=self.framework.schema_registry)

        # --- Command routing: O(1) ---
        cmd_prefix = self._resolve_command_prefix(cfg)
        plain_text = (event.plain_text or "").strip()
        command_handled = False
        if plain_text.startswith(cmd_prefix):
            cmd_body = plain_text[len(cmd_prefix):]
            parts = cmd_body.split()
            cmd_name = parts[0].lower() if parts else ""
            cmd_args = parts[1:]
            cmd_entry = self.framework.command_registry.resolve(cmd_name)
            if cmd_entry is not None and cmd_entry.plugin_name in enabled:
                plugin_name = cmd_entry.plugin_name
                try:
                    ctx = await _build_ctx(plugin_name)
                    plugin = _instantiate(plugin_name, ctx)
                    handler = getattr(plugin, cmd_entry.handler_name, None)
                    if callable(handler):
                        cmd_payload = dict(payload)
                        cmd_payload["command_name"] = cmd_name
                        cmd_payload["command_args"] = cmd_args
                        logger.info(
                            "[{}] 命令分发: {} -> {} (cmd={})",
                            event.platform,
                            plugin_name,
                            cmd_entry.handler_name,
                            cmd_name,
                        )
                        await cast(
                            Callable[[dict[str, object]], Awaitable[None]], handler
                        )(cmd_payload)
                    handled_plugins.add(plugin_name)
                    command_handled = True
                except Exception as exc:
                    logger.error(
                        "[{}] 插件 {!r} 命令处理异常 (cmd={}): {}",
                        event.platform, plugin_name, cmd_name, exc,
                    )

        if not command_handled:
            # --- Event handler routing ---
            ev_entries = self.framework.event_handler_registry.resolve(event.event_name)
            by_plugin: dict[str, list[EventHandlerEntry]] = {}
            for ev_entry in ev_entries:
                if ev_entry.plugin_name in enabled:
                    by_plugin.setdefault(ev_entry.plugin_name, []).append(ev_entry)

            for plugin_name, entries in by_plugin.items():
                try:
                    ctx = await _build_ctx(plugin_name)
                    plugin = _instantiate(plugin_name, ctx)
                    for ev_entry in entries:
                        handler = getattr(plugin, ev_entry.handler_name, None)
                        if callable(handler):
                            logger.info(
                                "[{}] 分发至插件: {} -> {} (event={})",
                                event.platform,
                                plugin_name,
                                ev_entry.handler_name,
                                event.event_name,
                            )
                            await cast(
                                Callable[[dict[str, object]], Awaitable[None]], handler
                            )(payload)
                    await plugin.on_event(event.event_name, payload)
                except Exception as exc:
                    logger.error(
                        "[{}] 插件 {!r} 事件处理异常 (event={}): {}",
                        event.platform, plugin_name, event.event_name, exc,
                    )
                handled_plugins.add(plugin_name)

            # --- on_event fallback for remaining enabled plugins ---
            for plugin_name in enabled:
                if plugin_name in handled_plugins:
                    continue
                try:
                    ctx = await _build_ctx(plugin_name)
                    plugin = _instantiate(plugin_name, ctx)
                    await plugin.on_event(event.event_name, payload)
                except Exception as exc:
                    logger.error(
                        "[{}] 插件 {!r} on_event 异常: {}",
                        event.platform, plugin_name, exc,
                    )

        # --- LLM fallback (message events only) ---
        if self.llm_handler is not None and event.event_type == EventType.MESSAGE:
            try:
                extra = await self._get_llm_extra_payload(event, execution, cfg)
                llm_payload = {**payload, **extra}
                await self.llm_handler.handle(
                    payload=llm_payload,
                    execution=execution,
                    configuration=cfg,
                    conversation=conversation,
                    reply=reply_callable,
                    recall=recall_callable,
                )
            except Exception as exc:
                logger.error("[{}] LLM handler 异常: {}", event.platform, exc)

        return contexts

    # ------------------------------------------------------------------
    # Context builders (shared)
    # ------------------------------------------------------------------

    def build_execution_context(self, event: PlatformEvent) -> ExecutionContext:
        roles, group_roles = self._resolve_roles(event)
        return self.framework.build_execution_context(
            event_name=event.event_name,
            actor_id=event.user_id,
            platform=event.platform,
            platform_instance_uuid=event.platform_instance_uuid,
            conversation_id=None,
            chat_id=event.chat_id,
            group_id=event.group_id,
            thread_id=None,
            message_id=event.message_id,
            scope=self._resolve_scope(event),
            roles=roles,
            group_roles=group_roles,
            is_authenticated=bool(event.user_id),
            metadata={
                **event.metadata,
                "platform_event_type": event.event_type,
                "platform_scene": event.scene,
                "platform_self_id": event.self_id,
                "platform_segments": [
                    {"type": seg.type, "data": dict(seg.data)} for seg in event.segments
                ],
                "platform_raw_event": event.raw_event,
            },
        )

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _resolve_roles(
        self, event: PlatformEvent
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        roles: list[str] = []
        group_roles: list[str] = []
        if event.user_id and event.user_id in self.framework.owner_ids:
            roles.append("owner")
        if event.sender is not None:
            role = event.sender.role
            if role == "owner":
                group_roles.append("group_owner")
            elif role == "admin":
                group_roles.append("group_admin")
            elif role == "member":
                group_roles.append("member")
        return tuple(roles), tuple(group_roles)

    def _resolve_scope(self, event: PlatformEvent) -> str:
        if event.scene == Scene.GROUP:
            return "group"
        if event.scene == Scene.PRIVATE:
            return "private"
        return "platform"

    def _resolve_command_prefix(self, configuration: ConfigurationContext) -> str:
        raw = configuration.framework_config.get("command_prefix")
        if isinstance(raw, str) and raw:
            return raw
        return "/"

    def _build_effective_text(self, event: PlatformEvent) -> str:
        """Build a readable text representation of the message segments.

        - @bot (self_id) is skipped (it's an activation signal, not content)
        - @others become [@user_id]
        - Media segments are labelled by type
        """
        self_id = event.self_id
        parts: list[str] = []
        for seg in event.segments:
            if seg.type == SegmentType.TEXT:
                t = seg.data.get("text", "")
                if isinstance(t, str):
                    parts.append(t)
            elif seg.type == SegmentType.MENTION:
                uid = str(seg.data.get("user_id", ""))
                if uid == "all":
                    parts.append("[@全体成员]")
                elif self_id and uid == self_id:
                    pass  # @bot itself — skip
                elif uid:
                    parts.append(f"[@{uid}]")
            elif seg.type == SegmentType.IMAGE:
                parts.append("[图片]")
            elif seg.type == SegmentType.VOICE:
                parts.append("[语音]")
            elif seg.type == SegmentType.VIDEO:
                parts.append("[视频]")
        return "".join(parts).strip()

    def _build_payload(self, event: PlatformEvent) -> dict[str, object]:
        sender: dict[str, object] | None = None
        if event.sender is not None:
            sender = {
                "user_id": event.sender.user_id,
                "username": event.sender.username,
                "role": event.sender.role,
                **event.sender.metadata,
            }
        return {
            "event_type": event.event_type,
            "event_name": event.event_name,
            "scene": event.scene,
            "user_id": event.user_id,
            "group_id": event.group_id,
            "chat_id": event.chat_id,
            "message_id": event.message_id,
            "plain_text": event.plain_text,
            "effective_text": self._build_effective_text(event),
            "segments": [
                {"type": seg.type, "data": dict(seg.data)} for seg in event.segments
            ],
            "sender": sender,
            "metadata": event.metadata,
            "raw_event": event.raw_event,
        }

