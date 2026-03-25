from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Protocol, cast

from .context import ConversationContext
from .models import ConversationKey, SessionKey, ValueMap


class ConversationStore(Protocol):
    def get_conversation(self, conversation_key: str) -> ConversationContext | None: ...

    def get_session(self, session_key: str) -> ConversationContext | None: ...

    def save(self, context: ConversationContext) -> ConversationContext: ...

    def upsert(self, context: ConversationContext) -> ConversationContext: ...

    def delete(self, conversation_key: str) -> None: ...

    def list_conversation_keys(self) -> tuple[str, ...]: ...


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._conversations: dict[str, ConversationContext] = {}
        self._sessions: dict[str, ConversationContext] = {}

    def get_conversation(self, conversation_key: str) -> ConversationContext | None:
        context = self._conversations.get(conversation_key)
        if context is None:
            return None
        return _clone_context(context)

    def get_session(self, session_key: str) -> ConversationContext | None:
        context = self._sessions.get(session_key)
        if context is None:
            return None
        return _clone_context(context)

    def save(self, context: ConversationContext) -> ConversationContext:
        stored = _clone_context(context)
        if stored.conversation_key is not None:
            self._conversations[stored.conversation_key.value] = stored
        if stored.session_key is not None:
            self._sessions[stored.session_key.value] = stored
        return _clone_context(stored)

    def upsert(self, context: ConversationContext) -> ConversationContext:
        return self.save(context)

    def delete(self, conversation_key: str) -> None:
        context = self._conversations.pop(conversation_key, None)
        if context is None or context.session_key is None:
            return
        _ = self._sessions.pop(context.session_key.value, None)

    def list_conversation_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._conversations.keys()))


class SQLiteConversationStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path: Path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def get_conversation(self, conversation_key: str) -> ConversationContext | None:
        query = "SELECT * FROM conversations WHERE conversation_key = ?"
        with self._connect() as connection:
            row = cast(
                sqlite3.Row | None,
                connection.execute(query, (conversation_key,)).fetchone(),
            )
        if row is None:
            return None
        return _clone_context(self._row_to_context(row))

    def get_session(self, session_key: str) -> ConversationContext | None:
        query = "SELECT * FROM conversations WHERE session_key = ?"
        with self._connect() as connection:
            row = cast(
                sqlite3.Row | None,
                connection.execute(query, (session_key,)).fetchone(),
            )
        if row is None:
            return None
        return _clone_context(self._row_to_context(row))

    def save(self, context: ConversationContext) -> ConversationContext:
        stored = _clone_context(context)
        payload = self._context_to_row(stored)
        query = (
            "INSERT INTO conversations ("
            "conversation_key, session_key, isolation_mode, conversation_id, scope, "
            "platform_type, platform_instance_uuid, chat_id, actor_id, thread_id, "
            "history_json, summary, memory_refs_json, provider_preferences_json, "
            "metadata_json"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(conversation_key) DO UPDATE SET "
            "session_key=excluded.session_key, isolation_mode=excluded.isolation_mode, "
            "conversation_id=excluded.conversation_id, scope=excluded.scope, "
            "platform_type=excluded.platform_type, "
            "platform_instance_uuid=excluded.platform_instance_uuid, "
            "chat_id=excluded.chat_id, actor_id=excluded.actor_id, "
            "thread_id=excluded.thread_id, "
            "history_json=excluded.history_json, summary=excluded.summary, "
            "memory_refs_json=excluded.memory_refs_json, "
            "provider_preferences_json=excluded.provider_preferences_json, "
            "metadata_json=excluded.metadata_json"
        )
        with self._connect() as connection:
            _ = connection.execute(query, payload)
            connection.commit()
        return _clone_context(stored)

    def upsert(self, context: ConversationContext) -> ConversationContext:
        return self.save(context)

    def delete(self, conversation_key: str) -> None:
        with self._connect() as connection:
            _ = connection.execute(
                "DELETE FROM conversations WHERE conversation_key = ?",
                (conversation_key,),
            )
            connection.commit()

    def list_conversation_keys(self) -> tuple[str, ...]:
        with self._connect() as connection:
            rows = cast(
                list[sqlite3.Row],
                connection.execute(
                    "SELECT conversation_key FROM conversations "
                    + "ORDER BY conversation_key"
                ).fetchall(),
            )
        return tuple(row[0] for row in rows)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        schema = (
            "CREATE TABLE IF NOT EXISTS conversations ("
            "conversation_key TEXT PRIMARY KEY, "
            "session_key TEXT, "
            "isolation_mode TEXT NOT NULL, "
            "conversation_id TEXT, "
            "scope TEXT, "
            "platform_type TEXT, "
            "platform_instance_uuid TEXT, "
            "chat_id TEXT, "
            "actor_id TEXT, "
            "thread_id TEXT, "
            "history_json TEXT NOT NULL, "
            "summary TEXT, "
            "memory_refs_json TEXT NOT NULL, "
            "provider_preferences_json TEXT NOT NULL, "
            "metadata_json TEXT NOT NULL"
            ")"
        )
        with self._connect() as connection:
            _ = connection.execute(schema)
            connection.commit()

    def _context_to_row(self, context: ConversationContext) -> tuple[str | None, ...]:
        conversation_key = (
            context.conversation_key.value if context.conversation_key else ""
        )
        session_key = context.session_key.value if context.session_key else None
        return (
            conversation_key,
            session_key,
            context.isolation_mode,
            context.conversation_id,
            context.scope,
            context.platform_type,
            context.platform_instance_uuid,
            context.chat_id,
            context.actor_id,
            context.thread_id,
            json.dumps(context.history, ensure_ascii=True),
            context.summary,
            json.dumps(context.memory_refs, ensure_ascii=True),
            json.dumps(context.provider_preferences, ensure_ascii=True),
            json.dumps(context.metadata, ensure_ascii=True),
        )

    def _row_to_context(self, row: sqlite3.Row) -> ConversationContext:
        conversation_key = self._row_str(row, "conversation_key")
        session_key = self._row_str(row, "session_key")
        return ConversationContext(
            isolation_mode=self._row_str(row, "isolation_mode") or "",
            conversation_key=ConversationKey(conversation_key)
            if conversation_key
            else None,
            session_key=SessionKey(session_key) if session_key else None,
            conversation_id=self._row_str(row, "conversation_id"),
            scope=self._row_str(row, "scope"),
            platform_type=self._row_str(row, "platform_type"),
            platform_instance_uuid=self._row_str(row, "platform_instance_uuid"),
            chat_id=self._row_str(row, "chat_id"),
            actor_id=self._row_str(row, "actor_id"),
            thread_id=self._row_str(row, "thread_id"),
            history=self._row_list_of_maps(row, "history_json"),
            summary=self._row_str(row, "summary"),
            memory_refs=self._row_list_of_strings(row, "memory_refs_json"),
            provider_preferences=self._row_value_map(row, "provider_preferences_json"),
            metadata=self._row_value_map(row, "metadata_json"),
        )

    def _row_str(self, row: sqlite3.Row, key: str) -> str | None:
        value = cast(object, row[key])
        return value if isinstance(value, str) else None

    def _row_list_of_maps(self, row: sqlite3.Row, key: str) -> list[ValueMap]:
        value = cast(object, row[key])
        if not isinstance(value, str):
            return []
        decoded = cast(object, json.loads(value))
        if not isinstance(decoded, list):
            return []
        items = cast(list[object], decoded)
        return [
            self._coerce_value_map(cast(dict[object, object], item))
            for item in items
            if isinstance(item, dict)
        ]

    def _row_list_of_strings(self, row: sqlite3.Row, key: str) -> list[str]:
        value = cast(object, row[key])
        if not isinstance(value, str):
            return []
        decoded = cast(object, json.loads(value))
        if not isinstance(decoded, list):
            return []
        items = cast(list[object], decoded)
        return [item for item in items if isinstance(item, str)]

    def _row_value_map(self, row: sqlite3.Row, key: str) -> ValueMap:
        value = cast(object, row[key])
        if not isinstance(value, str):
            return {}
        decoded = cast(object, json.loads(value))
        return self._coerce_value_map(decoded)

    def _coerce_value_map(self, value: object) -> ValueMap:
        if not isinstance(value, dict):
            return {}
        mapping = cast(dict[object, object], value)
        return {
            str(map_key): map_value
            for map_key, map_value in mapping.items()
            if isinstance(map_key, str)
        }


def _clone_context(context: ConversationContext) -> ConversationContext:
    return replace(
        context,
        history=list(context.history),
        memory_refs=list(context.memory_refs),
        provider_preferences=dict(context.provider_preferences),
        metadata=dict(context.metadata),
    )
