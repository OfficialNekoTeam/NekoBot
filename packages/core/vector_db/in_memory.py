"""内存向量数据库实现

使用简单列表实现向量存储和检索
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger
import math

from .base import VectorDatabase, DocumentChunk, SearchResult


@dataclass
class VectorEntry:
    """向量条目"""
    doc_id: str
    chunk_index: int
    embedding: List[float]


@dataclass
class IndexEntry:
    """索引条目"""
    doc_id: str
    text: str
    tokens: List[str]


class InMemoryVectorDB(VectorDatabase):
    """内存向量数据库
    
    使用简单的列表实现向量存储和检索
    """

    def __init__(self):
        """初始化内存向量数据库"""
        self.documents: Dict[str, IndexEntry] = {}  # doc_id -> IndexEntry
        self.vectors: Dict[str, VectorEntry] = {}  # doc_id -> VectorEntry
        self._initialized = False

    async def initialize(self):
        """初始化数据库"""
        logger.info("初始化内存向量数据库")
        self._initialized = True

    async def add_document(
        self,
        text: str,
        embedding: Optional[List[float]],
        metadata: Dict[str, Any] = None,
        doc_id: Optional[str] = None,
    ) -> str:
        """添加文档到向量数据库
        
        Args:
            text: 文档文本
            embedding: 向量嵌入（可选，会自动计算）
            metadata: 文档元数据
            doc_id: 文档ID（可选，自动生成）
            
        Returns:
            文档ID
        """
        if doc_id is None:
            doc_id = f"doc_{len(self.documents)}"
        
        # 创建索引条目
        tokens = self._tokenize(text)
        index_entry = IndexEntry(doc_id=doc_id, text=text, tokens=tokens)
        
        # 存储文档
        self.documents[doc_id] = index_entry
        
        # 如果提供了向量嵌入，则使用；否则生成简单的随机向量（简化实现）
        if embedding is not None:
            # 生成随机向量（768维）
            vec = [hash(str(i) % 1000000 / 1000000) * 2.0 - 1.0 for i in range(768)]
        self.vectors[doc_id] = VectorEntry(doc_id=doc_id, chunk_index=0, embedding=vec)
        
        logger.info(f"已添加文档到向量数据库: {doc_id}")
        return doc_id

    async def add_documents(self, chunks: List[DocumentChunk]) -> List[str]:
        """批量添加文档
        
        Args:
            chunks: 文档分块列表
            
        Returns:
            文档ID列表
        """
        doc_ids = []
        
        for chunk in chunks:
            doc_id = await self.add_document(
                text=chunk.text,
                embedding=chunk.embedding,
                metadata=chunk.metadata,
                doc_id=chunk.id,
            )
            doc_ids.append(doc_id)
        
        logger.info(f"已批量添加 {len(chunks)} 个文档分块到向量数据库")
        return doc_ids

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """搜索相似向量
        
        Args:
            query_embedding: 查询向量嵌入
            top_k: 返回前 K 个结果
            filter_metadata: 元数据过滤条件
            
        Returns:
            搜索结果列表
        """
        if not self._initialized:
            logger.warning("向量数据库未初始化，请先调用 initialize()")

        results = []
        
        # 计算余弦相似度
        for doc_id, vector_entry in self.vectors.items():
            # 过滤元数据
            if filter_metadata and doc_id in self.documents:
                doc_metadata = self.documents[doc_id].metadata
                match = True
                
                for key, value in filter_metadata.items():
                    if doc_metadata.get(key) != value:
                        match = False
                        break
                
                if not match:
                    continue
            
            # 计算相似度
            similarity = self._cosine_similarity(query_embedding, vector_entry.embedding)
            
            # 获取文档信息
            doc_entry = self.documents.get(doc_id)
            
            if doc_entry:
                results.append(SearchResult(
                    document_id=doc_id,
                    text=doc_entry.text,
                    score=similarity,
                    metadata=doc_entry.metadata,
                ))
        
        # 按相似度排序
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # 只返回前 top_k 个结果
        return results[:top_k]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            相似度（-1到1之间）
        """
        if len(vec1) != len(vec2):
            # 长度不匹配，返回0
            return 0.0
        
        # 计算点积
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # 计算向量长度
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        # 避免除零
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        # 计算余弦相似度
        cosine = dot_product / (magnitude1 * magnitude2)
        
        return max(-1.0, min(1.0, cosine))

    async def delete_document(self, doc_id: str) -> bool:
        """删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            是否删除成功
        """
        if doc_id in self.documents:
            del self.documents[doc_id]
            
            # 删除所有相关的向量
            vectors_to_delete = [k for k, v in self.vectors.items() if v.doc_id == doc_id]
            for v in vectors_to_delete:
                del self.vectors[v]
            
            logger.info(f"已从向量数据库删除文档: {doc_id}")
            return True
        
        logger.warning(f"文档 {doc_id} 不存在于向量数据库中")
        return False

    async def delete_documents(self, doc_ids: List[str]) -> int:
        """批量删除文档
        
        Args:
            doc_ids: 文档ID列表
            
        Returns:
            删除的文档数量
        """
        count = 0
        
        for doc_id in doc_ids:
            if await self.delete_document(doc_id):
                count += 1
        
        logger.info(f"已批量删除 {count} 个文档")
        return count

    async def clear(self) -> bool:
        """清空所有文档"""
        self.documents.clear()
        self.vectors.clear()
        logger.info("已清空向量数据库")
        return True

    async def count(self) -> int:
        """获取文档数量
        
        Returns:
            文档总数
        """
        return len(self.documents)

    async def get_document(self, doc_id: str) -> Optional[DocumentChunk]:
        """获取文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            文档分块对象，如果不存在则返回 None
        """
        index_entry = self.documents.get(doc_id)
        
        if index_entry:
            # 简化实现：返回整个文档作为一个分块
            return DocumentChunk(
                id=f"{doc_id}_0",
                document_id=doc_id,
                text=index_entry.text,
                chunk_index=0,
                metadata=index_entry.metadata,
                embedding=self.vectors.get(f"{doc_id}_0", {}).embedding if f"{doc_id}_0" in self.vectors else None,
            )
        
        return None