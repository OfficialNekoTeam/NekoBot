from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from packages.app import NekoBotFramework
from packages.contracts.specs import EventHandlerSpec, PluginSpec, RegisteredPlugin
from packages.platforms.onebot_v11.dispatch import OneBotV11Dispatcher
from packages.platforms.onebot_v11.message_codec import OneBotV11MessageCodec
from packages.platforms.onebot_v11.types import (
    OneBotV11Event,
    OneBotV11OutboundTarget,
    OneBotV11Scene,
)
from packages.providers.types import ValueMap
from packages.runtime.context import PluginContext
from packages.schema import SchemaRegistry


@dataclass
class Recorder:
    payloads: list[dict[str, object]] = field(default_factory=list)
    replies: list[str] = field(default_factory=list)


class FakePlugin:
    recorder: Recorder | None = None

    def __init__(
        self,
        context: PluginContext,
        schema_registry: SchemaRegistry | None = None,
    ) -> None:
        self.context: PluginContext = context
        self.schema_registry: SchemaRegistry | None = schema_registry

    async def on_message_group(self, payload: dict[str, object]) -> None:
        recorder = type(self).recorder
        if recorder is not None:
            recorder.payloads.append(payload)
        await self.context.reply("pong")

    async def on_event(self, event_name: str, payload: dict[str, object]) -> None:
        _ = event_name, payload


async def test_dispatch_builds_contexts_and_routes_reply() -> None:
    framework = NekoBotFramework()
    recorder = Recorder()
    FakePlugin.recorder = recorder
    framework.runtime_registry.register_plugin(
        RegisteredPlugin(
            plugin_class=FakePlugin,
            spec=PluginSpec(name="demo-plugin"),
            event_handlers=(
                ("on_message_group", EventHandlerSpec(event="message.group")),
            ),
        )
    )

    sent: list[tuple[OneBotV11OutboundTarget, list[dict[str, object]]]] = []

    async def send_callable(
        target: OneBotV11OutboundTarget,
        segments: list[dict[str, object]],
    ) -> dict[str, object]:
        sent.append((target, segments))
        return {"status": "ok"}

    dispatcher = OneBotV11Dispatcher(
        framework,
        send_callable=send_callable,
        message_codec=OneBotV11MessageCodec(),
    )
    event = OneBotV11Event(
        event_type="message",
        event_name="message.group",
        scene=OneBotV11Scene.GROUP,
        platform_instance_uuid="instance-1",
        user_id="user-1",
        group_id="group-42",
        chat_id="group-42",
        message_id="msg-1",
        plain_text="hello",
    )

    contexts = await dispatcher.dispatch_event(event)

    assert len(contexts) == 1
    assert contexts[0].execution.scope == "group"
    assert contexts[0].conversation is not None
    assert contexts[0].conversation.conversation_key is not None
    assert recorder.payloads[0]["plain_text"] == "hello"
    assert len(sent) == 1
    target, segments = sent[0]
    assert target.group_id == "group-42"
    assert segments[0] == cast(
        ValueMap,
        {"type": "text", "data": {"text": "pong"}},
    )
