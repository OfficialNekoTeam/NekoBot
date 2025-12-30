"""文档分块策略基类

定义所有分块策略的基类接口
"""

from abc import ABC, abstractmethod
from typing import List


class BaseChunker(ABC):
    """分块策略基类
    
    所有分块策略都应该继承此类并实现 get_chunks 方法
    """

    @abstractmethod
    async def get_chunks(
        self,
        content: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> List[str]:
        """将内容分块
        
        Args:
            content: 文档内容
            chunk_size: 分块大小（字符数）
            chunk_overlap: 重叠大小（字符数）
            
        Returns:
            分块后的文本列表
        """
        pass

    @abstractmethod
    def get_config(self) -> dict:
        """获取分块配置
        
        Returns:
            分块配置字典
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}"