from __future__ import annotations

from typing import cast

from loguru import logger

from ...app import NekoBotFramework
from ...conversations.context import ConfigurationContext
from ...llm.handler import LLMHandler
from .config import OneBotV11AdapterConfig, build_onebot_v11_config
from .dispatch import OneBotV11Dispatcher
from .event_parser import OneBotV11EventParser
from .message_codec import OneBotV11MessageCodec
from .transport import OneBotV11Transport, OneBotV11TransportConfig, RawEventHandler
from .types import (
    OneBotV11MessageSegment,
    OneBotV11OutboundTarget,
    ValueMap,
)


class OneBotV11Adapter:
    def __init__(
        self,
        config: OneBotV11AdapterConfig,
        *,
        parser: OneBotV11EventParser | None = None,
        message_codec: OneBotV11MessageCodec | None = None,
        dispatcher: OneBotV11Dispatcher | None = None,
        transport_runtime: OneBotV11Transport | None = None,
        configuration: ConfigurationContext | None = None,
    ) -> None:
        self.config: OneBotV11AdapterConfig = config
        self.parser: OneBotV11EventParser = parser or OneBotV11EventParser()
        self.message_codec: OneBotV11MessageCodec = (
            message_codec or OneBotV11MessageCodec()
        )
        self.dispatcher: OneBotV11Dispatcher | None = dispatcher
        self.transport_runtime: OneBotV11Transport | None = transport_runtime
        self.configuration: ConfigurationContext | None = configuration
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

    async def handle_raw_event(self, raw_event: ValueMap) -> None:
        event = self.parser.parse(
            raw_event,
            platform_instance_uuid=self.config.instance_uuid,
        )
        if self.dispatcher is not None:
            await self.dispatcher.dispatch_event(event, self.configuration)

    async def call_api(
        self,
        action: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if self.transport_runtime is None:
            raise RuntimeError("OneBot v11 transport is not configured")
        return await self.transport_runtime.call_api(action, params)

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

    transport = OneBotV11Transport(
        OneBotV11TransportConfig(
            host=normalized_config.host,
            port=normalized_config.port,
            path=normalized_config.path,
            access_token=normalized_config.access_token,
        ),
    )

    adapter: OneBotV11Adapter | None = None

    async def send_callable(
        target: OneBotV11OutboundTarget,
        payload: list[dict[str, object]],
    ) -> dict[str, object]:
        if adapter is None:
            raise RuntimeError("Adapter not initialized")
        return await adapter.send_to_target(target, payload)

    llm_handler = LLMHandler(framework)

    async def delete_callable(message_id: str) -> dict[str, object]:
        if adapter is None:
            raise RuntimeError("Adapter not initialized")
        return await adapter.delete_message(message_id)

    async def fetch_message_callable(message_id: str) -> dict[str, object]:
        if adapter is None:
            raise RuntimeError("Adapter not initialized")
        return await adapter.call_api(
            "get_msg",
            {"message_id": int(message_id) if message_id.isdigit() else message_id},
        )

    async def fetch_forward_callable(forward_id: str) -> dict[str, object]:
        if adapter is None:
            raise RuntimeError("Adapter not initialized")
        # Apifox: 支持 message_id 和 id 两个参数名，示例用 message_id
        return await adapter.call_api("get_forward_msg", {"message_id": forward_id, "id": forward_id})

    dispatcher = OneBotV11Dispatcher(
        framework,
        send_callable=send_callable,
        delete_callable=delete_callable,
        fetch_message_callable=fetch_message_callable,
        fetch_forward_callable=fetch_forward_callable,
        message_codec=message_codec,
        llm_handler=llm_handler,
    )

    adapter = OneBotV11Adapter(
        normalized_config,
        parser=OneBotV11EventParser(),
        message_codec=message_codec,
        dispatcher=dispatcher,
        transport_runtime=transport,
        configuration=configuration,
    )

    async def raw_event_handler(raw_event: ValueMap) -> None:
        await adapter.handle_raw_event(raw_event)

    transport.raw_event_handler = cast(RawEventHandler, raw_event_handler)

    logger.info(
        "OneBot v11 adapter created: instance_uuid={} host={}:{}{} ",
        normalized_config.instance_uuid,
        normalized_config.host,
        normalized_config.port,
        normalized_config.path,
    )
    return adapter
