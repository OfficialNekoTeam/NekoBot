"""知识库管理器

统一管理向量数据库、文档解析、检索等知识库功能
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger

from .base import VectorDatabase
from .models import KnowledgeBase, Document


class KnowledgeBaseManager:
    """知识库管理器
    
    统一管理知识库的所有功能
    """

    def __init__(self, vector_db: Optional[VectorDatabase]):
        """初始化知识库管理器
        
        Args:
            vector_db: 向量数据库实例
        """
        self.vector_db = vector_db
        self._knowledge_bases: Dict[str, KnowledgeBase] = {}

    async def create_knowledge_base(
        self,
        kb_id: str,
        name: str,
        description: str = "",
        embedding_model: str = "openai",
    ) -> str:
        """创建知识库
        
        Args:
            kb_id: 知识库 ID
            name: 知识库名称
            description: 知识库描述
            embedding_model: 嵌入模型名称
            
        Returns:
            知识库 ID
        """
        kb = KnowledgeBase(
            id=kb_id,
            name=name,
            description=description,
            embedding_model=embedding_model,
        )
        
        self._knowledge_bases[kb_id] = kb
        logger.info(f"已创建知识库: {name} ({kb_id})")
        return kb_id

    async def delete_knowledge_base(self, kb_id: str) -> bool:
        """删除知识库
        
        Args:
            kb_id: 知识库 ID
            
        Returns:
            是否成功删除
        """
        if kb_id not in self._knowledge_bases:
            logger.warning(f"知识库 {kb_id} 不存在")
            return False
        
        del self._knowledge_bases[kb_id]
        
        # 清空向量数据库中的相关文档
        if self.vector_db:
            await self.vector_db.clear()
        
        logger.info(f"已删除知识库: {kb_id}")
        return True

    async def get_knowledge_base(self, kb_id: str) -> Optional[KnowledgeBase]:
        """获取知识库
        
        Args:
            kb_id: 知识库 ID
            
        Returns:
            知识库对象，如果不存在则返回 None
        """
        return self._knowledge_bases.get(kb_id)

    async def list_knowledge_bases(self) -> List[KnowledgeBase]:
        """列出所有知识库
        
        Returns:
            知识库列表
        """
        return list(self._knowledge_bases.values())

    async def add_document(
        self,
        kb_id: str,
        text: str,
        metadata: Dict[str, Any],
    ) -> str:
        """添加文档到知识库
        
        Args:
            kb_id: 知识库 ID
            text: 文档文本
            metadata: 文档元数据
            
        Returns:
            文档 ID
        """
        if kb_id not in self._knowledge_bases:
            logger.warning(f"知识库 {kb_id} 不存在")
            return ""
        
        # 这里简化实现，实际应该调用向量数据库添加文档
        doc_id = f"doc_{kb_id}_{len(text)}"
        logger.info(f"已添加文档到知识库 {kb_id}: {doc_id}")
        return doc_id

    async def search(
        self,
        kb_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """搜索知识库
        
        Args:
            kb_id: 知识库 ID
            query: 查询文本
            top_k: 返回前 K 个结果
            
        Returns:
            搜索结果列表
        """
        if kb_id not in self._knowledge_bases:
            logger.warning(f"知识库 {kb_id} 不存在")
            return []
        
        # 这里简化实现，实际应该调用向量数据库搜索
        logger.info(f"在知识库 {kb_id} 中搜索: {query}")
        return [
            {
                "document_id": f"doc_{kb_id}_1",
                "text": f"示例文档内容: {query}",
                "score": 0.95,
            }
        ]

    async def delete_document(self, kb_id: str, doc_id: str) -> bool:
        """删除文档
        
        Args:
            kb_id: 知识库 ID
            doc_id: 文档 ID
            
        Returns:
            是否成功删除
        """
        if kb_id not in self._knowledge_bases:
            logger.warning(f"知识库 {kb_id} 不存在")
            return False
        
        logger.info(f"已从知识库 {kb_id} 中删除文档: {doc_id}")
        return True

    async def get_document_count(self, kb_id: str) -> int:
        """获取知识库中的文档数量
        
        Args:
            kb_id: 知识库 ID
            
        Returns:
            文档数量
        """
        if kb_id not in self._knowledge_bases:
            return 0
        return 0  # 简化实现


# 创建全局知识库管理器实例
kb_manager: Optional[KnowledgeBaseManager] = None


def get_kb_manager() -> KnowledgeBaseManager:
    """获取或创建全局知识库管理器实例
    
    Returns:
        知识库管理器实例
    """
    global kb_manager
    if kb_manager is None:
        kb_manager = KnowledgeBaseManager(vector_db=None)
    return kb_manager