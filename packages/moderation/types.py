from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

ValueMap: TypeAlias = dict[str, object]


class ModerationStage:
    INPUT: str = "input"
    OUTPUT: str = "output"
    FINAL_SEND: str = "final_send"


@dataclass(slots=True)
class ModerationRequest:
    stage: str
    text: str
    actor_id: str | None = None
    platform: str | None = None
    conversation_key: str | None = None
    metadata: ValueMap = field(default_factory=dict)


@dataclass(frozen=True)
class ModerationDecision:
    action: str
    reason: str = ""
    rewritten_text: str | None = None
    source: str | None = None
    metadata: ValueMap = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.action != "block"
