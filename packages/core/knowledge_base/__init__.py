"""向量数据库系统

提供向量数据库的统一接口
"""

from .base import VectorDatabase, DocumentChunk, SearchResult
from .chunking import ChunkingStrategy, FixedSizeChunker, RecursiveChunker

__all__ = [
    "VectorDatabase",
    "DocumentChunk",
    "SearchResult",
    "ChunkingStrategy",
    "FixedSizeChunker",
    "RecursiveChunker",
]