from __future__ import annotations

from quart import Blueprint, current_app, request

from ...bootstrap.manager import ConfigManager
from ..deps import require_auth

platforms_bp = Blueprint("platforms", __name__, url_prefix="/api/v1/platforms")


def _manager() -> ConfigManager | None:
    fw = current_app.config.get("FRAMEWORK")
    return getattr(fw, "config_manager", None) if fw else None


def _no_mgr() -> tuple[dict, int]:
    return {"success": False, "message": "Config manager not available."}, 503


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@platforms_bp.route("", methods=["GET"], strict_slashes=False)
@require_auth
async def list_platforms() -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_mgr()
    config_id = request.args.get("config_id", "default")
    platforms = mgr.get_platforms(config_id)
    return {"success": True, "data": platforms}


# ---------------------------------------------------------------------------
# Create / upsert
# ---------------------------------------------------------------------------


@platforms_bp.route("", methods=["POST"], strict_slashes=False)
@require_auth
async def create_platform() -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_mgr()
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    instance_uuid = str(body.get("instance_uuid", "")).strip()
    if not instance_uuid:
        return {"success": False, "message": "instance_uuid is required."}, 400
    config_id = str(body.pop("config_id", "default"))
    await mgr.upsert_platform(instance_uuid, body, config_id)
    return {"success": True, "data": body}, 201


@platforms_bp.route("/<instance_uuid>", methods=["PUT"])
@require_auth
async def update_platform(instance_uuid: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_mgr()
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    config_id = str(body.pop("config_id", "default"))
    platforms = mgr.get_platforms(config_id)
    exists = any(p.get("instance_uuid") == instance_uuid for p in platforms)
    if not exists:
        return {"success": False, "message": f"Platform {instance_uuid!r} not found."}, 404
    body["instance_uuid"] = instance_uuid
    await mgr.upsert_platform(instance_uuid, body, config_id)
    return {"success": True, "data": body}


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@platforms_bp.route("/<instance_uuid>", methods=["DELETE"])
@require_auth
async def delete_platform(instance_uuid: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_mgr()
    config_id = request.args.get("config_id", "default")
    deleted = await mgr.delete_platform(instance_uuid, config_id)
    if not deleted:
        return {"success": False, "message": f"Platform {instance_uuid!r} not found."}, 404
    return {"success": True}


# ---------------------------------------------------------------------------
# Enable / disable toggle
# ---------------------------------------------------------------------------


@platforms_bp.route("/<instance_uuid>/enabled", methods=["PATCH"])
@require_auth
async def set_platform_enabled(instance_uuid: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return _no_mgr()
    body = await request.get_json()
    if not isinstance(body, dict) or "enabled" not in body:
        return {"success": False, "message": "enabled field is required."}, 400
    config_id = str(body.get("config_id", "default"))
    platforms = mgr.get_platforms(config_id)
    target = next((p for p in platforms if p.get("instance_uuid") == instance_uuid), None)
    if target is None:
        return {"success": False, "message": f"Platform {instance_uuid!r} not found."}, 404
    updated = dict(target)
    updated["enabled"] = bool(body["enabled"])
    await mgr.upsert_platform(instance_uuid, updated, config_id)
    return {"success": True, "data": {"instance_uuid": instance_uuid, "enabled": updated["enabled"]}}
