from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import cast

from loguru import logger
from quart import Quart, abort
from quart import websocket as quart_ws

from .types import ValueMap

RawEventHandler = Callable[[ValueMap], Awaitable[None]]


@dataclass(slots=True)
class OneBotV11TransportConfig:
    host: str = "0.0.0.0"
    port: int = 6299
    path: str = "/ws"
    access_token: str | None = None


class _ClientConnection:
    """Per-connection send queue, drained inside the handler's asyncio context."""

    def __init__(
        self,
        send_fn: Callable[[dict[str, object]], Awaitable[None]],
    ) -> None:
        self._send_fn = send_fn
        self._queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()

    async def enqueue(self, payload: dict[str, object]) -> None:
        await self._queue.put(payload)

    async def drain(self) -> None:
        """Call this as a task created inside the WebSocket handler so that
        quart_ws resolves to the correct connection via asyncio context copy."""
        while True:
            item = await self._queue.get()
            if item is None:
                return
            await self._send_fn(item)

    async def stop(self) -> None:
        await self._queue.put(None)


class OneBotV11Transport:
    def __init__(
        self,
        config: OneBotV11TransportConfig,
        *,
        raw_event_handler: RawEventHandler | None = None,
    ) -> None:
        self.config = config
        self.raw_event_handler = raw_event_handler
        self._app: Quart = Quart(__name__)
        self._clients: list[_ClientConnection] = []
        self._pending_actions: dict[str, asyncio.Future[dict[str, object]]] = {}
        self._shutdown_event: asyncio.Event | None = None
        self._serve_task: asyncio.Task[None] | None = None

        # Auth check before upgrade — returns HTTP 401 so client sees a handshake error
        @self._app.before_websocket
        async def _check_auth() -> None:
            if not self.config.access_token:
                return
            token = quart_ws.args.get("access_token", "")
            auth_header = quart_ws.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[len("Bearer "):]
            if token != self.config.access_token:
                abort(401)

        self._app.websocket(self.config.path)(self._handle_websocket)

    @property
    def has_clients(self) -> bool:
        return bool(self._clients)

    async def start(self) -> None:
        if self._serve_task is not None:
            return
        self._shutdown_event = asyncio.Event()

        from hypercorn.asyncio import serve as hypercorn_serve
        from hypercorn.config import Config as HypercornConfig

        hconfig = HypercornConfig()
        hconfig.bind = [f"{self.config.host}:{self.config.port}"]
        hconfig.loglevel = "WARNING"

        self._serve_task = asyncio.create_task(
            hypercorn_serve(  # type: ignore[arg-type]
                self._app,
                hconfig,
                shutdown_trigger=self._shutdown_event.wait,
            )
        )
        # Yield so hypercorn can bind the socket before we return
        await asyncio.sleep(0.05)
        logger.info(
            "OneBot v11 transport listening on ws://{}:{}{}",
            self.config.host,
            self.config.port,
            self.config.path,
        )

    async def stop(self) -> None:
        for client in list(self._clients):
            await client.stop()
        self._clients.clear()

        for future in list(self._pending_actions.values()):
            if not future.done():
                future.cancel()
        self._pending_actions.clear()

        if self._shutdown_event is not None:
            self._shutdown_event.set()
            self._shutdown_event = None

        if self._serve_task is not None:
            try:
                await asyncio.wait_for(self._serve_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._serve_task.cancel()
            self._serve_task = None

        logger.info("OneBot v11 transport stopped")

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

        logger.debug("OneBot action send: action={} echo={}", action, echo)
        await self._clients[0].enqueue(payload)
        try:
            return await future
        finally:
            self._pending_actions.pop(echo, None)

    async def _handle_websocket(self) -> None:
        # asyncio.create_task copies the current contextvars context, so quart_ws
        # inside drain() resolves to this connection's WebSocket object.
        async def _send_fn(data: dict[str, object]) -> None:
            await quart_ws.send(json.dumps(data))

        client = _ClientConnection(_send_fn)
        self._clients.append(client)
        remote = (
            quart_ws.headers.get("X-Forwarded-For")
            or quart_ws.headers.get("X-Real-IP")
            or quart_ws.remote_addr
            or "unknown"
        )
        n = len(self._clients)
        logger.info("[OneBot] 客户端已连接: {} (当前连接数: {})", remote, n)

        drain_task = asyncio.create_task(client.drain())
        try:
            while True:
                raw = await quart_ws.receive()
                if isinstance(raw, bytes):
                    raw = raw.decode()
                await self._handle_text_frame(raw)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("[OneBot] 处理客户端时出错: {}", exc)
        finally:
            drain_task.cancel()
            if client in self._clients:
                self._clients.remove(client)
            n = len(self._clients)
            logger.info("[OneBot] 客户端已断开: {} (当前连接数: {})", remote, n)

    async def _handle_text_frame(self, payload: str) -> None:
        logger.debug("OneBot raw websocket payload: {}", payload)
        raw = cast(object, json.loads(payload))
        if not isinstance(raw, dict):
            return
        data = {
            str(key): value
            for key, value in cast(dict[object, object], raw).items()
            if isinstance(key, str)
        }

        if self._is_action_response(data):
            logger.debug("OneBot action response received: echo={}", data.get("echo"))
            self._resolve_action_response(data)
            return

        if self.raw_event_handler is not None:
            logger.debug(
                (
                    "OneBot event payload received: post_type=%s message_type=%s "
                    "notice_type=%s request_type=%s meta_event_type=%s"
                ),
                data.get("post_type"),
                data.get("message_type"),
                data.get("notice_type"),
                data.get("request_type"),
                data.get("meta_event_type"),
            )
            task = asyncio.create_task(self.raw_event_handler(data))
            task.add_done_callback(self._on_event_task_done)

    def _on_event_task_done(self, task: asyncio.Task[None]) -> None:
        if not task.cancelled() and task.exception() is not None:
            logger.error("[OneBot] 事件处理异常: {}", task.exception())

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
