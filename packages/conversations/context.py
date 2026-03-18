from __future__ import annotations

from dataclasses import replace
from dataclasses import dataclass, field
from typing import Any

from .models import ConversationKey, IsolationMode, SessionKey


@dataclass(slots=True)
class ConfigurationContext:
    framework_config: dict[str, Any] = field(default_factory=dict)
    plugin_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    provider_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    permission_config: dict[str, Any] = field(default_factory=dict)
    moderation_config: dict[str, Any] = field(default_factory=dict)
    conversation_config: dict[str, Any] = field(default_factory=dict)
    plugin_bindings: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get_plugin_config(self, plugin_name: str) -> dict[str, Any]:
        return dict(self.plugin_configs.get(plugin_name, {}))

    def get_provider_config(self, provider_name: str) -> dict[str, Any]:
        return dict(self.provider_configs.get(provider_name, {}))

    def get_plugin_binding(self, plugin_name: str) -> dict[str, Any]:
        return dict(self.plugin_bindings.get(plugin_name, {}))

    def is_plugin_enabled(self, plugin_name: str) -> bool:
        binding = self.get_plugin_binding(plugin_name)
        if "enabled" in binding:
            return bool(binding.get("enabled"))
        return True

    def resolve_provider_name(self, default: str | None = None) -> str | None:
        configured = self.conversation_config.get("provider_name")
        if isinstance(configured, str) and configured:
            return configured

        framework_default = self.framework_config.get("default_provider")
        if isinstance(framework_default, str) and framework_default:
            return framework_default

        return default

    def resolve_moderation_strategy(self) -> str | None:
        configured = self.moderation_config.get("strategy")
        if isinstance(configured, str) and configured:
            return configured

        framework_default = self.framework_config.get("moderation_strategy")
        if isinstance(framework_default, str) and framework_default:
            return framework_default

        return None

    @property
    def isolation_mode(self) -> str:
        configured = self.conversation_config.get("isolation_mode")
        if isinstance(configured, str) and configured:
            return configured
        return IsolationMode.SHARED_GROUP

    @property
    def compression_mode(self) -> str:
        configured = self.conversation_config.get("compression_mode")
        if isinstance(configured, str) and configured:
            return configured
        return "suggest"

    @property
    def summarization_mode(self) -> str:
        configured = self.conversation_config.get("summarization_mode")
        if isinstance(configured, str) and configured:
            return configured
        return "manual"


@dataclass(slots=True)
class ConversationContext:
    isolation_mode: str
    conversation_key: ConversationKey | None = None
    session_key: SessionKey | None = None
    conversation_id: str | None = None
    scope: str | None = None
    platform_type: str | None = None
    platform_instance_uuid: str | None = None
    chat_id: str | None = None
    actor_id: str | None = None
    thread_id: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    summary: str | None = None
    memory_refs: list[str] = field(default_factory=list)
    provider_preferences: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._conversations: dict[str, ConversationContext] = {}
        self._sessions: dict[str, ConversationContext] = {}

    def get_conversation(self, conversation_key: str) -> ConversationContext | None:
        context = self._conversations.get(conversation_key)
        if context is None:
            return None
        return replace(context)

    def get_session(self, session_key: str) -> ConversationContext | None:
        context = self._sessions.get(session_key)
        if context is None:
            return None
        return replace(context)

    def save(self, context: ConversationContext) -> ConversationContext:
        stored = replace(
            context,
            history=list(context.history),
            memory_refs=list(context.memory_refs),
            provider_preferences=dict(context.provider_preferences),
            metadata=dict(context.metadata),
        )
        if stored.conversation_key is not None:
            self._conversations[stored.conversation_key.value] = stored
        if stored.session_key is not None:
            self._sessions[stored.session_key.value] = stored
        return replace(stored)

    def upsert(self, context: ConversationContext) -> ConversationContext:
        return self.save(context)

    def delete(self, conversation_key: str) -> None:
        context = self._conversations.pop(conversation_key, None)
        if context is None or context.session_key is None:
            return
        _ = self._sessions.pop(context.session_key.value, None)

    def list_conversation_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._conversations.keys()))
