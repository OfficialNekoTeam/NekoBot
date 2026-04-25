from __future__ import annotations

from dataclasses import asdict

from quart import Blueprint, current_app, request

from ...knowledge.store import KnowledgeStore
from ..deps import require_auth

knowledge_bp = Blueprint("knowledge", __name__, url_prefix="/api/v1/knowledge")


def _store() -> KnowledgeStore | None:
    fw = current_app.config.get("FRAMEWORK")
    if fw is None:
        return None
    return getattr(fw, "knowledge_store", None)


# ---------------------------------------------------------------------------
# 状态检查（公开，无需鉴权）
# ---------------------------------------------------------------------------


@knowledge_bp.route("/status", methods=["GET"])
async def status() -> dict:
    """检查知识库后端是否已加载。"""
    store = _store()
    available = store is not None
    backend = type(store).__name__ if available else None
    return {"success": True, "data": {"available": available, "backend": backend}}


# ---------------------------------------------------------------------------
# 知识库 CRUD
# ---------------------------------------------------------------------------


@knowledge_bp.route("", methods=["GET"], strict_slashes=False)
@require_auth
async def list_kbs() -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return {"success": False, "message": "No knowledge base backend loaded."}, 501
    kbs = await store.list_kbs()
    return {"success": True, "data": [asdict(kb) for kb in kbs]}


@knowledge_bp.route("", methods=["POST"], strict_slashes=False)
@require_auth
async def create_kb() -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return {"success": False, "message": "No knowledge base backend loaded."}, 501
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    kb_id = str(body.get("id", "")).strip()
    name = str(body.get("name", "")).strip()
    if not kb_id or not name:
        return {"success": False, "message": "id and name are required."}, 400
    kb = await store.create_kb(
        kb_id=kb_id,
        name=name,
        description=str(body.get("description", "")),
        embedding_model=str(body.get("embedding_model", "text-embedding-3-small")),
    )
    return {"success": True, "data": asdict(kb)}, 201


@knowledge_bp.route("/<kb_id>", methods=["GET"])
@require_auth
async def get_kb(kb_id: str) -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return {"success": False, "message": "No knowledge base backend loaded."}, 501
    kb = await store.get_kb(kb_id)
    if kb is None:
        return {"success": False, "message": f"Knowledge base {kb_id!r} not found."}, 404
    return {"success": True, "data": asdict(kb)}


@knowledge_bp.route("/<kb_id>", methods=["PUT"])
@require_auth
async def update_kb(kb_id: str) -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return {"success": False, "message": "No knowledge base backend loaded."}, 501
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    kb = await store.update_kb(
        kb_id=kb_id,
        name=str(body.get("name", "")).strip() or None,
        description=str(body.get("description", "")) or None,
    )
    if kb is None:
        return {"success": False, "message": f"Knowledge base {kb_id!r} not found."}, 404
    return {"success": True, "data": asdict(kb)}


@knowledge_bp.route("/<kb_id>", methods=["DELETE"])
@require_auth
async def delete_kb(kb_id: str) -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return {"success": False, "message": "No knowledge base backend loaded."}, 501
    deleted = await store.delete_kb(kb_id)
    if not deleted:
        return {"success": False, "message": f"Knowledge base {kb_id!r} not found."}, 404
    return {"success": True}


# ---------------------------------------------------------------------------
# 文档管理
# ---------------------------------------------------------------------------


@knowledge_bp.route("/<kb_id>/documents", methods=["GET"])
@require_auth
async def list_documents(kb_id: str) -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return {"success": False, "message": "No knowledge base backend loaded."}, 501
    docs = await store.list_documents(kb_id)
    return {"success": True, "data": [asdict(d) for d in docs]}


@knowledge_bp.route("/<kb_id>/documents", methods=["POST"])
@require_auth
async def upload_document(kb_id: str) -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return {"success": False, "message": "No knowledge base backend loaded."}, 501
    files = await request.files
    f = files.get("file")
    if f is None:
        return {"success": False, "message": "No file provided."}, 400
    content = await f.read()
    doc = await store.add_document(kb_id, f.filename or "upload", content)
    return {"success": True, "data": asdict(doc)}, 201


@knowledge_bp.route("/<kb_id>/documents/<doc_id>", methods=["DELETE"])
@require_auth
async def delete_document(kb_id: str, doc_id: str) -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return {"success": False, "message": "No knowledge base backend loaded."}, 501
    deleted = await store.delete_document(kb_id, doc_id)
    if not deleted:
        return {"success": False, "message": "Document not found."}, 404
    return {"success": True}


# ---------------------------------------------------------------------------
# 检索
# ---------------------------------------------------------------------------


@knowledge_bp.route("/<kb_id>/search", methods=["POST"])
@require_auth
async def search(kb_id: str) -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return {"success": False, "message": "No knowledge base backend loaded."}, 501
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    query = str(body.get("query", "")).strip()
    if not query:
        return {"success": False, "message": "query is required."}, 400
    results = await store.search(
        kb_id,
        query=query,
        top_k=int(body.get("top_k", 5)),
        score_threshold=float(body.get("score_threshold", 0.0)),
    )
    return {"success": True, "data": [asdict(r) for r in results]}


@knowledge_bp.route("/search", methods=["POST"])
@require_auth
async def search_multi() -> tuple[dict, int] | dict:
    store = _store()
    if store is None:
        return {"success": False, "message": "No knowledge base backend loaded."}, 501
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    kb_ids = body.get("kb_ids", [])
    if not isinstance(kb_ids, list) or not kb_ids:
        return {"success": False, "message": "kb_ids must be a non-empty list."}, 400
    query = str(body.get("query", "")).strip()
    if not query:
        return {"success": False, "message": "query is required."}, 400
    results = await store.search_multi(
        kb_ids,
        query=query,
        top_k=int(body.get("top_k", 5)),
    )
    return {"success": True, "data": [asdict(r) for r in results]}
