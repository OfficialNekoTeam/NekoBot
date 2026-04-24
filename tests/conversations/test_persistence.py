from __future__ import annotations

from pathlib import Path

import pytest

from packages.conversations.context import ConversationContext
from packages.conversations.models import ConversationKey, SessionKey
from packages.conversations.persistence import (
    InMemoryConversationStore,
    SQLiteConversationStore,
)


def _conversation_context() -> ConversationContext:
    return ConversationContext(
        isolation_mode="per_user",
        conversation_key=ConversationKey(
            "onebot:instance-1:group:group-42:user:user-7"
        ),
        session_key=SessionKey("onebot:instance-1:group:group-42:user:user-7"),
        conversation_id="conversation-1",
        scope="group",
        platform_type="onebot",
        platform_instance_uuid="instance-1",
        chat_id="group-42",
        actor_id="user-7",
        thread_id="thread-2",
        history=[{"role": "user", "content": "hello"}],
        summary="summary",
        memory_refs=["memory-1"],
        provider_preferences={"provider": "openai"},
        metadata={"tag": "demo"},
    )


@pytest.mark.asyncio
async def test_in_memory_store_save_get_and_list() -> None:
    store = InMemoryConversationStore()
    context = _conversation_context()
    conversation_key = context.conversation_key

    assert conversation_key is not None

    saved = await store.save(context)
    loaded = await store.get_conversation(conversation_key.value)

    assert saved is not context
    assert loaded is not None
    assert loaded.conversation_key == context.conversation_key
    assert loaded.history == context.history
    assert await store.list_conversation_keys() == (conversation_key.value,)


@pytest.mark.asyncio
async def test_in_memory_store_returns_cloned_contexts() -> None:
    store = InMemoryConversationStore()
    context = _conversation_context()
    conversation_key = context.conversation_key

    assert conversation_key is not None

    _ = await store.save(context)

    loaded = await store.get_conversation(conversation_key.value)
    assert loaded is not None
    loaded.history.append({"role": "assistant", "content": "mutated"})

    reloaded = await store.get_conversation(conversation_key.value)
    assert reloaded is not None
    assert reloaded.history == [{"role": "user", "content": "hello"}]


@pytest.mark.asyncio
async def test_in_memory_store_delete_removes_conversation_and_session() -> None:
    store = InMemoryConversationStore()
    context = _conversation_context()
    conversation_key = context.conversation_key
    session_key = context.session_key

    assert conversation_key is not None
    assert session_key is not None

    _ = await store.save(context)

    await store.delete(conversation_key.value)

    assert await store.get_conversation(conversation_key.value) is None
    assert await store.get_session(session_key.value) is None


@pytest.mark.asyncio
async def test_sqlite_store_persists_and_loads_context(tmp_path: Path) -> None:
    store = SQLiteConversationStore(tmp_path / "conversations.sqlite3")
    context = _conversation_context()
    conversation_key = context.conversation_key

    assert conversation_key is not None

    saved = await store.save(context)
    loaded = await store.get_conversation(conversation_key.value)

    assert saved.conversation_key == context.conversation_key
    assert loaded is not None
    assert loaded.conversation_key == context.conversation_key
    assert loaded.history == context.history
    assert loaded.summary == "summary"
    assert loaded.metadata["tag"] == "demo"


@pytest.mark.asyncio
async def test_in_memory_store_persona_crud() -> None:
    store = InMemoryConversationStore()

    assert await store.get_persona("cat") is None
    assert await store.list_personas() == {}

    await store.save_persona("cat", "你是一只猫")
    await store.save_persona("dog", "你是一只狗")

    assert await store.get_persona("cat") == "你是一只猫"
    assert await store.list_personas() == {"cat": "你是一只猫", "dog": "你是一只狗"}

    await store.delete_persona("cat")
    assert await store.get_persona("cat") is None
    assert "dog" in await store.list_personas()

    await store.delete_persona("nonexistent")  # must not raise


@pytest.mark.asyncio
async def test_sqlite_store_persona_crud(tmp_path: Path) -> None:
    store = SQLiteConversationStore(tmp_path / "conversations.sqlite3")

    assert await store.get_persona("cat") is None
    assert await store.list_personas() == {}

    await store.save_persona("cat", "你是一只猫")
    await store.save_persona("dog", "你是一只狗")

    assert await store.get_persona("cat") == "你是一只猫"
    assert await store.list_personas() == {"cat": "你是一只猫", "dog": "你是一只狗"}

    await store.save_persona("cat", "updated")
    assert await store.get_persona("cat") == "updated"

    await store.delete_persona("cat")
    assert await store.get_persona("cat") is None
    assert "dog" in await store.list_personas()


@pytest.mark.asyncio
async def test_sqlite_store_close(tmp_path: Path) -> None:
    store = SQLiteConversationStore(tmp_path / "conversations.sqlite3")
    _ = await store.get_conversation("any-key")  # opens connection
    await store.close()
    assert store._conn is None


@pytest.mark.asyncio
async def test_sqlite_store_lists_and_deletes_conversations(tmp_path: Path) -> None:
    store = SQLiteConversationStore(tmp_path / "conversations.sqlite3")
    context = _conversation_context()
    conversation_key = context.conversation_key

    assert conversation_key is not None

    _ = await store.save(context)

    assert await store.list_conversation_keys() == (conversation_key.value,)

    await store.delete(conversation_key.value)

    assert await store.list_conversation_keys() == ()
    assert await store.get_conversation(conversation_key.value) is None
