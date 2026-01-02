"""NekoBot 会话管理

实现会话/对话分离，支持对话切换
"""

from .manager import (
    Conversation,
    Session,
    ConversationManager,
    SessionDeletedCallback,
)

__all__ = [
    "Conversation",
    "Session",
    "ConversationManager",
    "SessionDeletedCallback",
]
