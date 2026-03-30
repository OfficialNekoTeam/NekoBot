from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any

import mcp
import mcp.client.stdio
import mcp.types
from loguru import logger

from ..registry import ToolEntry
from .base import mcp_tools_to_entries, unwrap_call_result
from .types import MCPServerConfig


class StdioMCPClient:
    def __init__(self, config: MCPServerConfig) -> None:
        if not config.command:
            raise ValueError(f"MCP stdio {config.name!r} requires 'command'")
        self.server_name = config.name
        self.timeout = config.timeout
        self._command = config.command
        self._env = config.env or {}
        self._cwd = config.cwd
        self._exit_stack = AsyncExitStack()
        self._session: mcp.ClientSession | None = None
        self._tools: list[ToolEntry] = []

    async def start(self) -> None:
        params = mcp.StdioServerParameters(
            command=self._command[0],
            args=self._command[1:],
            env=self._env or None,
        )
        read, write = await self._exit_stack.enter_async_context(
            mcp.client.stdio.stdio_client(params)
        )
        self._session = await self._exit_stack.enter_async_context(
            mcp.ClientSession(read, write)
        )
        await self._session.initialize()
        await self._sync_tools()
        logger.info("MCP stdio[{}]: started ({} tool(s))", self.server_name, len(self._tools))

    async def stop(self) -> None:
        await self._exit_stack.aclose()
        self._session = None
        logger.info("MCP stdio[{}]: stopped", self.server_name)

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
