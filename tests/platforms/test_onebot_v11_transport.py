from __future__ import annotations

import asyncio
import json
import socket
from typing import cast

from aiohttp import ClientSession, WSMsgType

from packages.platforms.onebot_v11.transport import (
    OneBotV11Transport,
    OneBotV11TransportConfig,
)


def _unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        address = cast(tuple[str, int], sock.getsockname())
        return int(address[1])


async def test_transport_rejects_invalid_access_token() -> None:
    port = _unused_port()
    transport = OneBotV11Transport(
        OneBotV11TransportConfig(
            host="127.0.0.1",
            port=port,
            access_token="secret",
        )
    )
    await transport.start()
    try:
        async with ClientSession() as session:
            response = await session.get(
                f"http://127.0.0.1:{port}/ws?access_token=wrong"
            )
            assert response.status in (400, 401)
    finally:
        await transport.stop()


async def test_transport_routes_raw_events_to_handler() -> None:
    port = _unused_port()
    received: list[dict[str, object]] = []

    async def raw_event_handler(event: dict[str, object]) -> None:
        received.append(event)

    transport = OneBotV11Transport(
        OneBotV11TransportConfig(host="127.0.0.1", port=port),
        raw_event_handler=raw_event_handler,
    )
    await transport.start()
    try:
        async with ClientSession() as session:
            async with session.ws_connect(f"http://127.0.0.1:{port}/ws") as websocket:
                await websocket.send_json(
                    {"post_type": "message", "message_type": "private", "user_id": 1}
                )
                await asyncio.sleep(0.05)
    finally:
        await transport.stop()

    assert received[0]["post_type"] == "message"


async def test_transport_call_api_waits_for_echo_response() -> None:
    port = _unused_port()
    transport = OneBotV11Transport(
        OneBotV11TransportConfig(host="127.0.0.1", port=port)
    )
    await transport.start()
    try:
        async with ClientSession() as session:
            async with session.ws_connect(f"http://127.0.0.1:{port}/ws") as websocket:
                action_task = asyncio.create_task(
                    transport.call_api(
                        "send_private_msg", {"user_id": 1, "message": "hi"}
                    )
                )
                sent = await websocket.receive()
                assert sent.type == WSMsgType.TEXT
                payload = cast(dict[str, object], json.loads(cast(str, sent.data)))
                assert payload["action"] == "send_private_msg"
                await websocket.send_json(
                    {
                        "status": "ok",
                        "retcode": 0,
                        "data": {"message_id": 42},
                        "echo": payload["echo"],
                    }
                )
                result = await action_task
    finally:
        await transport.stop()

    assert result["status"] == "ok"
    assert result["data"] == {"message_id": 42}
