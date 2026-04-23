"""Shared types, constants, and dataclasses for the LLM handler."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..conversations.context import ConfigurationContext, ConversationContext
    from ..runtime.context import ExecutionContext

_DEFAULT_HISTORY_LIMIT = 20
_COMPRESS_KEEP_TURNS = 5
_SUMMARIZE_PROMPT = (
    "请将以下对话历史简洁地总结成几句话，保留关键信息和结论，"
    "不要包含无关细节。总结用中文输出。\n\n对话历史：\n{history}"
)

_PREF_ENABLED = "reply_enabled"
_PREF_MODEL = "preferred_model"
_PREF_PROVIDER = "preferred_provider"
_PREF_GROUP_ENABLED = "group_reply_enabled"
_PREF_BLACKLIST = "user_blacklist"
_PREF_WHITELIST = "user_whitelist"
_PREF_PERSONA = "persona"

# config.json 里 plugin_configs 下的节名（保持向后兼容）
_CONFIG_SECTION = "llm_chat"

ReplyCallable = Callable[[str], Awaitable[str | None]]
RecallCallable = Callable[[str], Awaitable[None]]


async def _noop_recall(message_id: str) -> None:
    _ = message_id


@dataclass
class _Ctx:
    """单次消息处理的上下文束，字段可变。"""

    payload: dict[str, object]
    execution: ExecutionContext
    configuration: ConfigurationContext
    conversation: ConversationContext
    reply: ReplyCallable
    recall: RecallCallable
    config: dict[str, object]
