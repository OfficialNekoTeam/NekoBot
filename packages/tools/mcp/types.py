from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class MCPServerConfig:
    """MCP server connection configuration."""

    name: str
    transport: Literal["stdio", "sse", "http"]

    # stdio only
    command: list[str] | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    cwd: str | None = None

    # sse / streamable-http only
    url: str | None = None
    headers: dict[str, str] | None = None

    # common
    timeout: float = 30.0
    enabled: bool = True
