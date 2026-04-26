from __future__ import annotations

from dataclasses import asdict

from quart import Blueprint, current_app, request

from ..deps import require_auth

conversations_bp = Blueprint("conversations", __name__, url_prefix="/api/v1/conversations")
personas_bp = Blueprint("personas", __name__, url_prefix="/api/v1/personas")


def _store():
    fw = current_app.config.get("FRAMEWORK")
    return getattr(fw, "conversation_store", None) if fw else None


def _no_store() -> tuple[dict, int]:
    return {"success": False, "message": "Conversation store not available."}, 503


# ===========================================================================
# Conversations
# ===========================================================================


@conversations_bp.route("", methods=["GET"], strict_slashes=False)
@require_auth
async def list_conversations() -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return _no_store()
    keys = await store.list_conversation_keys()
    return {"success": True, "data": list(keys)}


@conversations_bp.route("/<path:key>", methods=["GET"])
@require_auth
async def get_conversation(key: str) -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return _no_store()
    ctx = await store.get_conversation(key)
    if ctx is None:
        return {"success": False, "message": "Conversation not found."}, 404
    return {"success": True, "data": asdict(ctx)}


@conversations_bp.route("/<path:key>", methods=["DELETE"])
@require_auth
async def delete_conversation(key: str) -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return _no_store()
    await store.delete(key)
    return {"success": True}


# ===========================================================================
# Personas
# ===========================================================================


@personas_bp.route("", methods=["GET"], strict_slashes=False)
@require_auth
async def list_personas() -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return _no_store()
    personas = await store.list_personas()
    return {"success": True, "data": personas}


@personas_bp.route("/<name>", methods=["GET"])
@require_auth
async def get_persona(name: str) -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return _no_store()
    prompt = await store.get_persona(name)
    if prompt is None:
        return {"success": False, "message": f"Persona {name!r} not found."}, 404
    return {"success": True, "data": {"name": name, "prompt": prompt}}


@personas_bp.route("", methods=["POST"], strict_slashes=False)
@require_auth
async def create_persona() -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return _no_store()
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    name = str(body.get("name", "")).strip()
    prompt = str(body.get("prompt", "")).strip()
    if not name or not prompt:
        return {"success": False, "message": "name and prompt are required."}, 400
    await store.save_persona(name, prompt)
    return {"success": True, "data": {"name": name, "prompt": prompt}}, 201


@personas_bp.route("/<name>", methods=["PUT"])
@require_auth
async def update_persona(name: str) -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return _no_store()
    existing = await store.get_persona(name)
    if existing is None:
        return {"success": False, "message": f"Persona {name!r} not found."}, 404
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        return {"success": False, "message": "prompt is required."}, 400
    await store.save_persona(name, prompt)
    return {"success": True, "data": {"name": name, "prompt": prompt}}


@personas_bp.route("/<name>", methods=["DELETE"])
@require_auth
async def delete_persona(name: str) -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return _no_store()
    existing = await store.get_persona(name)
    if existing is None:
        return {"success": False, "message": f"Persona {name!r} not found."}, 404
    await store.delete_persona(name)
    return {"success": True}
