from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeAlias

from .event_parser import OneBotV11EventParser
from .message_codec import OneBotV11MessageCodec
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


@dataclass(frozen=True)
class OneBotV11AdapterConfig:
    instance_uuid: str
    host: str = "0.0.0.0"
    port: int = 6299
    path: str = "/ws"
    access_token: str | None = None
    self_id: str | None = None
    command_prefix: str = "/"
    metadata: ValueMap = field(default_factory=dict)


class OneBotV11Adapter:
    def __init__(
        self,
        config: OneBotV11AdapterConfig,
        *,
        event_handler: EventHandlerCallable | None = None,
        transport: TransportCallable | None = None,
        parser: OneBotV11EventParser | None = None,
        message_codec: OneBotV11MessageCodec | None = None,
    ) -> None:
        self.config: OneBotV11AdapterConfig = config
        self.event_handler: EventHandlerCallable | None = event_handler
        self.transport: TransportCallable | None = transport
        self.parser: OneBotV11EventParser = parser or OneBotV11EventParser()
        self.message_codec: OneBotV11MessageCodec = (
            message_codec or OneBotV11MessageCodec()
        )
        self._running: bool = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
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

    async def delete_message(self, message_id: str) -> dict[str, object]:
        return await self.call_api(
            "delete_msg",
            {"message_id": self._numeric_or_original(message_id)},
        )

    async def get_login_info(self) -> dict[str, object]:
        return await self.call_api("get_login_info")

    def _numeric_or_original(self, value: str) -> int | str:
        return int(value) if value.isdigit() else value
