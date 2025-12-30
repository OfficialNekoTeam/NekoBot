"""上下文管理模块

提供会话上下文的持久化存储、压缩和管理功能
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from loguru import logger
from .database import BaseDatabase


class CompressionStrategy(Enum):
    """上下文压缩策略"""
    NONE = "none"
    FIFO = "fifo"
    LRU = "lru"
    SUMMARY = "summary"


@dataclass
class CompressionConfig:
    """上下文压缩配置"""
    strategy: CompressionStrategy = CompressionStrategy.FIFO
    max_messages: int = 20
    min_messages: int = 4
    summary_threshold: int = 150


class ContextManager:
    """上下文管理器 - 支持持久化存储"""

    def __init__(self, db: BaseDatabase, config: CompressionConfig = None):
        """初始化上下文管理器

        Args:
            db: 数据库实例
            config: 压缩配置
        """
        self.db = db
        self.config = config or CompressionConfig()

        # 从数据库加载所有上下文
        self.contexts: Dict[str, List[Dict[str, Any]]] = {}
        self._load_contexts_from_db()

    def _load_contexts_from_db(self) -> None:
        """从数据库加载所有上下文"""
        try:
            rows = self.db.execute("SELECT id, session_id, platform_id, user_id, data FROM contexts ORDER BY created_at DESC")
            for row in rows:
                context_id = row["id"]
                session_id = row["session_id"]
                try:
                    data = json.loads(row["data"]) if row["data"] else {}
                except Exception:
                    data = {}
                self.contexts[context_id] = {
                    "id": context_id,
                    "session_id": session_id,
                    "platform_id": row["platform_id"],
                    "user_id": row["user_id"],
                    "messages": data.get("messages", [])
                }
            logger.info(f"从数据库加载了 {len(self.contexts)} 个上下文")
        except Exception as e:
            logger.error(f"从数据库加载上下文失败: {e}")

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> None:
        """添加消息到上下文并持久化

        Args:
            session_id: 会话 ID
            role: 角色
            content: 消息内容
            metadata: 元数据
        """
        # 获取或创建上下文
        context = self.contexts.get(session_id)
        if not context:
            # 如果上下文不存在，创建新上下文
            try:
                self.db.execute(
                    "INSERT INTO contexts (session_id, platform_id, user_id, data) VALUES (?, ?, ?, ?)",
                    (session_id, "", "", json.dumps({"messages": []}))
                )
                context_id = self.db.last_insert_rowid()
                context_id = self.db.last_insert_rowid()
                self.contexts[context_id] = {
                    "id": context_id,
                    "session_id": session_id,
                    "platform_id": "",
                    "user_id": "",
                    "messages": []
                }
                logger.info(f"创建新上下文: {context_id}")
            except Exception as e:
                logger.error(f"创建上下文失败: {e}")
                raise

        # 添加消息到上下文
        message_dict = {
            "role": role,
            "content": content,
            "timestamp": metadata.get("timestamp", ""),
            "metadata": {k: v for k, v in metadata.items() if k not in ["role", "content", "timestamp"]}
        }
        context["messages"].append(message_dict)

        # 应用压缩策略
        self._apply_compression(context_id)

        # 持久化保存到数据库
        self._save_context_to_db(context_id)

    def get_context(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取会话上下文

        Args:
            session_id: 会话 ID
            limit: 消息数量限制

        Returns:
            上下文列表
        """
        context = self.contexts.get(session_id)
        if not context:
            return []

        messages = context.get("messages", [])

        if limit is not None and len(messages) > limit:
            messages = messages[-limit:]

        return messages

    def _apply_compression(self, context_id: str) -> None:
        """应用压缩策略"""
        context = self.contexts.get(context_id)
        if not context:
            return

        messages = context.get("messages", [])
        strategy = self.config.strategy
        max_messages = self.config.max_messages
        min_messages = self.config.min_messages

        if strategy == CompressionStrategy.NONE:
            pass
        elif strategy == CompressionStrategy.FIFO:
            if len(messages) > max_messages:
                messages = messages[-max_messages:]
        elif strategy == CompressionStrategy.LRU:
            # LRU 简化实现：保留所有消息
            pass
        elif strategy == CompressionStrategy.SUMMARY:
            # 会话总结替代
            pass

        # 确保至少保留 min_messages 条
        if len(messages) < min_messages:
            pass

        # 更新内存中的上下文
        context["messages"] = messages

    def _save_context_to_db(self, context_id: str) -> None:
        """保存上下文到数据库"""
        context = self.contexts.get(context_id)
        if not context:
            return

        try:
            self.db.execute(
                "UPDATE contexts SET data = ? WHERE id = ?",
                (json.dumps(context), context["id"])
            )
            logger.debug(f"保存上下文 {context_id} 到数据库")
        except Exception as e:
            logger.error(f"保存上下文到数据库失败: {e}")
            raise

    def clear_context(self, session_id: str) -> None:
        """清除会话上下文"""
        if session_id in self.contexts:
            del self.contexts[session_id]
            # 从数据库删除
            try:
                context_id_obj = self.db.execute(
                    "SELECT id FROM contexts WHERE session_id = ?",
                    (session_id,)
                )
                if context_id_obj:
                    self.db.execute("DELETE FROM contexts WHERE id = ?", (context_id_obj[0],))
                    logger.info(f"清除会话 {session_id} 的上下文")
            except Exception as e:
                logger.error(f"清除上下文失败: {e}")
                raise

    def get_context_stats(self, session_id: str) -> Dict[str, int]:
        """获取上下文统计信息

        Args:
            session_id: 会话 ID

        Returns:
            统计信息
        """
        context = self.contexts.get(session_id)
        if not context:
            return {"total_messages": 0, "user_messages": 0}

        messages = context.get("messages", [])
        return {
            "total_messages": len(messages),
            "user_messages": len([m for m in messages if m["role"] == "user"]),
            "assistant_messages": len([m for m in messages if m["role"] == "assistant"]),
        }
