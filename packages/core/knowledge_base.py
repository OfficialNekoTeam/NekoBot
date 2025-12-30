1"""知识库管理模块

提供文档的添加、检索、删除等功能，以及 RAG 检索集成
"""

import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from loguru import logger
from .database import BaseDatabase


@dataclass
class KnowledgeDocument:
    """知识库文档"""
    id: str
    title: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = None
    created_at: float
    updated_at: float
    tags: List[str] = None
    category: str = "general"


@dataclass
class KnowledgeBase:
    """知识库"""
    id: str
    name: str
    description: str
    created_at: float
    updated_at: float
    documents_count: int = 0
    embedding_model: str = "openai"
    api_key: str = ""
    api_endpoint: str = ""


@dataclass
class RetrievalResult:
    """检索结果"""
    query: str
    results: List[Dict[str, Any]]
    total_docs: int = 0
    retrieval_time: float = 0.0


class KnowledgeManager:
    """知识库管理器"""

    def __init__(self, db: BaseDatabase, config: Dict[str, Any]):
        """初始化知识库管理器

        Args:
            db: 数据库实例
            config: 配置字典
        """
        self.db = db
        self.config = config

        # 初始化数据库表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_bases (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                documents_count INTEGER DEFAULT 0,
                embedding_model TEXT DEFAULT 'openai',
                api_key TEXT,
                api_endpoint TEXT
            );

            CREATE TABLE IF NOT EXISTS knowledge_documents (
                id TEXT PRIMARY KEY,
                base_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding BLOB,
                metadata TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                tags TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_kb_docs_base ON knowledge_documents(base_id);
            CREATE INDEX IF NOT EXISTS idx_kb_docs_tags ON knowledge_documents(tags);
        """)
        logger.info("知识库管理器初始化完成")

    def create_knowledge_base(
        self,
        name: str,
        description: str,
        embedding_model: str = "openai",
        api_key: str = "",
        api_endpoint: str = ""
    ) -> KnowledgeBase:
        """创建知识库

        Args:
            name: 知识库名称
            description: 知识库描述
            embedding_model: 嵌入模型（openai/gemini/glm）
            api_key: API 密钥
            api_endpoint: API 端点

        Returns:
            KnowledgeBase 对象
        """
        base_id = f"kb_{uuid.uuid4().hex[:8]}"
        now = datetime.now().timestamp()

        try:
            self.db.execute(
                "INSERT INTO knowledge_bases (id, name, description, created_at, updated_at, documents_count, embedding_model, api_key, api_endpoint) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (base_id, name, description, now, now, 0, embedding_model, api_key, api_endpoint)
            )
            logger.info(f"创建知识库: {name}")
            return KnowledgeBase(
                id=base_id,
                name=name,
                description=description,
                created_at=now,
                updated_at=now,
                documents_count=0,
                embedding_model=embedding_model,
                api_key=api_key,
                api_endpoint=api_endpoint
            )
        except Exception as e:
            logger.error(f"创建知识库失败: {e}")
            raise

    def get_knowledge_base(self, base_id: str) -> Optional[KnowledgeBase]:
        """获取知识库"""
        try:
            rows = self.db.execute(
                "SELECT * FROM knowledge_bases WHERE id = ?",
                (base_id,)
            )
            if rows:
                row = rows[0]
                return KnowledgeBase(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    documents_count=row["documents_count"],
                    embedding_model=row["embedding_model"],
                    api_key="***",  # 不暴露密钥
                    api_endpoint=row["api_endpoint"]
                )
            return None
        except Exception as e:
            logger.error(f"获取知识库失败: {e}")
            return None

    def get_all_knowledge_bases(self) -> List[KnowledgeBase]:
        """获取所有知识库"""
        try:
            rows = self.db.execute("SELECT * FROM knowledge_bases ORDER BY created_at DESC")
            bases = []
            for row in rows:
                bases.append(KnowledgeBase(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    documents_count=row["documents_count"],
                    embedding_model=row["embedding_model"],
                    api_key="***",
                    api_endpoint=row["api_endpoint"]
                ))
            return bases
        except Exception as e:
            logger.error(f"获取知识库列表失败: {e}")
            return []

    def delete_knowledge_base(self, base_id: str) -> bool:
        """删除知识库"""
        try:
            # 删除文档
            self.db.execute("DELETE FROM knowledge_documents WHERE base_id = ?", (base_id,))
            # 删除知识库
            self.db.execute("DELETE FROM knowledge_bases WHERE id = ?", (base_id,))
            logger.info(f"删除知识库: {base_id}")
            return True
        except Exception as e:
            logger.error(f"删除知识库失败: {e}")
            return False

    def add_document(
        self,
        base_id: str,
        title: str,
        content: str,
        tags: List[str] = None,
        category: str = "general"
    ) -> KnowledgeDocument:
        """添加文档到知识库

        Args:
            base_id: 知识库 ID
            title: 文档标题
            content: 文档内容
            tags: 标签列表
            category: 文档类别

        Returns:
            KnowledgeDocument 对象
        """
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        now = datetime.now().timestamp()

        try:
            self.db.execute(
                "INSERT INTO knowledge_documents (id, base_id, title, content, created_at, updated_at, tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (doc_id, base_id, title, content, now, now, json.dumps(tags) if tags else None)
            )
            logger.info(f"添加文档到知识库 {base_id}")

            # 更新文档计数
            self.db.execute(
                "UPDATE knowledge_bases SET documents_count = documents_count + 1 WHERE id = ?",
                (base_id,)
            )

            return KnowledgeDocument(
                id=doc_id,
                base_id=base_id,
                title=title,
                content=content,
                created_at=now,
                updated_at=now,
                tags=tags or [],
                category=category
            )
        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            raise

    def retrieve(
        self,
        base_id: str,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.0,
        filters: Dict[str, Any] = None
    ) -> RetrievalResult:
        """检索文档

        Args:
            base_id: 知识库 ID
            query: 查询内容
            top_k: 返回结果数量
            min_similarity: 最小相似度
            filters: 过滤条件

        Returns:
            检索结果
        """
        start_time = datetime.now().timestamp()

        try:
            # 这里可以实现更复杂的检索逻辑
            # 简化实现：返回所有文档
            rows = self.db.execute(
                "SELECT id, title, content, tags FROM knowledge_documents WHERE base_id = ? LIMIT ?",
                (base_id, top_k)
            )

            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"],
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                    "category": "general",
                    "score": 0.0  # 简化实现，可以添加向量相似度
                })

            end_time = datetime.now().timestamp()
            retrieval_time = end_time - start_time

            return RetrievalResult(
                query=query,
                results=results,
                total_docs=len(results),
                retrieval_time=retrieval_time
            )
        except Exception as e:
            logger.error(f"检索失败: {e}")
            return RetrievalResult(
                query=query,
                results=[],
                total_docs=0,
                retrieval_time=0.0
            )

    def delete_document(self, base_id: str, doc_id: str) -> bool:
        """删除文档"""
        try:
            self.db.execute("DELETE FROM knowledge_documents WHERE id = ?", (doc_id,))

            # 更新文档计数
            self.db.execute(
                "UPDATE knowledge_bases SET documents_count = documents_count - 1 WHERE id = ?",
                (base_id,)
            )

            logger.info(f"删除文档 {doc_id}")
            return True
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False
