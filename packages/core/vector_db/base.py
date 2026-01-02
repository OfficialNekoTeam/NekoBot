"""向量数据库基类

定义向量数据库的接口规范
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class DocumentChunk:
    """文档分块

    表示向量化后的文档片段
    """
    text: str
    """文档文本内容"""

    id: Optional[str] = None
    """文档 ID"""

    embedding: Optional[List[float]] = None
    """向量嵌入（可选）"""

    metadata: Dict[str, Any] = None
    """文档元数据"""

    source: Optional[str] = None
    """文档来源"""

    chunk_index: int = 0
    """分块索引"""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "text": self.text,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "source": self.source,
            "chunk_index": self.chunk_index,
        }


@dataclass
class SearchResult:
    """搜索结果

    表示向量搜索的结果
    """
    text: str
    """文档文本"""

    score: float
    """相似度分数"""

    document_id: Optional[str] = None
    """文档 ID"""

    metadata: Dict[str, Any] = None
    """文档元数据"""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "document_id": self.document_id,
            "text": self.text,
            "score": self.score,
            "metadata": self.metadata,
        }


class VectorDatabase(ABC):
    """向量数据库基类

    所有向量数据库实现都应该继承此类
    """

    @abstractmethod
    async def add_document(
        self,
        text: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        doc_id: Optional[str] = None,
    ) -> str:
        """添加文档到向量数据库

        Args:
            text: 文档文本
            embedding: 向量嵌入
            metadata: 元数据
            doc_id: 文档 ID（可选，自动生成）

        Returns:
            文档 ID
        """
        pass

    @abstractmethod
    async def add_documents(
        self,
        chunks: List[DocumentChunk],
    ) -> List[str]:
        """批量添加文档

        Args:
            chunks: 文档分块列表

        Returns:
            文档 ID 列表
        """
        pass

    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """搜索相似文档

        Args:
            query_embedding: 查询向量嵌入
            top_k: 返回前 K 个结果
            filter_metadata: 元数据过滤条件

        Returns:
            搜索结果列表
        """
        pass

    @abstractmethod
    async def delete_document(self, doc_id: str) -> bool:
        """删除文档

        Args:
            doc_id: 文档 ID

        Returns:
            是否删除成功
        """
        pass

    @abstractmethod
    async def delete_documents(self, doc_ids: List[str]) -> int:
        """批量删除文档

        Args:
            doc_ids: 文档 ID 列表

        Returns:
            删除的文档数量
        """
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """清空所有文档

        Returns:
            是否清空成功
        """
        pass

    @abstractmethod
    async def count(self) -> int:
        """获取文档数量

        Returns:
            文档总数
        """
        pass

    @abstractmethod
    async def get_document(
        self, doc_id: str
    ) -> Optional[DocumentChunk]:
        """获取文档

        Args:
            doc_id: 文档 ID

        Returns:
            文档对象，如果不存在则返回 None
        """
        pass
