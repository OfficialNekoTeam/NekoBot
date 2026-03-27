from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeAlias, cast

from ...app import NekoBotFramework
from ...conversations.context import ConfigurationContext
from .config import OneBotV11AdapterConfig, build_onebot_v11_config
from .dispatch import OneBotV11Dispatcher
from .event_parser import OneBotV11EventParser
from .message_codec import OneBotV11MessageCodec
from .transport import OneBotV11Transport, OneBotV11TransportConfig, RawEventHandler
from .types import (
    OneBotV11Event,
    OneBotV11MessageSegment,
    OneBotV11OutboundTarget,
    ValueMap,
)

TransportCallable: TypeAlias = Callable[
    [str, dict[str, object]], Awaitable[dict[str, object]]
]
EventHandlerCallable: TypeAlias = Callable[[OneBotV11Event], Awaitable[None]]


class OneBotV11Adapter:
    def __init__(
        self,
        config: OneBotV11AdapterConfig,
        *,
        event_handler: EventHandlerCallable | None = None,
        transport: TransportCallable | None = None,
        parser: OneBotV11EventParser | None = None,
        message_codec: OneBotV11MessageCodec | None = None,
        dispatcher: OneBotV11Dispatcher | None = None,
        transport_runtime: OneBotV11Transport | None = None,
    ) -> None:
        self.config: OneBotV11AdapterConfig = config
        self.event_handler: EventHandlerCallable | None = event_handler
        self.transport: TransportCallable | None = transport
        self.parser: OneBotV11EventParser = parser or OneBotV11EventParser()
        self.message_codec: OneBotV11MessageCodec = (
            message_codec or OneBotV11MessageCodec()
        )
        self.dispatcher: OneBotV11Dispatcher | None = dispatcher
        self.transport_runtime: OneBotV11Transport | None = transport_runtime
        self._running: bool = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self.transport_runtime is not None:
            await self.transport_runtime.start()
        self._running = True

    async def stop(self) -> None:
        if self.transport_runtime is not None:
            await self.transport_runtime.stop()
        self._running = False

    async def handle_raw_event(self, raw_event: ValueMap) -> OneBotV11Event:
        event = self.parser.parse(
            raw_event,
            platform_instance_uuid=self.config.instance_uuid,
        )
        if self.event_handler is not None:
            await self.event_handler(event)
        return event

    async def call_api(
        self,
        action: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if self.transport is None:
            raise RuntimeError("OneBot v11 transport is not configured")
        return await self.transport(action, params or {})

    async def send_private_message(
        self,
        *,
        user_id: str,
        segments: list[OneBotV11MessageSegment],
    ) -> dict[str, object]:
        payload = self.message_codec.encode(segments)
        return await self.call_api(
            "send_private_msg",
            {"user_id": self._numeric_or_original(user_id), "message": payload},
        )

    async def send_group_message(
        self,
        *,
        group_id: str,
        segments: list[OneBotV11MessageSegment],
    ) -> dict[str, object]:
        payload = self.message_codec.encode(segments)
        return await self.call_api(
            "send_group_msg",
            {"group_id": self._numeric_or_original(group_id), "message": payload},
        )

    async def send_to_target(
        self,
        target: OneBotV11OutboundTarget,
        segments: list[OneBotV11MessageSegment],
    ) -> dict[str, object]:
        if target.scene == "group" and target.group_id is not None:
            return await self.send_group_message(
                group_id=target.group_id,
                segments=segments,
            )
        if target.user_id is not None:
            return await self.send_private_message(
                user_id=target.user_id,
                segments=segments,
            )
        raise ValueError("OneBot v11 outbound target is missing required identifiers")

    async def send_to_target_from_payload(
        self,
        target: OneBotV11OutboundTarget,
        payload: list[dict[str, object]],
    ) -> dict[str, object]:
        if target.scene == "group" and target.group_id is not None:
            return await self.call_api(
                "send_group_msg",
                {
                    "group_id": self._numeric_or_original(target.group_id),
                    "message": payload,
                },
            )
        if target.user_id is not None:
            return await self.call_api(
                "send_private_msg",
                {
                    "user_id": self._numeric_or_original(target.user_id),
                    "message": payload,
                },
            )
        raise ValueError("OneBot v11 outbound target is missing required identifiers")

    async def delete_message(self, message_id: str) -> dict[str, object]:
        return await self.call_api(
            "delete_msg",
            {"message_id": self._numeric_or_original(message_id)},
        )

    async def get_login_info(self) -> dict[str, object]:
        return await self.call_api("get_login_info")

    def _numeric_or_original(self, value: str) -> int | str:
        return int(value) if value.isdigit() else value


def create_onebot_v11_adapter(
    config: dict[str, object],
    **kwargs: object,
) -> OneBotV11Adapter:
    framework = kwargs.get("framework")
    configuration = kwargs.get("configuration")
    if not isinstance(framework, NekoBotFramework):
        raise TypeError("OneBot v11 adapter creation requires framework instance")
    if configuration is not None and not isinstance(
        configuration, ConfigurationContext
    ):
        raise TypeError("configuration must be a ConfigurationContext when provided")

    normalized_config = build_onebot_v11_config(config)
    message_codec = OneBotV11MessageCodec()
    adapter: OneBotV11Adapter

    async def event_handler(event: OneBotV11Event) -> None:
        if adapter.dispatcher is None:
            return
        _ = await adapter.dispatcher.dispatch_event(event, configuration)

    transport = OneBotV11Transport(
        OneBotV11TransportConfig(
            host=normalized_config.host,
            port=normalized_config.port,
            path=normalized_config.path,
            access_token=normalized_config.access_token,
        ),
        raw_event_handler=None,
    )

    dispatcher = OneBotV11Dispatcher(
        framework,
        send_callable=lambda target, payload: adapter.send_to_target_from_payload(
            target, payload
        ),
        message_codec=message_codec,
    )

    adapter = OneBotV11Adapter(
        normalized_config,
        event_handler=event_handler,
        transport=transport.call_api,
        parser=OneBotV11EventParser(),
        message_codec=message_codec,
        dispatcher=dispatcher,
        transport_runtime=transport,
    )

    async def raw_event_handler(raw_event: ValueMap) -> None:
        _ = await adapter.handle_raw_event(raw_event)

    transport.raw_event_handler = cast(RawEventHandler, raw_event_handler)
    return adapter
