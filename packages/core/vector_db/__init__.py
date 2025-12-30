"""向量数据库系统

提供向量数据库的统一接口
"""

from .base import VectorDatabase, DocumentChunk, SearchResult

__all__ = [
    "VectorDatabase",
    "DocumentChunk",
    "SearchResult",
]