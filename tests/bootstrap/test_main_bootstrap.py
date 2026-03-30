from __future__ import annotations

import asyncio
import json
import socket
from typing import TypeAlias, cast, override

from aiohttp import ClientSession, WSMsgType

from packages.app import NekoBotFramework
from packages.bootstrap.config import BootstrapConfig
from packages.bootstrap.runtime import bootstrap_runtime
from packages.contracts.specs import ProviderSpec, RegisteredProvider
from packages.platforms.registry import PlatformRegistry
from packages.providers.base import ChatProvider
from packages.providers.types import ProviderRequest, ProviderResponse

ValueMap: TypeAlias = dict[str, object]


def _unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        address = cast(tuple[str, int], sock.getsockname())
        return int(address[1])


class FakeAdapter:
    def __init__(self, config: ValueMap, **kwargs: object) -> None:
        self.config: ValueMap = config
        self.kwargs: dict[str, object] = kwargs
        self.started: bool = False
        self.stopped: bool = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


def create_fake_adapter(config: ValueMap, **kwargs: object) -> FakeAdapter:
    return FakeAdapter(config, **kwargs)


class FakeChatProvider(ChatProvider):
    @override
    @classmethod
    def provider_spec(cls) -> ProviderSpec:
        return ProviderSpec(name="fake-chat", kind="chat", capabilities=("chat",))

    @override
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        last = request.messages[-1].content if request.messages else (request.prompt or "")
        return ProviderResponse(content=f"echo:{last}")


async def test_bootstrap_runtime_starts_and_stops_platforms() -> None:
    framework = NekoBotFramework()
    registry = PlatformRegistry()
    registry.register(
        platform_type="fake",
        module_path="tests.bootstrap.test_main_bootstrap",
        factory_name="create_fake_adapter",
    )
    config = BootstrapConfig(platforms=[{"type": "fake", "instance_uuid": "bot-a"}])

    runtime = await bootstrap_runtime(config, framework=framework, registry=registry)

    assert len(runtime.running_platforms) == 1
    adapter = cast(FakeAdapter, runtime.running_platforms[0].adapter)
    assert adapter.started is True

    await runtime.stop()

    assert adapter.stopped is True


async def test_bootstrap_runtime_builds_configuration_context() -> None:
    framework = NekoBotFramework()
    registry = PlatformRegistry()
    registry.register(
        platform_type="fake",
        module_path="tests.bootstrap.test_main_bootstrap",
        factory_name="create_fake_adapter",
    )
    config = BootstrapConfig(
        framework_config={"default_provider": "openai"},
        conversation_config={"isolation_mode": "per_user"},
        platforms=[{"type": "fake", "instance_uuid": "bot-a"}],
    )

    runtime = await bootstrap_runtime(config, framework=framework, registry=registry)

    assert runtime.configuration.resolve_provider_name() == "openai"
    assert runtime.configuration.isolation_mode == "per_user"

    await runtime.stop()

    adapter = cast(FakeAdapter, runtime.running_platforms[0].adapter)
    assert adapter.stopped is True


async def test_bootstrap_runtime_handles_real_onebot_private_event() -> None:
    port = _unused_port()
    framework = NekoBotFramework()
    framework.runtime_registry.register_provider(
        RegisteredProvider(
            provider_class=FakeChatProvider,
            spec=FakeChatProvider.provider_spec(),
        )
    )
    runtime = await bootstrap_runtime(
        BootstrapConfig(
            framework_config={"default_provider": "fake-chat"},
            platforms=[
                {
                    "type": "onebot_v11",
                    "instance_uuid": "bot-a",
                    "enabled": True,
                    "host": "127.0.0.1",
                    "port": port,
                    "access_token": "secret",
                }
            ],
        ),
        framework=framework,
    )

    try:
        async with ClientSession() as session:
            async with session.ws_connect(
                f"http://127.0.0.1:{port}/ws?access_token=secret"
            ) as websocket:
                await websocket.send_json(
                    {
                        "post_type": "message",
                        "message_type": "private",
                        "user_id": 20001,
                        "self_id": 10001,
                        "message_id": 1,
                        "message": "hello",
                        "raw_message": "hello",
                    }
                )
                sent = await websocket.receive()
                assert sent.type == WSMsgType.TEXT
                payload = cast(dict[str, object], json.loads(cast(str, sent.data)))
                assert payload["action"] == "send_private_msg"
                params = cast(dict[str, object], payload["params"])
                assert params["user_id"] == 20001
                message = cast(list[dict[str, object]], params["message"])
                assert message[0] == {"type": "text", "data": {"text": "echo:hello"}}
                await websocket.send_json(
                    {
                        "status": "ok",
                        "retcode": 0,
                        "data": {"message_id": 99},
                        "echo": payload["echo"],
                    }
                )
                await asyncio.sleep(0.05)
    finally:
        await runtime.stop()


