"""文档分块策略"""

from .fixed_size import FixedSizeChunker
from .recursive import RecursiveChunker

__all__ = [
    "FixedSizeChunker",
    "RecursiveChunker",
]