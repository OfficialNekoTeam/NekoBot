from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import cast

from aiohttp import WSMsgType, web

from .types import ValueMap

RawEventHandler = Callable[[ValueMap], Awaitable[None]]


@dataclass(slots=True)
class OneBotV11TransportConfig:
    host: str = "0.0.0.0"
    port: int = 6299
    path: str = "/ws"
    access_token: str | None = None


class OneBotV11Transport:
    def __init__(
        self,
        config: OneBotV11TransportConfig,
        *,
        raw_event_handler: RawEventHandler | None = None,
    ) -> None:
        self.config: OneBotV11TransportConfig = config
        self.raw_event_handler: RawEventHandler | None = raw_event_handler
        self._app: web.Application = web.Application()
        _ = self._app.add_routes([web.get(self.config.path, self._handle_websocket)])
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._clients: list[web.WebSocketResponse] = []
        self._pending_actions: dict[str, asyncio.Future[dict[str, object]]] = {}

    @property
    def has_clients(self) -> bool:
        return bool(self._clients)

    async def start(self) -> None:
        if self._runner is not None:
            return
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.config.host, self.config.port)
        await self._site.start()

    async def stop(self) -> None:
        for client in list(self._clients):
            _ = await client.close()
        self._clients.clear()

        for echo, future in list(self._pending_actions.items()):
            if not future.done():
                _ = future.cancel()
            _ = self._pending_actions.pop(echo, None)

        if self._site is not None:
            await self._site.stop()
            self._site = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def call_api(
        self,
        action: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if not self._clients:
            raise RuntimeError("no OneBot v11 websocket clients connected")

        payload: dict[str, object] = {
            "action": action,
            "params": params or {},
        }
        echo = str(uuid.uuid4())
        payload["echo"] = echo

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, object]] = loop.create_future()
        self._pending_actions[echo] = future
        await self._clients[0].send_json(payload)
        try:
            return await future
        finally:
            _ = self._pending_actions.pop(echo, None)

    async def _handle_websocket(self, request: web.Request) -> web.StreamResponse:
        if self.config.access_token:
            token = request.query.get("access_token", "")
            if token != self.config.access_token:
                return web.Response(
                    status=401, text="Unauthorized: Invalid access_token"
                )

        websocket = web.WebSocketResponse()
        _ = await websocket.prepare(request)
        self._clients.append(websocket)
        try:
            async for message in websocket:
                if message.type == WSMsgType.TEXT:
                    await self._handle_text_frame(cast(str, message.data))
                elif message.type == WSMsgType.ERROR:
                    break
        finally:
            if websocket in self._clients:
                _ = self._clients.remove(websocket)
        return websocket

    async def _handle_text_frame(self, payload: str) -> None:
        raw = cast(object, json.loads(payload))
        if not isinstance(raw, dict):
            return
        data = {
            str(key): value
            for key, value in cast(dict[object, object], raw).items()
            if isinstance(key, str)
        }

        if self._is_action_response(data):
            self._resolve_action_response(data)
            return

        if self.raw_event_handler is not None:
            await self.raw_event_handler(data)

    def _is_action_response(self, payload: ValueMap) -> bool:
        return "echo" in payload and ("status" in payload or "retcode" in payload)

    def _resolve_action_response(self, payload: ValueMap) -> None:
        echo = payload.get("echo")
        if not isinstance(echo, str):
            return
        future = self._pending_actions.get(echo)
        if future is None or future.done():
            return
        future.set_result(dict(payload))
