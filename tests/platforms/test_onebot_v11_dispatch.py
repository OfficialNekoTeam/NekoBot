from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast, override

from packages.app import NekoBotFramework
from packages.contracts.specs import (
    EventHandlerSpec,
    PluginSpec,
    ProviderSpec,
    RegisteredPlugin,
    RegisteredProvider,
)
from packages.llm.handler import LLMHandler
from packages.platforms.onebot_v11.dispatch import OneBotV11Dispatcher
from packages.platforms.onebot_v11.message_codec import OneBotV11MessageCodec
from packages.platforms.onebot_v11.types import OneBotV11OutboundTarget
from packages.platforms.types import PlatformEvent, Scene
from packages.providers.base import ChatProvider
from packages.providers.types import ProviderRequest, ProviderResponse, ValueMap
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


class PrivatePlugin(FakePlugin):
    async def on_message_private(self, payload: dict[str, object]) -> None:
        recorder = type(self).recorder
        if recorder is not None:
            recorder.payloads.append(payload)


class NoticePlugin(FakePlugin):
    async def on_notice_notify(self, payload: dict[str, object]) -> None:
        recorder = type(self).recorder
        if recorder is not None:
            recorder.payloads.append(payload)


class FakeChatProvider(ChatProvider):
    @override
    @classmethod
    def provider_spec(cls) -> ProviderSpec:
        return ProviderSpec(name="fake-chat", kind="chat", capabilities=("chat",))

    @override
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        last = (
            request.messages[-1].content if request.messages else (request.prompt or "")
        )
        return ProviderResponse(content=f"echo:{last}")


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
    event = PlatformEvent(
        event_type="message",
        event_name="message.group",
        scene=Scene.GROUP,
        platform="onebot",
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


async def test_dispatch_generic_group_handler_matches_concrete_group_event() -> None:
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

    async def send_callable(
        target: OneBotV11OutboundTarget,
        segments: list[dict[str, object]],
    ) -> dict[str, object]:
        _ = target, segments
        return {"status": "ok"}

    dispatcher = OneBotV11Dispatcher(
        framework,
        send_callable=send_callable,
        message_codec=OneBotV11MessageCodec(),
    )
    event = PlatformEvent(
        event_type="message",
        event_name="message.group.normal",
        scene=Scene.GROUP,
        platform="onebot",
        platform_instance_uuid="instance-1",
        user_id="user-1",
        group_id="group-42",
        chat_id="group-42",
        message_id="msg-1",
        plain_text="hello",
    )

    contexts = await dispatcher.dispatch_event(event)

    assert len(contexts) == 1
    assert recorder.payloads[0]["event_name"] == "message.group.normal"


async def test_dispatch_generic_private_handler_matches_concrete_private_event() -> (
    None
):
    framework = NekoBotFramework()
    recorder = Recorder()
    PrivatePlugin.recorder = recorder
    framework.runtime_registry.register_plugin(
        RegisteredPlugin(
            plugin_class=PrivatePlugin,
            spec=PluginSpec(name="private-plugin"),
            event_handlers=(
                ("on_message_private", EventHandlerSpec(event="message.private")),
            ),
        )
    )

    async def send_callable(
        target: OneBotV11OutboundTarget,
        segments: list[dict[str, object]],
    ) -> dict[str, object]:
        _ = target, segments
        return {"status": "ok"}

    dispatcher = OneBotV11Dispatcher(
        framework,
        send_callable=send_callable,
        message_codec=OneBotV11MessageCodec(),
    )
    event = PlatformEvent(
        event_type="message",
        event_name="message.private.friend",
        scene=Scene.PRIVATE,
        platform="onebot",
        platform_instance_uuid="instance-1",
        user_id="user-1",
        chat_id="user-1",
        message_id="msg-1",
        plain_text="hello",
    )

    contexts = await dispatcher.dispatch_event(event)

    assert len(contexts) == 1
    assert recorder.payloads[0]["event_name"] == "message.private.friend"


async def test_dispatch_generic_notice_handler_matches_concrete_notice_event() -> None:
    framework = NekoBotFramework()
    recorder = Recorder()
    NoticePlugin.recorder = recorder
    framework.runtime_registry.register_plugin(
        RegisteredPlugin(
            plugin_class=NoticePlugin,
            spec=PluginSpec(name="notice-plugin"),
            event_handlers=(
                ("on_notice_notify", EventHandlerSpec(event="notice.notify")),
            ),
        )
    )

    async def send_callable(
        target: OneBotV11OutboundTarget,
        segments: list[dict[str, object]],
    ) -> dict[str, object]:
        _ = target, segments
        return {"status": "ok"}

    dispatcher = OneBotV11Dispatcher(
        framework,
        send_callable=send_callable,
        message_codec=OneBotV11MessageCodec(),
    )
    event = PlatformEvent(
        event_type="notice",
        event_name="notice.notify.poke",
        scene=Scene.PRIVATE,
        platform="onebot",
        platform_instance_uuid="instance-1",
        user_id="user-1",
        chat_id="user-1",
    )

    contexts = await dispatcher.dispatch_event(event)

    assert len(contexts) == 1
    assert recorder.payloads[0]["event_name"] == "notice.notify.poke"


async def test_dispatch_llm_handler_replies_on_private_message() -> None:
    framework = NekoBotFramework()
    framework.runtime_registry.register_provider(
        RegisteredProvider(
            provider_class=FakeChatProvider,
            spec=FakeChatProvider.provider_spec(),
        )
    )
    configuration = framework.build_configuration_context(
        framework_config={"default_provider": "fake-chat"}
    )

    sent: list[tuple[OneBotV11OutboundTarget, list[dict[str, object]]]] = []

    async def send_callable(
        target: OneBotV11OutboundTarget,
        segments: list[dict[str, object]],
    ) -> dict[str, object]:
        sent.append((target, segments))
        return {"status": "ok", "data": {"message_id": 99}}

    llm_handler = LLMHandler(framework)
    dispatcher = OneBotV11Dispatcher(
        framework,
        send_callable=send_callable,
        message_codec=OneBotV11MessageCodec(),
        llm_handler=llm_handler,
    )
    event = PlatformEvent(
        event_type="message",
        event_name="message.private",
        scene=Scene.PRIVATE,
        platform="onebot",
        platform_instance_uuid="instance-1",
        user_id="user-1",
        chat_id="user-1",
        message_id="msg-2",
        plain_text="hello llm",
    )

    contexts = await dispatcher.dispatch_event(event, configuration)

    assert len(contexts) == 0  # no plugins, just LLM handler
    assert len(sent) == 1
    target, segments = sent[0]
    assert target.user_id == "user-1"
    assert segments[0] == cast(
        ValueMap,
        {"type": "text", "data": {"text": "echo:hello llm"}},
    )
