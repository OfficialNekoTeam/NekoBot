"""知识库数据模型

定义知识库、文档、分块等数据模型
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class KnowledgeBase:
    """知识库数据模型
    
    表示一个知识库
    """
    
    id: str
    """知识库 ID（唯一标识符）"""
    
    name: str
    """知识库名称"""
    
    description: str
    """知识库描述"""
    
    embedding_model: str = "openai"
    """嵌入模型名称"""
    
    created_at: datetime
    """创建时间"""
    
    document_count: int = 0
    """文档数量"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "embedding_model": self.embedding_model,
            "created_at": self.created_at.isoformat(),
            "document_count": self.document_count,
        }


@dataclass
class Document:
    """文档数据模型"""
    
    id: str
    """文档 ID"""
    
    kb_id: str
    """所属知识库 ID"""
    
    title: str = ""
    """文档标题"""
    
    content: str
    """文档内容"""
    
    source: str = "manual"
    """文档来源（manual/manual/upload/等）"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """文档元数据"""
    
    chunk_count: int = 1
    """分块数量"""
    
    created_at: datetime
    """创建时间"""
    
    updated_at: Optional[datetime] = None
    """更新时间"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "kb_id": self.kb_id,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "metadata": self.metadata,
            "chunk_count": self.chunk_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class DocumentChunk:
    """文档分块数据模型"""
    
    id: str
    """分块 ID"""
    
    document_id: str
    """所属文档 ID"""
    
    content: str
    """分块内容"""
    
    chunk_index: int = 0
    """分块索引"""
    
    embedding: Optional[List[float]] = None
    """向量嵌入（可选）"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """分块元数据"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "content": self.content,
            "chunk_index": self.chunk_index,
            "metadata": self.metadata,
        }


@dataclass
class ChunkingStrategy:
    """分块策略配置"""
    
    type: str = "fixed"
    """策略类型：fixed/recursive"""
    
    chunk_size: int = 500
    """分块大小（字符数）"""
    
    chunk_overlap: int = 50
    """分块重叠（字符数）"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }