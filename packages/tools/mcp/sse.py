from __future__ import annotations

from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any

import mcp
import mcp.client.sse
import mcp.types
from loguru import logger

from ..registry import ToolEntry
from .base import mcp_tools_to_entries, unwrap_call_result
from .types import MCPServerConfig


class SSEMCPClient:
    def __init__(self, config: MCPServerConfig) -> None:
        if not config.url:
            raise ValueError(f"MCP SSE {config.name!r} requires 'url'")
        self.server_name = config.name
        self.timeout = config.timeout
        self._url = config.url
        self._headers = config.headers or {}
        self._exit_stack = AsyncExitStack()
        self._session: mcp.ClientSession | None = None
        self._tools: list[ToolEntry] = []

    async def start(self) -> None:
        read, write = await self._exit_stack.enter_async_context(
            mcp.client.sse.sse_client(
                url=self._url,
                headers=self._headers,
                timeout=self.timeout,
            )
        )
        self._session = await self._exit_stack.enter_async_context(
            mcp.ClientSession(
                read, write,
                read_timeout_seconds=timedelta(seconds=self.timeout),
            )
        )
        await self._session.initialize()
        await self._sync_tools()
        logger.info("MCP SSE[{}]: started ({} tool(s))", self.server_name, len(self._tools))

    async def stop(self) -> None:
        await self._exit_stack.aclose()
        self._session = None
        logger.info("MCP SSE[{}]: stopped", self.server_name)

    async def list_tools(self) -> list[ToolEntry]:
        return list(self._tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> object:
        assert self._session is not None
        result = await self._session.call_tool(name, arguments)
        return unwrap_call_result(result)

    async def refresh(self) -> None:
        await self._sync_tools()

    async def _sync_tools(self) -> None:
        assert self._session is not None
        response = await self._session.list_tools()
        self._tools = mcp_tools_to_entries(response.tools, self.server_name)
