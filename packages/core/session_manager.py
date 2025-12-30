"""会话管理模块

提供会话历史、上下文压缩、会话总结等功能
"""

import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger
from .database import BaseDatabase
from .session_isolation import SessionIsolationManager


class SessionMessage:
    """会话消息"""

    def __init__(
        self,
        role: str,
        content: str,
        timestamp: float,
        metadata: Dict[str, Any] = None
    ):
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now().timestamp()
        self.metadata = metadata or {}


class ConversationSession:
    """会话"""

    def __init__(
        self,
        session_id: str,
        platform_id: str,
        user_id: str,
        created_at: float,
        updated_at: float,
        messages: List[SessionMessage] = None,
        summary: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ):
        self.session_id = session_id
        self.platform_id = platform_id
        self.user_id = user_id
        self.created_at = created_at or datetime.now().timestamp()
        self.updated_at = updated_at or datetime.now().timestamp()
        self.messages = messages or []
        self.summary = summary
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "platform_id": self.platform_id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.__dict__ for m in (self.messages or [])],
            "summary": self.summary,
            "metadata": self.metadata
        }


class CompressionStrategy:
    """上下文压缩策略"""
    NONE = "none"
    FIFO = "fifo"
    LRU = "lru"
    SUMMARY = "summary"


class CompressionConfig:
    """上下文压缩配置"""
    strategy: CompressionStrategy = CompressionStrategy.FIFO
    max_messages: int = 20
    min_messages: int = 4
    summary_threshold: int = 150


