from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, TypeAlias

from .models import ConversationKey, IsolationMode, SessionKey, ValueMap

ScopedValueMap: TypeAlias = dict[str, ValueMap]


class ScopeExecution(Protocol):
    scope: str
    platform: str | None
    platform_instance_uuid: str | None
    chat_id: str | None
    group_id: str | None
    channel_id: str | None


@dataclass(slots=True)
class ConfigurationContext:
    framework_config: ValueMap = field(default_factory=dict)
    plugin_configs: ScopedValueMap = field(default_factory=dict)
    provider_configs: ScopedValueMap = field(default_factory=dict)
    permission_config: ValueMap = field(default_factory=dict)
    moderation_config: ValueMap = field(default_factory=dict)
    conversation_config: ValueMap = field(default_factory=dict)
    plugin_bindings: ScopedValueMap = field(default_factory=dict)

    def get_plugin_config(self, plugin_name: str) -> ValueMap:
        return dict(self.plugin_configs.get(plugin_name, {}))

    def get_provider_config(self, provider_name: str) -> ValueMap:
        return dict(self.provider_configs.get(provider_name, {}))

    def get_plugin_binding(self, plugin_name: str) -> ValueMap:
        return dict(self.plugin_bindings.get(plugin_name, {}))

    def is_plugin_enabled(
        self,
        plugin_name: str,
        execution: ScopeExecution | None = None,
    ) -> bool:
        binding = self.get_plugin_binding(plugin_name)
        if execution is not None and not self._binding_matches_scope(
            binding, execution
        ):
            return False
        if "enabled" in binding:
            return bool(binding.get("enabled"))
        return True

    def _binding_matches_scope(
        self,
        binding: ValueMap,
        execution: ScopeExecution,
    ) -> bool:
        scopes = binding.get("scopes")
        if isinstance(scopes, list) and scopes and execution.scope not in scopes:
            return False

        platforms = binding.get("platforms")
        if (
            isinstance(platforms, list)
            and platforms
            and execution.platform not in platforms
        ):
            return False

        instances = binding.get("platform_instances")
        if (
            isinstance(instances, list)
            and instances
            and execution.platform_instance_uuid not in instances
        ):
            return False

        enabled_chats = binding.get("enabled_chats")
        if isinstance(enabled_chats, list) and enabled_chats:
            chat_id = execution.chat_id or execution.group_id or execution.channel_id
            if chat_id not in enabled_chats:
                return False

        disabled_chats = binding.get("disabled_chats")
        if isinstance(disabled_chats, list) and disabled_chats:
            chat_id = execution.chat_id or execution.group_id or execution.channel_id
            if chat_id in disabled_chats:
                return False

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
    history: list[ValueMap] = field(default_factory=list)
    summary: str | None = None
    memory_refs: list[str] = field(default_factory=list)
    provider_preferences: ValueMap = field(default_factory=dict)
    metadata: ValueMap = field(default_factory=dict)
