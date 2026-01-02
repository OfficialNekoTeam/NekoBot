"""NekoBot 会话管理

实现会话/对话分离，支持对话切换
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Awaitable, Any
from pathlib import Path
import json
import uuid
from loguru import logger

from ..types import MessageChain


# ============== 会话和对话 ==============

@dataclass
class Conversation:
    """对话

    表示一次完整的对话，包含消息历史
    """
    conversation_id: str
    session_id: str
    title: str
    messages: list[dict[str, str]] = field(default_factory=list)
    persona_id: str | None = None
    kb_ids: list[str] = field(default_factory=list)  # 关联的知识库
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: str | MessageChain) -> None:
        """添加消息

        Args:
            role: 角色 (user/assistant/system)
            content: 消息内容
        """
        text = content.text_content if isinstance(content, MessageChain) else content
        self.messages.append({
            "role": role,
            "content": text
        })
        self.updated_at = datetime.now()

    def to_llm_messages(self) -> list[dict[str, str]]:
        """转换为 LLM 消息格式"""
        return [
            {
                "role": msg["role"],
                "content": msg["content"]
            }
            for msg in self.messages
        ]

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "conversation_id": self.conversation_id,
            "session_id": self.session_id,
            "title": self.title,
            "messages": self.messages,
            "persona_id": self.persona_id,
            "kb_ids": self.kb_ids,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Conversation":
        """从字典创建"""
        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now()
        updated_at = datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now()

        return cls(
            conversation_id=data["conversation_id"],
            session_id=data["session_id"],
            title=data["title"],
            messages=data.get("messages", []),
            persona_id=data.get("persona_id"),
            kb_ids=data.get("kb_ids", []),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            updated_at=updated_at,
        )


@dataclass
class Session:
    """会话

    表示一个对话窗口（如群聊、私聊）
    一个会话可以有多个对话
    """
    session_id: str  # unified_id
    platform_id: str
    channel_id: str
    user_id: str
    current_conversation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def unified_id(self) -> str:
        """统一 ID"""
        return f"{self.platform_id}:{self.channel_id}:{self.user_id}"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "platform_id": self.platform_id,
            "channel_id": self.channel_id,
            "user_id": self.user_id,
            "current_conversation_id": self.current_conversation_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """从字典创建"""
        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now()

        return cls(
            session_id=data["session_id"],
            platform_id=data["platform_id"],
            channel_id=data["channel_id"],
            user_id=data["user_id"],
            current_conversation_id=data.get("current_conversation_id"),
            metadata=data.get("metadata", {}),
            created_at=created_at,
        )


# ============== 会话管理器 ==============

SessionDeletedCallback = Callable[[str], Awaitable[None]]


class ConversationManager:
    """会话管理器

    负责管理会话和对话
    """

    def __init__(self, storage_path: str | None = None):
        """初始化会话管理器

        Args:
            storage_path: 存储路径，默认为 data/conversations/
        """
        self._sessions: dict[str, Session] = {}
        self._conversations: dict[str, Conversation] = {}
        self._on_session_deleted_callbacks: list[SessionDeletedCallback] = []

        # 存储路径
        if storage_path is None:
            storage_path = "data/conversations"
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._sessions_file = self.storage_path / "sessions.json"
        self._conversations_dir = self.storage_path / "conversations"
        self._conversations_dir.mkdir(exist_ok=True)

    async def load(self) -> None:
        """加载会话和对话数据"""
        await self._load_sessions()
        await self._load_conversations()

    async def save(self) -> None:
        """保存会话和对话数据"""
        await self._save_sessions()
        await self._save_conversations()

    async def _load_sessions(self) -> None:
        """加载会话数据"""
        if not self._sessions_file.exists():
            return

        try:
            content = await self._read_file_async(self._sessions_file)
            data = json.loads(content)

            for session_data in data:
                session = Session.from_dict(session_data)
                self._sessions[session.session_id] = session

            logger.info(f"Loaded {len(self._sessions)} sessions")

        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")

    async def _save_sessions(self) -> None:
        """保存会话数据"""
        try:
            data = [s.to_dict() for s in self._sessions.values()]
            content = json.dumps(data, indent=2, ensure_ascii=False)
            await self._write_file_async(self._sessions_file, content)
        except Exception as e:
            logger.error(f"Failed to save sessions: {e}")

    async def _load_conversations(self) -> None:
        """加载对话数据"""
        for file_path in self._conversations_dir.glob("*.json"):
            try:
                content = await self._read_file_async(file_path)
                data = json.loads(content)

                conv = Conversation.from_dict(data)
                self._conversations[conv.conversation_id] = conv

            except Exception as e:
                logger.error(f"Failed to load conversation {file_path}: {e}")

        logger.info(f"Loaded {len(self._conversations)} conversations")

    async def _save_conversations(self) -> None:
        """保存对话数据"""
        # 清空现有文件
        for file_path in self._conversations_dir.glob("*.json"):
            try:
                file_path.unlink()
            except Exception:
                pass

        # 保存所有对话
        for conv in self._conversations.values():
            try:
                content = json.dumps(conv.to_dict(), indent=2, ensure_ascii=False)
                file_path = self._conversations_dir / f"{conv.conversation_id}.json"
                await self._write_file_async(file_path, content)
            except Exception as e:
                logger.error(f"Failed to save conversation {conv.conversation_id}: {e}")

    async def _read_file_async(self, file_path: Path) -> str:
        """异步读取文件"""
        import asyncio
        return await asyncio.to_thread(file_path.read_text, encoding='utf-8')

    async def _write_file_async(self, file_path: Path, content: str) -> None:
        """异步写入文件"""
        import asyncio
        await asyncio.to_thread(file_path.write_text, content, encoding='utf-8')

    def register_on_session_deleted(self, callback: SessionDeletedCallback) -> None:
        """注册会话删除回调"""
        self._on_session_deleted_callbacks.append(callback)

    async def _trigger_session_deleted(self, session_id: str) -> None:
        """触发会话删除回调"""
        for callback in self._on_session_deleted_callbacks:
            try:
                await callback(session_id)
            except Exception as e:
                logger.error(f"Session deleted callback error: {e}")

    def get_or_create_session(self, event: MessageEvent) -> Session:
        """获取或创建会话"""
        session_id = event.unified_id

        if session_id not in self._sessions:
            self._sessions[session_id] = Session(
                session_id=session_id,
                platform_id=event.platform_id,
                channel_id=event.channel_id,
                user_id=event.user_id
            )

        return self._sessions[session_id]

    async def new_conversation(
        self,
        session_id: str,
        title: str | None = None,
        persona_id: str | None = None
    ) -> Conversation:
        """创建新对话

        Args:
            session_id: 会话 ID
            title: 对话标题
            persona_id: 人设 ID

        Returns:
            新创建的对话
        """
        conv = Conversation(
            conversation_id=uuid.uuid4().hex[:16],
            session_id=session_id,
            title=title or "新对话",
            persona_id=persona_id
        )

        self._conversations[conv.conversation_id] = conv

        # 设置为当前对话
        if session_id in self._sessions:
            self._sessions[session_id].current_conversation_id = conv.conversation_id

        # 自动保存
        await self._save_conversations()

        logger.info(f"Created new conversation: {conv.conversation_id} for session: {session_id}")
        return conv

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        """获取对话"""
        return self._conversations.get(conversation_id)

    def get_current_conversation(self, session_id: str) -> Conversation | None:
        """获取当前对话"""
        session = self._sessions.get(session_id)
        if not session or not session.current_conversation_id:
            return None
        return self._conversations.get(session.current_conversation_id)

    def list_conversations(self, session_id: str) -> list[Conversation]:
        """列出会话的所有对话"""
        return [
            conv for conv in self._conversations.values()
            if conv.session_id == session_id
        ]

    async def switch_conversation(
        self,
        session_id: str,
        conversation_id: str
    ) -> bool:
        """切换对话

        Args:
            session_id: 会话 ID
            conversation_id: 目标对话 ID

        Returns:
            是否切换成功
        """
        if session_id not in self._sessions:
            return False
        if conversation_id not in self._conversations:
            return False

        self._sessions[session_id].current_conversation_id = conversation_id
        await self._save_sessions()

        logger.info(f"Switched to conversation: {conversation_id} for session: {session_id}")
        return True

    async def delete_conversation(self, conversation_id: str) -> bool:
        """删除对话

        Args:
            conversation_id: 对话 ID

        Returns:
            是否删除成功
        """
        if conversation_id not in self._conversations:
            return False

        conv = self._conversations.pop(conversation_id)

        # 如果是当前对话，清除引用
        for session in self._sessions.values():
            if session.current_conversation_id == conversation_id:
                session.current_conversation_id = None

        # 保存变更
        await self._save_sessions()
        await self._save_conversations()

        logger.info(f"Deleted conversation: {conversation_id}")
        return True

    async def delete_session(self, session_id: str) -> bool:
        """删除会话

        Args:
            session_id: 会话 ID

        Returns:
            是否删除成功
        """
        if session_id not in self._sessions:
            return False

        # 删除会话的所有对话
        conv_ids_to_delete = [
            conv_id for conv_id, conv in self._conversations.items()
            if conv.session_id == session_id
        ]
        for conv_id in conv_ids_to_delete:
            await self.delete_conversation(conv_id)

        # 删除会话
        del self._sessions[session_id]

        # 触发回调
        await self._trigger_session_deleted(session_id)

        # 保存变更
        await self._save_sessions()

        logger.info(f"Deleted session: {session_id}")
        return True


# ============== 导出 ==============

__all__ = [
    "Conversation",
    "Session",
    "ConversationManager",
    "SessionDeletedCallback",
]
