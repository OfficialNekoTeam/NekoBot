"""固定大小分块策略

按固定大小将文档分块
"""

from ..base import BaseChunker
from typing import List


class FixedSizeChunker(BaseChunker):
    """固定大小分块器
    
    将文档按固定大小分块，可配置重叠字符数
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """初始化分块器
        
        Args:
            chunk_size: 分块大小（字符数）
            chunk_overlap: 重叠大小（字符数）
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def get_chunks(
        self,
        content: str,
    ) -> List[str]:
        """将内容分块
        
        Args:
            content: 文档内容
            chunk_size: 分块大小（字符数）
            chunk_overlap: 重叠大小（字符数）
            
        Returns:
            分块后的文本列表
        """
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + self.chunk_size
            chunk = content[start:end]
            chunks.append(chunk)
            start = end - self.chunk_overlap
        
        return chunks

    def get_config(self) -> dict:
        """获取分块配置
        
        Returns:
            分块配置字典
        """
        return {
            "type": "fixed_size",
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }