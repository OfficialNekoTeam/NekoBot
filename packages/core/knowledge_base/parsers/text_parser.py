"""纯文本文档解析器"""

from ..base import BaseParser
from typing import List


class TextParser(BaseParser):
    """纯文本文档解析器
    
    直接处理纯文本内容，不需要特殊解析
    """

    def supports(self, file_path) -> bool:
        """检查是否支持该文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            总是支持（纯文本）
        """
        return True

    async def parse(self, file_path) -> str:
        """解析纯文本文档
        
        Args:
            file_path: 文件路径
            
        Returns:
            文档文本内容
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return content

    async def get_chunks(
        self,
        content: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> List[str]:
        """将内容分块
        
        Args:
            content: 文档内容
            chunk_size: 分块大小
            chunk_overlap: 重叠大小
            
        Returns:
            分块后的文本列表
        """
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + chunk_size
            chunks.append(content[start:end])
            start = end - chunk_overlap
        
        return chunks