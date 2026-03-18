from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class IsolationMode:
    PRIVATE = "private"
    PER_USER = "per_user"
    SHARED_GROUP = "shared_group"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class ConversationKey:
    value: str

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class SessionKey:
    value: str

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ScopeRoute:
    platform_type: str
    platform_instance_uuid: str
    scope: str
    chat_id: str | None = None
    actor_id: str | None = None
    thread_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_segments(self) -> tuple[str, ...]:
        segments = [self.platform_type, self.platform_instance_uuid, self.scope]
        if self.chat_id:
            segments.append(self.chat_id)
        if self.thread_id:
            segments.extend(("thread", self.thread_id))
        if self.actor_id:
            segments.extend(("user", self.actor_id))
        return tuple(segments)
