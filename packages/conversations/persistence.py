from __future__ import annotations

import collections
import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Protocol, cast

import aiosqlite

from .context import ConversationContext
from .models import ConversationKey, SessionKey, ValueMap


class ConversationStore(Protocol):
    async def get_conversation(self, conversation_key: str) -> ConversationContext | None: ...

    async def get_session(self, session_key: str) -> ConversationContext | None: ...

    async def save(self, context: ConversationContext) -> ConversationContext: ...

    async def upsert(self, context: ConversationContext) -> ConversationContext: ...

    async def delete(self, conversation_key: str) -> None: ...

    async def list_conversation_keys(self) -> tuple[str, ...]: ...

    # Persona 管理
    async def get_persona(self, name: str) -> str | None: ...
    async def save_persona(self, name: str, prompt: str) -> None: ...
    async def list_personas(self) -> dict[str, str]: ...
    async def delete_persona(self, name: str) -> None: ...


class InMemoryConversationStore:
    def __init__(self, max_size: int = 1000) -> None:
        self.max_size = max_size
        self._conversations: collections.OrderedDict[str, ConversationContext] = collections.OrderedDict()
        self._sessions: collections.OrderedDict[str, ConversationContext] = collections.OrderedDict()
        self._personas: dict[str, str] = {}

    async def get_conversation(self, conversation_key: str) -> ConversationContext | None:
        context = self._conversations.get(conversation_key)
        if context is None:
            return None
        return _clone_context(context)

    async def get_session(self, session_key: str) -> ConversationContext | None:
        context = self._sessions.get(session_key)
        if context is None:
            return None
        return _clone_context(context)

    async def save(self, context: ConversationContext) -> ConversationContext:
        stored = _clone_context(context)
        if stored.conversation_key is not None:
            self._conversations[stored.conversation_key.value] = stored
            self._conversations.move_to_end(stored.conversation_key.value)
            if len(self._conversations) > self.max_size:
                self._conversations.popitem(last=False)
        if stored.session_key is not None:
            self._sessions[stored.session_key.value] = stored
            self._sessions.move_to_end(stored.session_key.value)
            if len(self._sessions) > self.max_size:
                self._sessions.popitem(last=False)
        return _clone_context(stored)

    async def upsert(self, context: ConversationContext) -> ConversationContext:
        return await self.save(context)

    async def delete(self, conversation_key: str) -> None:
        context = self._conversations.pop(conversation_key, None)
        if context is None or context.session_key is None:
            return
        _ = self._sessions.pop(context.session_key.value, None)

    async def list_conversation_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._conversations.keys()))

    async def get_persona(self, name: str) -> str | None:
        return self._personas.get(name)

    async def save_persona(self, name: str, prompt: str) -> None:
        self._personas[name] = prompt

    async def list_personas(self) -> dict[str, str]:
        return dict(self._personas)

    async def delete_persona(self, name: str) -> None:
        self._personas.pop(name, None)