class SessionManager:
    """会话管理器 - 支持会话隔离"""

    def __init__(self, db: BaseDatabase, config: Dict[str, Any], isolation_manager: Optional[SessionIsolationManager] = None):
        """初始化会话管理器

        Args:
            db: 数据库实例
            config: 配置字典
            isolation_manager: 会话隔离管理器（可选）
        """
        self.db = db
        self.config = config or CompressionConfig()
        self.isolation_manager = isolation_manager

        # 初始化数据库表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL UNIQUE,
                platform_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                summary TEXT,
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS session_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                metadata TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_session_session_id ON sessions(session_id);
            CREATE INDEX IF NOT EXISTS idx_session_user ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_session_platform ON sessions(platform_id);
        """)

        # 初始化会话隔离管理器
        if self.isolation_manager:
            self.isolation_manager.initialize(self.db)

        logger.info("会话管理器初始化完成")

    def create_session(
        self,
        platform_id: str,
        user_id: str,
        summary: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> ConversationSession:
        """创建新会话

        Args:
            platform_id: 平台 ID
            user_id: 用户 ID
            summary: 会话总结
            metadata: 元数据

        Returns:
            ConversationSession 对象
        """
        session_id = f"{platform_id}:{user_id}:{uuid.uuid4().hex[:8]}"
        now = datetime.now().timestamp()

        # 检查会话隔离
        is_isolated = False
        if self.isolation_manager:
            key = self.isolation_manager.get_isolation_key(platform_id, user_id, None)
            is_isolated = not self.isolation_manager.check_isolation(key, session_id)

        try:
            self.db.execute(
                "INSERT INTO sessions (session_id, platform_id, user_id, created_at, updated_at, summary, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, platform_id, user_id, now, now, summary, json.dumps(metadata) if metadata else None)
            )
            logger.info(f"创建会话: {session_id}, 隔离: {is_isolated}")
            return ConversationSession(session_id, platform_id, user_id, now, [], summary, metadata)
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            raise

    def get_session(
        self,
        session_id: str
    ) -> Optional[ConversationSession]:
        """获取会话

        Args:
            session_id: 会话 ID

        Returns:
            ConversationSession 对象，不存在返回 None
        """
        try:
            rows = self.db.execute(
                "SELECT * FROM sessions WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
                (session_id,)
            )
            if rows:
                row = rows[0]
                messages = self._load_session_messages(row[0])
                return ConversationSession(
                    session_id=row["session_id"],
                    platform_id=row["platform_id"],
                    user_id=row["user_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    messages=messages,
                    summary=row["summary"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None
                )
            return None
        except Exception as e:
            logger.error(f"获取会话失败: {e}")
            return None

    def get_or_create_session(
        self,
        platform_id: str,
        user_id: str,
    ) -> ConversationSession:
        """获取或创建会话（如果不存在则创建）

        Args:
            platform_id: 平台 ID
            user_id: 用户 ID

        Returns:
            ConversationSession 对象
        """
        session = self.get_session(f"{platform_id}:{user_id}")
        if not session:
            session = self.create_session(platform_id, user_id)
        return session

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> None:
        """添加消息到会话

        Args:
            session_id: 会话 ID
            role: 角色（user/assistant/system）
            content: 消息内容
            metadata: 元数据
        """
        # 获取或创建会话
        self.get_or_create_session(session_id.split(":")[0], session_id.split(":")[1])

        try:
            self.db.execute(
                "INSERT INTO session_messages (session_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, datetime.now().timestamp(), json.dumps(metadata) if metadata else None)
            )
            logger.debug(f"添加消息到会话 {session_id}")
        except Exception as e:
            logger.error(f"添加消息失败: {e}")
            raise

    def get_session_messages(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[SessionMessage]:
        """获取会话消息

        Args:
            session_id: 会话 ID
            limit: 消息数量限制

        Returns:
            消息列表
        """
        try:
            rows = self.db.execute(
                f"SELECT role, content, timestamp, metadata FROM session_messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT {limit}",
                (session_id,)
            )
            messages = []
            for row in rows:
                messages.append(SessionMessage(
                    role=row["role"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None
                ))
            return messages
        except Exception as e:
            logger.error(f"获取会话消息失败: {e}")
            return []

    def update_session_summary(
        self,
        session_id: str,
        summary: str
    ) -> bool:
        """更新会话总结

        Args:
            session_id: 会话 ID
            summary: 会话总结

        Returns:
            是否成功
        """
        try:
            now = datetime.now().timestamp()
            self.db.execute(
                "UPDATE sessions SET summary = ?, updated_at = ? WHERE session_id = ?",
                (summary, now, session_id)
            )
            logger.info(f"更新会话总结: {session_id}")
            return True
        except Exception as e:
            logger.error(f"更新会话总结失败: {e}")
            return False

    def get_user_sessions(
        self,
        user_id: str,
        platform_id: Optional[str] = None
    ) -> List[ConversationSession]:
        """获取用户的所有会话

        Args:
            user_id: 用户 ID
            platform_id: 平台 ID（可选）

        Returns:
            会话列表
        """
        try:
            if platform_id:
                rows = self.db.execute(
                    "SELECT * FROM sessions WHERE user_id = ? AND platform_id = ? ORDER BY created_at DESC",
                    (user_id, platform_id)
                )
            else:
                rows = self.db.execute(
                    "SELECT * FROM sessions WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,)
                )
            sessions = []
            for row in rows:
                messages = self._load_session_messages(row["id"])
                sessions.append(ConversationSession(
                    session_id=row["session_id"],
                    platform_id=row["platform_id"],
                    user_id=row["user_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    messages=messages,
                    summary=row["summary"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None
                ))
            return sessions
        except Exception as e:
            logger.error(f"获取用户会话失败: {e}")
            return []

    def delete_session(
        self,
        session_id: str
    ) -> bool:
        """删除会话

        Args:
            session_id: 会话 ID

        Returns:
            是否成功
        """
        try:
            # 检查会话隔离
            if self.isolation_manager:
                key = self.isolation_manager.get_isolation_key(session_id.split(":")[0], session_id.split(":")[1], None)
                if self.isolation_manager.check_isolation(key, session_id):
                    logger.info(f"会话 {session_id} 是隔离的，跳过删除检查")
                    # 对于隔离会话，不需要特殊处理
                    pass
                else:
                    logger.warning(f"会话 {session_id} 不是隔离的，继续删除")

            # 删除会话消息
            self.db.execute("DELETE FROM session_messages WHERE session_id = ?", (session_id,))
            # 删除会话
            self.db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            logger.info(f"删除会话 {session_id}")
            return True
        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            return False

    def _load_session_messages(self, session_db_id: int) -> List[SessionMessage]:
        """从数据库加载会话消息"""
        try:
            rows = self.db.execute(
                "SELECT role, content, timestamp, metadata FROM session_messages WHERE session_id = ? ORDER BY timestamp ASC",
                (session_db_id,)
            )
            messages = []
            for row in rows:
                messages.append(SessionMessage(
                    role=row["role"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None
                ))
            return messages
        except Exception:
            return []
