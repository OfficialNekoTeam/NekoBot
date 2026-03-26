from __future__ import annotations

from collections.abc import Awaitable, Callable
from importlib import import_module
from typing import Protocol, TypeAlias, cast

from ...app import NekoBotFramework
from ...conversations.context import ConfigurationContext
from ...plugins.base import BasePlugin
from ...runtime.context import ExecutionContext, PluginContext
from .types import (
    OneBotV11Event,
    OneBotV11MessageSegment,
    OneBotV11OutboundTarget,
    OneBotV11Scene,
)

OutboundSender: TypeAlias = Callable[
    [OneBotV11OutboundTarget, list[dict[str, object]]],
    Awaitable[dict[str, object]],
]


class MessageCodecLike(Protocol):
    def text(self, text: str) -> OneBotV11MessageSegment: ...

    def encode(
        self, segments: list[OneBotV11MessageSegment]
    ) -> list[dict[str, object]]: ...


class OneBotV11Dispatcher:
    def __init__(
        self,
        framework: NekoBotFramework,
        *,
        send_callable: OutboundSender,
        message_codec: MessageCodecLike | None = None,
    ) -> None:
        self.framework: NekoBotFramework = framework
        self.send_callable: OutboundSender = send_callable
        self.message_codec: MessageCodecLike
        if message_codec is None:
            module = import_module("packages.platforms.onebot_v11.message_codec")
            codec_class = cast(
                Callable[[], object], getattr(module, "OneBotV11MessageCodec")
            )
            self.message_codec = cast(MessageCodecLike, codec_class())
        else:
            self.message_codec = message_codec

    def build_execution_context(self, event: OneBotV11Event) -> ExecutionContext:
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
            metadata={
                **event.metadata,
                "onebot_event_type": event.event_type,
                "onebot_scene": event.scene,
                "onebot_self_id": event.self_id,
                "onebot_segments": event.segments,
                "onebot_raw_event": event.raw_event,
            },
        )

    def build_reply_target(self, event: OneBotV11Event) -> OneBotV11OutboundTarget:
        if event.scene == OneBotV11Scene.GROUP and event.group_id is not None:
            return OneBotV11OutboundTarget(
                scene=OneBotV11Scene.GROUP,
                chat_id=event.group_id,
                group_id=event.group_id,
                user_id=event.user_id,
                message_id=event.message_id,
                reply_to_message_id=event.message_id,
            )

        chat_id = event.chat_id or event.user_id
        if chat_id is None:
            raise ValueError("OneBot v11 event is missing a reply target")

        return OneBotV11OutboundTarget(
            scene=OneBotV11Scene.PRIVATE,
            chat_id=chat_id,
            user_id=event.user_id or chat_id,
            message_id=event.message_id,
            reply_to_message_id=event.message_id,
        )

    async def dispatch_event(
        self,
        event: OneBotV11Event,
        configuration: ConfigurationContext | None = None,
    ) -> list[PluginContext]:
        execution = self.build_execution_context(event)
        configuration = configuration or self.framework.build_configuration_context()
        conversation = self.framework.build_conversation_context(
            execution, configuration
        )
        bindings = self.framework.resolve_effective_plugin_bindings(
            configuration,
            execution=execution,
        )
        contexts: list[PluginContext] = []
        for binding in bindings:
            plugin_context = self.framework.build_plugin_context(
                plugin_name=binding.plugin_name,
                execution=execution,
                configuration=configuration,
                conversation=conversation,
                binding=binding,
                reply_callable=self._build_reply_callable(event),
            )
            contexts.append(plugin_context)
            await self._dispatch_to_plugin(binding.plugin_name, event, plugin_context)
        return contexts

    async def _dispatch_to_plugin(
        self,
        plugin_name: str,
        event: OneBotV11Event,
        plugin_context: PluginContext,
    ) -> None:
        registered = self.framework.runtime_registry.plugins.get(plugin_name)
        if registered is None:
            return

        plugin_class = cast(type[BasePlugin], registered.plugin_class)
        plugin = plugin_class(
            plugin_context, schema_registry=self.framework.schema_registry
        )

        for handler_name, handler_spec in registered.event_handlers:
            if handler_spec.event != event.event_name:
                continue
            handler = getattr(plugin, handler_name, None)
            if callable(handler):
                await cast(Callable[[dict[str, object]], Awaitable[None]], handler)(
                    self._build_payload(event)
                )

        await plugin.on_event(event.event_name, self._build_payload(event))

    def _build_payload(self, event: OneBotV11Event) -> dict[str, object]:
        return {
            "event_type": event.event_type,
            "event_name": event.event_name,
            "scene": event.scene,
            "user_id": event.user_id,
            "group_id": event.group_id,
            "chat_id": event.chat_id,
            "message_id": event.message_id,
            "plain_text": event.plain_text,
            "segments": event.segments,
            "sender": event.sender,
            "metadata": event.metadata,
            "raw_event": event.raw_event,
        }

    def _build_reply_callable(
        self,
        event: OneBotV11Event,
    ) -> Callable[[str], Awaitable[None]]:
        target = self.build_reply_target(event)

        async def reply(message: str) -> None:
            outbound_segments: list[OneBotV11MessageSegment] = [
                self.message_codec.text(message)
            ]
            segments = self.message_codec.encode(outbound_segments)
            _ = await self.send_callable(target, segments)

        return reply

    def _resolve_scope(self, event: OneBotV11Event) -> str:
        if event.scene == OneBotV11Scene.GROUP:
            return "group"
        if event.scene == OneBotV11Scene.PRIVATE:
            return "private"
        return "platform"
