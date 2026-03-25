from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeAlias, cast

from ..conversations.context import ConfigurationContext, ConversationContext
from ..permissions import (
    AuthorizationContext,
    PermissionDecision,
    PermissionEngine,
    ResourceRef,
    Subject,
)
from ..permissions.constants import ScopeName

ValueMap: TypeAlias = dict[str, object]

ReplyCallable = Callable[[str], Awaitable[None]]
ProviderCallable = Callable[..., Awaitable[object]]
TaskCallable = Callable[[str, ValueMap], Awaitable[object]]
PermissionCallable = Callable[[tuple[str, ...], bool], PermissionDecision]


async def _noop_reply(message: str) -> None:
    _ = message
    return None


async def _missing_provider(*args: object, **kwargs: object) -> object:
    _ = args, kwargs
    raise RuntimeError("provider access is not configured for this context")


async def _missing_task(name: str, payload: ValueMap) -> object:
    _ = name, payload
    raise RuntimeError("task scheduling is not configured for this context")


def _allow_all_permissions(
    permissions: tuple[str, ...], require_all: bool
) -> PermissionDecision:
    _ = permissions, require_all
    return PermissionDecision(allowed=True, reason="default allow")


DEFAULT_REPLY_CALLABLE: ReplyCallable = _noop_reply
DEFAULT_PROVIDER_CALLABLE: ProviderCallable = _missing_provider
DEFAULT_TASK_CALLABLE: TaskCallable = _missing_task
DEFAULT_PERMISSION_CALLABLE: PermissionCallable = _allow_all_permissions


@dataclass(slots=True)
class ExecutionContext:
    event_name: str = ""
    actor_id: str | None = None
    platform: str | None = None
    platform_instance_uuid: str | None = None
    conversation_id: str | None = None
    chat_id: str | None = None
    group_id: str | None = None
    channel_id: str | None = None
    thread_id: str | None = None
    message_id: str | None = None
    scope: str = ScopeName.GLOBAL
    roles: tuple[str, ...] = ()
    platform_roles: tuple[str, ...] = ()
    group_roles: tuple[str, ...] = ()
    is_authenticated: bool = False
    metadata: ValueMap = field(default_factory=dict)

    def to_authorization_context(
        self, resource_kind: str, resource_name: str
    ) -> AuthorizationContext:
        return AuthorizationContext(
            subject=Subject(
                actor_id=self.actor_id,
                roles=self.roles,
                platform_roles=self.platform_roles,
                group_roles=self.group_roles,
                is_authenticated=self.is_authenticated,
            ),
            resource=ResourceRef(kind=resource_kind, name=resource_name),
            scope=self.scope,
            platform=self.platform,
            conversation_id=self.conversation_id,
            group_id=self.group_id,
            channel_id=self.channel_id,
            metadata=self.metadata.copy(),
        )


@dataclass(slots=True)
class PluginContext:
    plugin_name: str
    config: ValueMap = field(default_factory=dict)
    execution: ExecutionContext = field(default_factory=ExecutionContext)
    configuration: ConfigurationContext = field(default_factory=ConfigurationContext)
    conversation: ConversationContext | None = None
    reply_callable: ReplyCallable = DEFAULT_REPLY_CALLABLE
    provider_callable: ProviderCallable = DEFAULT_PROVIDER_CALLABLE
    task_callable: TaskCallable = DEFAULT_TASK_CALLABLE
    permission_callable: PermissionCallable = DEFAULT_PERMISSION_CALLABLE
    permission_engine: PermissionEngine | None = None
    resource_kind: str = "plugin"

    def __post_init__(self) -> None:
        if not self.config:
            self.config = self.configuration.get_plugin_config(self.plugin_name)

    async def reply(self, message: str) -> None:
        await self.reply_callable(message)

    async def request_provider(self, provider_name: str, **kwargs: object) -> object:
        return await self.provider_callable(provider_name=provider_name, **kwargs)

    async def schedule_task(self, task_name: str, payload: ValueMap) -> object:
        return await self.task_callable(task_name, payload)

    def get_config(self, key: str, default: object = None) -> object:
        return self.config.get(key, default)

    def permission_decision(
        self, *permissions: str, require_all: bool = True
    ) -> PermissionDecision:
        if self.permission_engine is not None:
            auth_context = self.execution.to_authorization_context(
                resource_kind=self.resource_kind,
                resource_name=self.plugin_name,
            )
            return self.permission_engine.evaluate(
                tuple(permissions),
                auth_context,
                require_all=require_all,
            )
        return self.permission_callable(tuple(permissions), require_all)

    def check_permissions(self, *permissions: str, require_all: bool = True) -> bool:
        return self.permission_decision(*permissions, require_all=require_all).allowed


@dataclass(frozen=True)
class EffectivePluginBinding:
    plugin_name: str
    enabled: bool
    config: ValueMap = field(default_factory=dict)
    metadata: ValueMap = field(default_factory=dict)


def build_effective_plugin_binding(
    plugin_name: str,
    configuration: ConfigurationContext,
    execution: ExecutionContext | None = None,
) -> EffectivePluginBinding:
    base_config = configuration.get_plugin_config(plugin_name)
    binding = configuration.get_plugin_binding(plugin_name)
    override_config = binding.get("config", {})
    merged_config = dict(base_config)
    if isinstance(override_config, dict):
        override_map = cast(dict[str, object], override_config)
        merged_config.update(override_map)
    enabled = configuration.is_plugin_enabled(plugin_name, execution=execution)
    binding_map = cast(dict[object, object], binding)
    metadata = {
        str(key): value
        for key, value in binding_map.items()
        if isinstance(key, str) and key not in {"enabled", "config"}
    }
    return EffectivePluginBinding(
        plugin_name=plugin_name,
        enabled=enabled,
        config=merged_config,
        metadata=metadata,
    )
