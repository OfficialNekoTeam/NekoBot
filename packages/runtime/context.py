from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ..permissions import (
    AuthorizationContext,
    PermissionDecision,
    PermissionEngine,
    ResourceRef,
    Subject,
)
from ..permissions.constants import ScopeName


ReplyCallable = Callable[[str], Awaitable[None]]
ProviderCallable = Callable[..., Awaitable[Any]]
TaskCallable = Callable[[str, dict[str, Any]], Awaitable[Any]]
PermissionCallable = Callable[[tuple[str, ...], bool], PermissionDecision]


async def _noop_reply(message: str) -> None:
    return None


async def _missing_provider(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError("provider access is not configured for this context")


async def _missing_task(name: str, payload: dict[str, Any]) -> Any:
    raise RuntimeError("task scheduling is not configured for this context")


def _allow_all_permissions(
    permissions: tuple[str, ...], require_all: bool
) -> PermissionDecision:
    return PermissionDecision(allowed=True, reason="default allow")


@dataclass(slots=True)
class ExecutionContext:
    event_name: str = ""
    actor_id: str | None = None
    platform: str | None = None
    conversation_id: str | None = None
    group_id: str | None = None
    channel_id: str | None = None
    scope: str = ScopeName.GLOBAL
    roles: tuple[str, ...] = ()
    platform_roles: tuple[str, ...] = ()
    group_roles: tuple[str, ...] = ()
    is_authenticated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

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
    config: dict[str, Any] = field(default_factory=dict)
    execution: ExecutionContext = field(default_factory=ExecutionContext)
    reply_callable: ReplyCallable = _noop_reply
    provider_callable: ProviderCallable = _missing_provider
    task_callable: TaskCallable = _missing_task
    permission_callable: PermissionCallable = _allow_all_permissions
    permission_engine: PermissionEngine | None = None
    resource_kind: str = "plugin"

    async def reply(self, message: str) -> None:
        await self.reply_callable(message)

    async def request_provider(self, provider_name: str, **kwargs: Any) -> Any:
        return await self.provider_callable(provider_name=provider_name, **kwargs)

    async def schedule_task(self, task_name: str, payload: dict[str, Any]) -> Any:
        return await self.task_callable(task_name, payload)

    def get_config(self, key: str, default: Any = None) -> Any:
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
