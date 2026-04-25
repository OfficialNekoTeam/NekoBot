from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeBase:
    id: str
    name: str
    description: str = ""
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 512
    chunk_overlap: int = 64
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeDocument:
    id: str
    kb_id: str
    filename: str
    content_hash: str
    chunk_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    document_id: str
    chunk_index: int
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeStore(ABC):
    """Protocol for knowledge base backends.

    Implement this ABC in a plugin and assign to ``framework.knowledge_store``
    during plugin load. The API layer will proxy requests to whatever
    implementation is registered at runtime.

    Data layout (suggested, backend may differ):
        data/knowledge/<kb_id>/          — index files
        data/knowledge/<kb_id>/meta.json — KnowledgeBase metadata
    """

    # ------------------------------------------------------------------
    # Knowledge base lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    async def create_kb(
        self,
        kb_id: str,
        name: str,
        description: str = "",
        embedding_model: str = "text-embedding-3-small",
    ) -> KnowledgeBase: ...

    @abstractmethod
    async def update_kb(
        self,
        kb_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> KnowledgeBase | None: ...

    @abstractmethod
    async def delete_kb(self, kb_id: str) -> bool: ...

    @abstractmethod
    async def list_kbs(self) -> list[KnowledgeBase]: ...

    @abstractmethod
    async def get_kb(self, kb_id: str) -> KnowledgeBase | None: ...

    # ------------------------------------------------------------------
    # Document management
    # ------------------------------------------------------------------

    @abstractmethod
    async def add_document(
        self,
        kb_id: str,
        filename: str,
        content: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeDocument: ...

    @abstractmethod
    async def delete_document(self, kb_id: str, doc_id: str) -> bool: ...

    @abstractmethod
    async def list_documents(self, kb_id: str) -> list[KnowledgeDocument]: ...

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    @abstractmethod
    async def search(
        self,
        kb_id: str,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> list[SearchResult]: ...

    @abstractmethod
    async def search_multi(
        self,
        kb_ids: list[str],
        query: str,
        top_k: int = 5,
    ) -> list[SearchResult]: ...
