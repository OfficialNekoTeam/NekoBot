from __future__ import annotations

from quart import Blueprint, current_app, request

from ...knowledge.store import KnowledgeStore

knowledge_bp = Blueprint("knowledge", __name__, url_prefix="/api/v1/knowledge")

_NOT_AVAILABLE = (
    {"success": False, "message": "No knowledge base backend is loaded. Install a knowledge base plugin."},
    501,
)


def _store() -> KnowledgeStore | None:
    fw = current_app.config.get("FRAMEWORK")
    if fw is None:
        return None
    return getattr(fw, "knowledge_store", None)


# ---------------------------------------------------------------------------
# Knowledge base CRUD
# ---------------------------------------------------------------------------


@knowledge_bp.route("/", methods=["GET"])
async def list_kbs():
    store = _store()
    if store is None:
        return _NOT_AVAILABLE
    kbs = await store.list_kbs()
    return {"success": True, "data": [kb.__dict__ for kb in kbs]}


@knowledge_bp.route("/", methods=["POST"])
async def create_kb():
    store = _store()
    if store is None:
        return _NOT_AVAILABLE
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    kb = await store.create_kb(
        kb_id=str(body.get("id", "")),
        name=str(body.get("name", "")),
        description=str(body.get("description", "")),
        embedding_model=str(body.get("embedding_model", "text-embedding-3-small")),
    )
    return {"success": True, "data": kb.__dict__}, 201


@knowledge_bp.route("/<kb_id>", methods=["GET"])
async def get_kb(kb_id: str):
    store = _store()
    if store is None:
        return _NOT_AVAILABLE
    kb = await store.get_kb(kb_id)
    if kb is None:
        return {"success": False, "message": f"Knowledge base {kb_id!r} not found."}, 404
    return {"success": True, "data": kb.__dict__}


@knowledge_bp.route("/<kb_id>", methods=["DELETE"])
async def delete_kb(kb_id: str):
    store = _store()
    if store is None:
        return _NOT_AVAILABLE
    deleted = await store.delete_kb(kb_id)
    if not deleted:
        return {"success": False, "message": f"Knowledge base {kb_id!r} not found."}, 404
    return {"success": True}


# ---------------------------------------------------------------------------
# Document management
# ---------------------------------------------------------------------------


@knowledge_bp.route("/<kb_id>/documents", methods=["GET"])
async def list_documents(kb_id: str):
    store = _store()
    if store is None:
        return _NOT_AVAILABLE
    docs = await store.list_documents(kb_id)
    return {"success": True, "data": [d.__dict__ for d in docs]}


@knowledge_bp.route("/<kb_id>/documents", methods=["POST"])
async def upload_document(kb_id: str):
    store = _store()
    if store is None:
        return _NOT_AVAILABLE
    files = await request.files
    f = files.get("file")
    if f is None:
        return {"success": False, "message": "No file provided."}, 400
    content = f.read()
    doc = await store.add_document(kb_id, f.filename or "upload", content)
    return {"success": True, "data": doc.__dict__}, 201


@knowledge_bp.route("/<kb_id>/documents/<doc_id>", methods=["DELETE"])
async def delete_document(kb_id: str, doc_id: str):
    store = _store()
    if store is None:
        return _NOT_AVAILABLE
    deleted = await store.delete_document(kb_id, doc_id)
    if not deleted:
        return {"success": False, "message": "Document not found."}, 404
    return {"success": True}


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


@knowledge_bp.route("/<kb_id>/search", methods=["POST"])
async def search(kb_id: str):
    store = _store()
    if store is None:
        return _NOT_AVAILABLE
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    results = await store.search(
        kb_id,
        query=str(body.get("query", "")),
        top_k=int(body.get("top_k", 5)),
        score_threshold=float(body.get("score_threshold", 0.0)),
    )
    return {"success": True, "data": [r.__dict__ for r in results]}


@knowledge_bp.route("/search", methods=["POST"])
async def search_multi():
    store = _store()
    if store is None:
        return _NOT_AVAILABLE
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    kb_ids = body.get("kb_ids", [])
    if not isinstance(kb_ids, list):
        return {"success": False, "message": "kb_ids must be a list."}, 400
    results = await store.search_multi(
        kb_ids,
        query=str(body.get("query", "")),
        top_k=int(body.get("top_k", 5)),
    )
    return {"success": True, "data": [r.__dict__ for r in results]}