async def test_bootstrap_runtime_handles_real_onebot_private_friend_event() -> None:
    port = _unused_port()
    framework = NekoBotFramework()
    framework.runtime_registry.register_provider(
        RegisteredProvider(
            provider_class=FakeChatProvider,
            spec=FakeChatProvider.provider_spec(),
        )
    )
    runtime = await bootstrap_runtime(
        BootstrapConfig(
            framework_config={"default_provider": "fake-chat"},
            platforms=[
                {
                    "type": "onebot_v11",
                    "instance_uuid": "bot-a",
                    "enabled": True,
                    "host": "127.0.0.1",
                    "port": port,
                    "access_token": "secret",
                }
            ],
        ),
        framework=framework,
    )

    try:
        async with ClientSession() as session:
            async with session.ws_connect(
                f"http://127.0.0.1:{port}/ws?access_token=secret"
            ) as websocket:
                await websocket.send_json(
                    {
                        "post_type": "message",
                        "message_type": "private",
                        "sub_type": "friend",
                        "user_id": 20001,
                        "self_id": 10001,
                        "message_id": 2,
                        "message": "hello friend",
                        "raw_message": "hello friend",
                    }
                )
                sent = await websocket.receive()
                assert sent.type == WSMsgType.TEXT
                payload = cast(dict[str, object], json.loads(cast(str, sent.data)))
                assert payload["action"] == "send_private_msg"
                params = cast(dict[str, object], payload["params"])
                assert params["user_id"] == 20001
                message = cast(list[dict[str, object]], params["message"])
                assert message[0] == {
                    "type": "text",
                    "data": {"text": "echo:hello friend"},
                }
                await websocket.send_json(
                    {
                        "status": "ok",
                        "retcode": 0,
                        "data": {"message_id": 100},
                        "echo": payload["echo"],
                    }
                )
                await asyncio.sleep(0.05)
    finally:
        await runtime.stop()


async def test_bootstrap_runtime_handles_real_onebot_group_normal_event() -> None:
    port = _unused_port()
    framework = NekoBotFramework()
    framework.runtime_registry.register_provider(
        RegisteredProvider(
            provider_class=FakeChatProvider,
            spec=FakeChatProvider.provider_spec(),
        )
    )
    runtime = await bootstrap_runtime(
        BootstrapConfig(
            framework_config={"default_provider": "fake-chat"},
            conversation_config={"isolation_mode": "shared_group"},
            platforms=[
                {
                    "type": "onebot_v11",
                    "instance_uuid": "bot-a",
                    "enabled": True,
                    "host": "127.0.0.1",
                    "port": port,
                    "access_token": "secret",
                }
            ],
        ),
        framework=framework,
    )

    try:
        async with ClientSession() as session:
            async with session.ws_connect(
                f"http://127.0.0.1:{port}/ws?access_token=secret"
            ) as websocket:
                await websocket.send_json(
                    {
                        "post_type": "message",
                        "message_type": "group",
                        "sub_type": "normal",
                        "group_id": 30003,
                        "user_id": 20001,
                        "self_id": 10001,
                        "message_id": 3,
                        "message": [
                            {"type": "at", "data": {"qq": "10001"}},
                            {"type": "text", "data": {"text": "hello group"}},
                        ],
                        "raw_message": "@10001 hello group",
                    }
                )
                sent = await websocket.receive()
                assert sent.type == WSMsgType.TEXT
                payload = cast(dict[str, object], json.loads(cast(str, sent.data)))
                assert payload["action"] == "send_group_msg"
                params = cast(dict[str, object], payload["params"])
                assert params["group_id"] == 30003
                message = cast(list[dict[str, object]], params["message"])
                assert message[0] == {
                    "type": "text",
                    "data": {"text": "echo:hello group"},
                }
                await websocket.send_json(
                    {
                        "status": "ok",
                        "retcode": 0,
                        "data": {"message_id": 101},
                        "echo": payload["echo"],
                    }
                )
                await asyncio.sleep(0.05)
    finally:
        await runtime.stop()
