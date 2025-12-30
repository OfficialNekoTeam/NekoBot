"""文档解析器基类

定义所有文档解析器的基类接口
"""

from abc import ABC, abstractmethod
from typing import List
from pathlib import Path


class BaseParser(ABC):
    """文档解析器基类
    
    所有文档解析器都应该继承此类并实现 parse 方法
    """

    @abstractmethod
    def parse(self, file_path: Path) -> str:
        """解析文档内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            解析后的文本内容
        """
        pass

    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        """检查是否支持该文件类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否支持
        """
        pass

    def get_chunks(self, content: str, chunk_size: int, chunk_overlap: int) -> List[str]:
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
            end = start + chunk_size
            chunk = content[start:end]
            chunks.append(chunk)
            start = end - chunk_overlap
        
        return chunks