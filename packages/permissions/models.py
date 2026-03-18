from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import ScopeName


@dataclass(frozen=True)
class Subject:
    actor_id: str | None = None
    roles: tuple[str, ...] = ()
    platform_roles: tuple[str, ...] = ()
    group_roles: tuple[str, ...] = ()
    is_authenticated: bool = False

    @property
    def all_roles(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys((*self.roles, *self.platform_roles, *self.group_roles))
        )


@dataclass(frozen=True)
class ResourceRef:
    kind: str
    name: str


@dataclass(frozen=True)
class AuthorizationContext:
    subject: Subject
    resource: ResourceRef
    scope: str = ScopeName.GLOBAL
    platform: str | None = None
    conversation_id: str | None = None
    group_id: str | None = None
    channel_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PermissionRule:
    permissions: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()
    resource_kinds: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    allow: bool = True
    require_all: bool = True
    description: str = ""

    def matches_context(self, context: AuthorizationContext) -> bool:
        if self.scopes and context.scope not in self.scopes:
            return False
        if self.resource_kinds and context.resource.kind not in self.resource_kinds:
            return False
        if self.resources and context.resource.name not in self.resources:
            return False
        if self.platforms and context.platform not in self.platforms:
            return False
        if self.roles:
            subject_roles = set(context.subject.all_roles)
            rule_roles = set(self.roles)
            if self.require_all and not rule_roles.issubset(subject_roles):
                return False
            if not self.require_all and rule_roles.isdisjoint(subject_roles):
                return False
        return True


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str
    matched_rules: tuple[PermissionRule, ...] = ()
