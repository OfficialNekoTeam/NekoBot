"""Markdown文档解析器"""

from ..base import BaseParser
from typing import List


class MarkdownParser(BaseParser):
    """Markdown文档解析器
    
    直接返回Markdown文本内容
    """

    def supports(self, file_path) -> bool:
        """检查是否支持该文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否支持（Markdown文件）
        """
        return file_path.suffix.lower() in [".md", ".markdown"]

    async def parse(self, file_path) -> str:
        """解析Markdown文档
        
        Args:
            file_path: 文件路径
            
        Returns:
            文档内容
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return content