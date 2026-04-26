from __future__ import annotations

from dataclasses import asdict

from quart import Blueprint, current_app, request

from ...tools.mcp.types import MCPServerConfig
from ..deps import require_auth

mcp_bp = Blueprint("mcp", __name__, url_prefix="/api/v1/mcp")


def _manager():
    fw = current_app.config.get("FRAMEWORK")
    return getattr(fw, "mcp_manager", None) if fw else None


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@mcp_bp.route("", methods=["GET"], strict_slashes=False)
@require_auth
async def list_servers() -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return {"success": False, "message": "MCP manager not available."}, 503
    servers = [
        {"name": name, "tool_count": mgr.tool_count(name)}
        for name in mgr.connected_servers
    ]
    return {"success": True, "data": servers}


# ---------------------------------------------------------------------------
# Add server
# ---------------------------------------------------------------------------


@mcp_bp.route("", methods=["POST"], strict_slashes=False)
@require_auth
async def add_server() -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return {"success": False, "message": "MCP manager not available."}, 503
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    name = str(body.get("name", "")).strip()
    transport = str(body.get("transport", "stdio"))
    if not name:
        return {"success": False, "message": "name is required."}, 400
    if transport not in ("stdio", "sse", "http"):
        return {"success": False, "message": "transport must be stdio, sse, or http."}, 400

    cfg = MCPServerConfig(
        name=name,
        transport=transport,  # type: ignore[arg-type]
        command=body.get("command"),
        args=body.get("args"),
        env=body.get("env"),
        cwd=body.get("cwd"),
        url=body.get("url"),
        headers=body.get("headers"),
        timeout=float(body.get("timeout", 30.0)),
        enabled=bool(body.get("enabled", True)),
    )
    ok = await mgr.add_server(cfg)
    if not ok:
        return {"success": False, "message": f"Failed to connect to MCP server {name!r}."}, 500
    return {"success": True, "data": asdict(cfg)}, 201


# ---------------------------------------------------------------------------
# Remove server
# ---------------------------------------------------------------------------


@mcp_bp.route("/<name>", methods=["DELETE"])
@require_auth
async def remove_server(name: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return {"success": False, "message": "MCP manager not available."}, 503
    if name not in mgr.connected_servers:
        return {"success": False, "message": f"MCP server {name!r} not found."}, 404
    await mgr.remove_server(name)
    return {"success": True}


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


@mcp_bp.route("/<name>/refresh", methods=["POST"])
@require_auth
async def refresh_server(name: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return {"success": False, "message": "MCP manager not available."}, 503
    ok = await mgr.refresh_server(name)
    if not ok:
        return {"success": False, "message": f"Failed to refresh MCP server {name!r}."}, 500
    return {"success": True, "data": {"name": name, "tool_count": mgr.tool_count(name)}}


@mcp_bp.route("/refresh", methods=["POST"])
@require_auth
async def refresh_all() -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return {"success": False, "message": "MCP manager not available."}, 503
    await mgr.refresh_all()
    return {
        "success": True,
        "data": [
            {"name": n, "tool_count": mgr.tool_count(n)}
            for n in mgr.connected_servers
        ],
    }
