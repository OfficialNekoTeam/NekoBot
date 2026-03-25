from __future__ import annotations

from packages.conversations.context import ConfigurationContext
from packages.conversations.models import IsolationMode
from packages.conversations.resolver import ConversationResolver
from packages.permissions.constants import ScopeName
from packages.runtime.context import ExecutionContext


def _execution_context(**overrides: object) -> ExecutionContext:
    base = ExecutionContext(
        platform="onebot",
        platform_instance_uuid="instance-1",
        scope=ScopeName.GROUP,
        chat_id="group-42",
        group_id="group-42",
        actor_id="user-7",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_resolver_private_scope_uses_actor_identity() -> None:
    resolver = ConversationResolver()
    execution = _execution_context(scope=ScopeName.PRIVATE, chat_id="dm-7")

    conversation = resolver.resolve_conversation_context(execution)

    assert conversation.conversation_key is not None
    assert conversation.session_key is not None
    assert conversation.conversation_key.value == "onebot:instance-1:private:user-7"
    assert conversation.session_key.value == conversation.conversation_key.value


def test_resolver_group_per_user_isolation_adds_user_segment() -> None:
    resolver = ConversationResolver()
    execution = _execution_context()
    configuration = ConfigurationContext(
        conversation_config={"isolation_mode": IsolationMode.PER_USER}
    )

    conversation = resolver.resolve_conversation_context(execution, configuration)

    assert conversation.conversation_key is not None
    assert (
        conversation.conversation_key.value
        == "onebot:instance-1:group:group-42:user:user-7"
    )


def test_resolver_group_shared_isolation_omits_user_segment() -> None:
    resolver = ConversationResolver()
    execution = _execution_context()
    configuration = ConfigurationContext(
        conversation_config={"isolation_mode": IsolationMode.SHARED_GROUP}
    )

    conversation = resolver.resolve_conversation_context(execution, configuration)

    assert conversation.conversation_key is not None
    assert conversation.conversation_key.value == "onebot:instance-1:group:group-42"


def test_resolver_group_hybrid_defaults_to_per_user() -> None:
    resolver = ConversationResolver()
    execution = _execution_context(metadata={})
    configuration = ConfigurationContext(
        conversation_config={"isolation_mode": IsolationMode.HYBRID}
    )

    conversation = resolver.resolve_conversation_context(execution, configuration)

    assert conversation.conversation_key is not None
    assert (
        conversation.conversation_key.value
        == "onebot:instance-1:group:group-42:user:user-7"
    )


def test_resolver_group_hybrid_can_share_group_when_flagged() -> None:
    resolver = ConversationResolver()
    execution = _execution_context(metadata={"shared_conversation": True})
    configuration = ConfigurationContext(
        conversation_config={"isolation_mode": IsolationMode.HYBRID}
    )

    conversation = resolver.resolve_conversation_context(execution, configuration)

    assert conversation.conversation_key is not None
    assert conversation.conversation_key.value == "onebot:instance-1:group:group-42"


def test_resolver_namespaces_explicit_conversation_id_by_platform_instance() -> None:
    resolver = ConversationResolver()
    execution = _execution_context(conversation_id="conversation-9")

    conversation = resolver.resolve_conversation_context(execution)

    assert conversation.conversation_key is not None
    assert (
        conversation.conversation_key.value
        == "onebot:instance-1:conversation:conversation-9"
    )


def test_resolver_thread_id_participates_in_group_key() -> None:
    resolver = ConversationResolver()
    execution = _execution_context(thread_id="thread-2")
    configuration = ConfigurationContext(
        conversation_config={"isolation_mode": IsolationMode.SHARED_GROUP}
    )

    conversation = resolver.resolve_conversation_context(execution, configuration)

    assert conversation.conversation_key is not None
    assert (
        conversation.conversation_key.value
        == "onebot:instance-1:group:thread:thread-2:group-42"
    )
