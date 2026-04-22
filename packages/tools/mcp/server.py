"""MCP server — exposes registered @agent_tool plugin tools via MCP protocol.

Supports two transports:
  - stdio:            run as subprocess, communicate on stdin/stdout
  - streamable-http:  returns a Starlette ASGI app to mount into any ASGI server

Usage::

    server = PluginMCPServer(tool_registry, name="nekobot")

    # stdio (blocking, meant to be launched by a host like Claude Desktop)
    server.run_stdio()

    # HTTP — mount the ASGI app into your existing ASGI/Quart app
    asgi_app = server.http_app()          # Starlette app at /mcp
    # or start a standalone uvicorn server
    await server.run_http_async(host="127.0.0.1", port=8765)
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from loguru import logger
from mcp.server.fastmcp import FastMCP

if TYPE_CHECKING:
    from ..registry import ToolRegistry


class PluginMCPServer:
    """Wraps FastMCP and syncs tools from ToolRegistry."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        *,
        name: str = "nekobot",
        instructions: str = "NekoBotPlugin agent tools",
    ) -> None:
        self._tool_registry = tool_registry
        self._mcp = FastMCP(name=name, instructions=instructions)
        self._registered_names: set[str] = set()

    # ------------------------------------------------------------------
    # Sync tools from ToolRegistry → FastMCP
    # ------------------------------------------------------------------

    def sync(self) -> None:
        """Rebuild the FastMCP tool list from the current ToolRegistry snapshot.

        Called once at startup and again after plugin hot-reload / unload.
        """
        defs = self._tool_registry.get_tool_definitions()
        current_names = {d.name for d in defs}

        # Remove tools that no longer exist — uses public SDK API
        for name in self._registered_names - current_names:
            self._mcp.remove_tool(name)
            logger.debug("PluginMCPServer: removed tool {!r}", name)

        # Add tools not yet registered
        for entry_list in self._tool_registry._plugin_tools.values():
            for entry in entry_list:
                if entry.name in self._registered_names:
                    continue
                self._add_tool(entry.name, entry.description, entry.handler)

        # Reflect actual registered state via public list_tools()
        self._registered_names = {t.name for t in self._mcp.list_tools()}
        logger.info(
            "PluginMCPServer: synced {} tool(s)", len(self._registered_names)
        )

    def _add_tool(
        self, name: str, description: str, handler: Any
    ) -> None:
        """Wrap handler so FastMCP can call it (drops positional plugin instance arg)."""

        @functools.wraps(handler)
        async def _wrapper(**kwargs: Any) -> Any:
            # plugin tools expect (self, **kwargs) — call without instance for MCP
            return await handler(**kwargs)

        _wrapper.__name__ = name
        _wrapper.__doc__ = description
        # strip 'self' from annotations so FastMCP doesn't complain
        orig_hints = getattr(handler, "__annotations__", {})
        _wrapper.__annotations__ = {
            k: v for k, v in orig_hints.items() if k != "self"
        }

        self._mcp.add_tool(
            _wrapper,
            name=name,
            description=description,
            structured_output=False,
        )
        logger.debug("PluginMCPServer: registered tool {!r}", name)

    # ------------------------------------------------------------------
    # Transport: stdio
    # ------------------------------------------------------------------

    def run_stdio(self) -> None:
        """Run as stdio MCP server (blocking). Meant to be invoked as a subprocess."""
        self.sync()
        logger.info("PluginMCPServer: starting stdio transport")
        self._mcp.run(transport="stdio")

    async def run_stdio_async(self) -> None:
        """Async version of run_stdio for embedding in an asyncio event loop."""
        self.sync()
        logger.info("PluginMCPServer: starting stdio transport (async)")
        await self._mcp.run_stdio_async()

    # ------------------------------------------------------------------
    # Transport: streamable-http (ASGI app)
    # ------------------------------------------------------------------

    def http_app(self, path: str = "/mcp") -> Any:
        """Return a Starlette ASGI app exposing tools at ``path``.

        Mount into any ASGI server::

            from starlette.applications import Starlette
            from starlette.routing import Mount

            app = Starlette(routes=[Mount("/mcp", app=server.http_app())])
        """
        self.sync()
        return self._mcp.streamable_http_app()

    async def run_http_async(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        path: str = "/mcp",
    ) -> None:
        """Start a standalone uvicorn server (runs until cancelled)."""
        try:
            import uvicorn
        except ImportError:
            raise RuntimeError(
                "uvicorn is required for PluginMCPServer.run_http_async(); "
                "install it with: pip install uvicorn"
            )

        self.sync()
        app = self._mcp.streamable_http_app()
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        logger.info(
            "PluginMCPServer: starting streamable-http on {}:{}{}", host, port, path
        )
        await server.serve()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def tool_names(self) -> list[str]:
        return [t.name for t in self._mcp.list_tools()]
