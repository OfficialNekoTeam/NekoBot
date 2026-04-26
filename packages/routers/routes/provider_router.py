from __future__ import annotations

from quart import Blueprint, current_app, request

from ...bootstrap.manager import ConfigManager
from ..deps import require_auth

provider_bp = Blueprint("providers", __name__, url_prefix="/api/v1/providers")


def _manager() -> ConfigManager | None:
    fw = current_app.config.get("FRAMEWORK")
    if fw is None:
        return None
    return getattr(fw, "config_manager", None)


def _no_backend() -> tuple[dict, int]:
    return {"success": False, "message": "Config manager not available."}, 503


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


@provider_bp.route("", methods=["GET"], strict_slashes=False)
@require_auth
async def list_providers() -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_backend()
    config_id = request.args.get("config_id", "default")
    providers = mgr.get_providers(config_id)
    return {"success": True, "data": providers}


@provider_bp.route("", methods=["POST"], strict_slashes=False)
@require_auth
async def create_provider() -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_backend()
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    name = str(body.get("name", "")).strip()
    if not name:
        return {"success": False, "message": "name is required."}, 400
    config_id = str(body.get("config_id", "default"))
    cfg = {k: v for k, v in body.items() if k not in ("name", "config_id")}
    await mgr.set_provider(name, cfg, config_id)
    return {"success": True, "data": {name: cfg}}, 201


# ---------------------------------------------------------------------------
# Single resource
# ---------------------------------------------------------------------------


@provider_bp.route("/<name>", methods=["GET"])
@require_auth
async def get_provider(name: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_backend()
    config_id = request.args.get("config_id", "default")
    providers = mgr.get_providers(config_id)
    if name not in providers:
        return {"success": False, "message": f"Provider {name!r} not found."}, 404
    return {"success": True, "data": {name: providers[name]}}


@provider_bp.route("/<name>", methods=["PUT"])
@require_auth
async def update_provider(name: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_backend()
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    config_id = str(body.pop("config_id", "default"))
    providers = mgr.get_providers(config_id)
    if name not in providers:
        return {"success": False, "message": f"Provider {name!r} not found."}, 404
    await mgr.set_provider(name, body, config_id)
    return {"success": True, "data": {name: body}}


@provider_bp.route("/<name>", methods=["DELETE"])
@require_auth
async def delete_provider(name: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_backend()
    config_id = request.args.get("config_id", "default")
    deleted = await mgr.delete_provider(name, config_id)
    if not deleted:
        return {"success": False, "message": f"Provider {name!r} not found."}, 404
    return {"success": True}


# ---------------------------------------------------------------------------
# Enable / disable toggle
# ---------------------------------------------------------------------------


@provider_bp.route("/<name>/enabled", methods=["PATCH"])
@require_auth
async def set_provider_enabled(name: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_backend()
    body = await request.get_json()
    if not isinstance(body, dict) or "enabled" not in body:
        return {"success": False, "message": "enabled field is required."}, 400
    config_id = str(body.get("config_id", "default"))
    providers = mgr.get_providers(config_id)
    if name not in providers:
        return {"success": False, "message": f"Provider {name!r} not found."}, 404
    cfg = dict(providers[name])
    cfg["enabled"] = bool(body["enabled"])
    await mgr.set_provider(name, cfg, config_id)
    return {"success": True, "data": {"name": name, "enabled": cfg["enabled"]}}