class SQLiteConversationStore:
    """Async SQLite conversation store backed by aiosqlite.

    Schema initialisation is done synchronously in __init__ (one-time,
    negligible cost) so callers don't need an extra async setup step.
    All data-access methods are fully async and do not block the event loop.
    """

    _INSERT_SQL = (
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

    def __init__(self, database_path: str | Path) -> None:
        self.database_path: Path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_sync()
        self._conn: aiosqlite.Connection | None = None

    async def _get_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.database_path)
            self._conn.row_factory = aiosqlite.Row
        return self._conn

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Public async interface
    # ------------------------------------------------------------------

    async def get_conversation(self, conversation_key: str) -> ConversationContext | None:
        db = await self._get_conn()
        async with db.execute(
            "SELECT * FROM conversations WHERE conversation_key = ?",
            (conversation_key,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return _clone_context(self._row_to_context(row))

    async def get_session(self, session_key: str) -> ConversationContext | None:
        db = await self._get_conn()
        async with db.execute(
            "SELECT * FROM conversations WHERE session_key = ?",
            (session_key,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return _clone_context(self._row_to_context(row))

    async def save(self, context: ConversationContext) -> ConversationContext:
        stored = _clone_context(context)
        payload = self._context_to_row(stored)
        db = await self._get_conn()
        await db.execute(self._INSERT_SQL, payload)
        await db.commit()
        return _clone_context(stored)

    async def upsert(self, context: ConversationContext) -> ConversationContext:
        return await self.save(context)

    async def delete(self, conversation_key: str) -> None:
        db = await self._get_conn()
        await db.execute(
            "DELETE FROM conversations WHERE conversation_key = ?",
            (conversation_key,),
        )
        await db.commit()

    async def list_conversation_keys(self) -> tuple[str, ...]:
        db = await self._get_conn()
        async with db.execute(
            "SELECT conversation_key FROM conversations ORDER BY conversation_key"
        ) as cursor:
            rows = await cursor.fetchall()
        return tuple(row[0] for row in rows)

    # ------------------------------------------------------------------
    # Persona CRUD
    # ------------------------------------------------------------------

    async def get_persona(self, name: str) -> str | None:
        db = await self._get_conn()
        async with db.execute(
            "SELECT prompt FROM personas WHERE name = ?",
            (name,),
        ) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else None

    async def save_persona(self, name: str, prompt: str) -> None:
        db = await self._get_conn()
        await db.execute(
            "INSERT INTO personas (name, prompt) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET prompt=excluded.prompt",
            (name, prompt),
        )
        await db.commit()

    async def list_personas(self) -> dict[str, str]:
        db = await self._get_conn()
        async with db.execute("SELECT name, prompt FROM personas") as cursor:
            rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}

    async def delete_persona(self, name: str) -> None:
        db = await self._get_conn()
        await db.execute("DELETE FROM personas WHERE name = ?", (name,))
        await db.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _initialize_sync(self) -> None:
        """Create the schema using plain sqlite3 (one-time, startup only)."""
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
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(schema)
            # 新增 personas 表
            conn.execute(
                "CREATE TABLE IF NOT EXISTS personas ("
                "name TEXT PRIMARY KEY, "
                "prompt TEXT NOT NULL, "
                "metadata_json TEXT"
                ")"
            )
            conn.commit()

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

    def _row_to_context(self, row: aiosqlite.Row) -> ConversationContext:
        conversation_key = self._row_str(row, "conversation_key")
        session_key = self._row_str(row, "session_key")
        return ConversationContext(
            isolation_mode=self._row_str(row, "isolation_mode") or "",
            conversation_key=ConversationKey(conversation_key) if conversation_key else None,
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

    def _row_str(self, row: aiosqlite.Row, key: str) -> str | None:
        value = cast(object, row[key])
        return value if isinstance(value, str) else None

    def _row_list_of_maps(self, row: aiosqlite.Row, key: str) -> list[ValueMap]:
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

    def _row_list_of_strings(self, row: aiosqlite.Row, key: str) -> list[str]:
        value = cast(object, row[key])
        if not isinstance(value, str):
            return []
        decoded = cast(object, json.loads(value))
        if not isinstance(decoded, list):
            return []
        items = cast(list[object], decoded)
        return [item for item in items if isinstance(item, str)]

    def _row_value_map(self, row: aiosqlite.Row, key: str) -> ValueMap:
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


def _clone_context(context: ConversationContext, max_history_size: int = 150) -> ConversationContext:
    history = list(context.history)
    if len(history) > max_history_size:
        # Keep the latest messages + system messages (optional, usually system is fixed logic).
        # We simply truncate to avoid OOM. Wait, if there are important system prompts at index 0,
        # usually they are passed dynamically via ProviderRequest, not stored in history forever.
        # But just in case, we keep the last MAX events.
        history = history[-max_history_size:]

    return replace(
        context,
        history=history,
        memory_refs=list(context.memory_refs)[:max_history_size],  # Same bounds for safety
        provider_preferences=dict(context.provider_preferences),
        metadata=dict(context.metadata),
    )
