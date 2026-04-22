from __future__ import annotations

import json
from typing import Any

import mcp.types

from ..registry import ToolEntry


def mcp_tools_to_entries(
    tools: list[mcp.types.Tool], server_name: str
) -> list[ToolEntry]:
    entries: list[ToolEntry] = []
    for t in tools:
        entries.append(
            ToolEntry(
                name=t.name,
                description=t.description or "",
                parameters_schema=t.inputSchema if isinstance(t.inputSchema, dict) else {},
                handler=_noop_handler,
                plugin_name=f"mcp:{server_name}",
                backend=f"mcp:{server_name}",
            )
        )
    return entries


def unwrap_call_result(result: mcp.types.CallToolResult) -> str:
    texts = [
        c.text
        for c in result.content
        if isinstance(c, mcp.types.TextContent)
    ]
    joined = "\n".join(texts)
    if result.isError:
        raise RuntimeError(f"MCP tool error: {joined}")
    return joined if joined else json.dumps(
        [c.model_dump() for c in result.content], ensure_ascii=False
    )


async def _noop_handler(**_: Any) -> str:
    return ""
