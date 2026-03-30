from __future__ import annotations

from typing import TYPE_CHECKING, Union

from loguru import logger

from .http import StreamableHTTPMCPClient
from .sse import SSEMCPClient
from .stdio import StdioMCPClient
from .types import MCPServerConfig

if TYPE_CHECKING:
    from ..registry import ToolRegistry

_AnyMCPClient = Union[StdioMCPClient, SSEMCPClient, StreamableHTTPMCPClient]


def _make_client(config: MCPServerConfig) -> _AnyMCPClient:
    if config.transport == "stdio":
        return StdioMCPClient(config)
    if config.transport == "sse":
        return SSEMCPClient(config)
    if config.transport == "http":
        return StreamableHTTPMCPClient(config)
    raise ValueError(
        f"unknown MCP transport {config.transport!r} for server {config.name!r}"
    )


class MCPManager:
    """Manages lifecycle of multiple MCP server connections.

    Usage::

        manager = MCPManager(tool_registry)
        await manager.load([
            MCPServerConfig(name="fs", transport="stdio",
                            command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "."]),
            MCPServerConfig(name="search", transport="http",
                            url="http://localhost:3001"),
        ])

        # hot-add / hot-remove at runtime
        await manager.add_server(MCPServerConfig(...))
        await manager.remove_server("fs")

        # graceful shutdown
        await manager.stop_all()
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry
        self._clients: dict[str, _AnyMCPClient] = {}

    async def load(self, configs: list[MCPServerConfig]) -> None:
        """Connect all enabled servers and sync their tools."""
        for config in configs:
            if not config.enabled:
                logger.debug("MCPManager: skipping disabled server {!r}", config.name)
                continue
            await self.add_server(config)

    async def add_server(self, config: MCPServerConfig) -> bool:
        """Connect a single MCP server (hot-add). Returns True on success."""
        if config.name in self._clients:
            logger.info("MCPManager: replacing existing server {!r}", config.name)
            await self.remove_server(config.name)

        client = _make_client(config)
        try:
            await client.start()
        except Exception as exc:
            logger.error("MCPManager: failed to start {!r}: {}", config.name, exc)
            return False

        self._clients[config.name] = client
        self._tool_registry.add_backend(config.name, client)
        await self._tool_registry.sync_backends()
        return True

    async def remove_server(self, name: str) -> None:
        """Disconnect a single MCP server (hot-remove)."""
        client = self._clients.pop(name, None)
        if client is None:
            return
        try:
            await client.stop()
        except Exception as exc:
            logger.warning("MCPManager: error stopping {!r}: {}", name, exc)
        self._tool_registry.remove_backend(name)
        await self._tool_registry.sync_backends()

    async def refresh_server(self, name: str) -> bool:
        """Re-fetch tool list for one server without reconnecting."""
        client = self._clients.get(name)
        if client is None:
            logger.warning("MCPManager: unknown server {!r}", name)
            return False
        try:
            await client.refresh()
            await self._tool_registry.sync_backends()
            return True
        except Exception as exc:
            logger.error("MCPManager: failed to refresh {!r}: {}", name, exc)
            return False

    async def refresh_all(self) -> None:
        for name in list(self._clients):
            await self.refresh_server(name)

    async def stop_all(self) -> None:
        for name in list(self._clients):
            await self.remove_server(name)

    @property
    def connected_servers(self) -> list[str]:
        return list(self._clients)

    def tool_count(self, server_name: str) -> int:
        client = self._clients.get(server_name)
        return len(client._tools) if client else 0
