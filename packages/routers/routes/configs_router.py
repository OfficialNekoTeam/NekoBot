from __future__ import annotations

from dataclasses import asdict

from quart import Blueprint, current_app, request

from ...bootstrap.manager import ConfigManager
from ..deps import require_auth

configs_bp = Blueprint("configs", __name__, url_prefix="/api/v1/configs")


def _manager() -> ConfigManager | None:
    fw = current_app.config.get("FRAMEWORK")
    return getattr(fw, "config_manager", None) if fw else None


def _no_mgr() -> tuple[dict, int]:
    return {"success": False, "message": "Config manager not available."}, 503


# ---------------------------------------------------------------------------
# Config CRUD
# ---------------------------------------------------------------------------


@configs_bp.route("", methods=["GET"], strict_slashes=False)
@require_auth
async def list_configs() -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_mgr()
    entries = [asdict(e) for e in mgr.list_configs()]
    return {"success": True, "data": entries}


@configs_bp.route("", methods=["POST"], strict_slashes=False)
@require_auth
async def create_config() -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_mgr()
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    name = str(body.get("name", "")).strip()
    if not name:
        return {"success": False, "message": "name is required."}, 400
    description = str(body.get("description", ""))
    base_id = str(body.get("base_id", "default"))
    entry = mgr.create_config(name, description=description, base_id=base_id)
    return {"success": True, "data": asdict(entry)}, 201


@configs_bp.route("/<config_id>", methods=["GET"])
@require_auth
async def get_config(config_id: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_mgr()
    entry = mgr.get_entry(config_id)
    if entry is None:
        return {"success": False, "message": f"Config {config_id!r} not found."}, 404
    cfg = mgr.get_config(config_id)
    data = asdict(entry)
    if cfg is not None:
        data["providers"] = cfg.provider_configs
        data["plugin_bindings"] = cfg.plugin_bindings
    return {"success": True, "data": data}


@configs_bp.route("/<config_id>", methods=["PATCH"])
@require_auth
async def rename_config(config_id: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_mgr()
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    name = str(body.get("name", "")).strip() or None
    description = body.get("description")
    if name is None and description is None:
        return {"success": False, "message": "name or description is required."}, 400
    entry = mgr.get_entry(config_id)
    if entry is None:
        return {"success": False, "message": f"Config {config_id!r} not found."}, 404
    mgr.rename_config(
        config_id,
        name=name or entry.name,
        description=str(description) if description is not None else None,
    )
    updated = mgr.get_entry(config_id)
    return {"success": True, "data": asdict(updated)}


@configs_bp.route("/<config_id>", methods=["DELETE"])
@require_auth
async def delete_config(config_id: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_mgr()
    try:
        deleted = await mgr.delete_config(config_id)
    except ValueError as exc:
        return {"success": False, "message": str(exc)}, 400
    if not deleted:
        return {"success": False, "message": f"Config {config_id!r} not found."}, 404
    return {"success": True}


# ---------------------------------------------------------------------------
# Routing table
# ---------------------------------------------------------------------------


@configs_bp.route("/routes", methods=["GET"])
@require_auth
async def list_routes() -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_mgr()
    return {"success": True, "data": mgr.router.list_routes()}


@configs_bp.route("/routes", methods=["POST"])
@require_auth
async def add_route() -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_mgr()
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    instance_uuid = str(body.get("instance_uuid", "")).strip()
    scope = str(body.get("scope", "")).strip()
    session_id = str(body.get("session_id", "")).strip()
    config_id = str(body.get("config_id", "")).strip()
    if not config_id:
        return {"success": False, "message": "config_id is required."}, 400
    if mgr.get_entry(config_id) is None:
        return {"success": False, "message": f"Config {config_id!r} not found."}, 404
    mgr.router.add_route(instance_uuid, scope, session_id, config_id)
    return {"success": True, "data": mgr.router.list_routes()}, 201


@configs_bp.route("/routes/<path:key>", methods=["DELETE"])
@require_auth
async def delete_route(key: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_mgr()
    parts = key.split(":", 2)
    if len(parts) != 3:
        return {"success": False, "message": "Invalid route key format. Expected instance_uuid:scope:session_id"}, 400
    removed = mgr.router.remove_route(*parts)
    if not removed:
        return {"success": False, "message": "Route not found."}, 404
    return {"success": True}
