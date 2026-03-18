from __future__ import annotations

from abc import ABC, abstractmethod

from .types import ModerationDecision, ModerationRequest


class ModerationBackend(ABC):
    name: str

    @abstractmethod
    async def review(self, request: ModerationRequest) -> ModerationDecision:
        raise NotImplementedError
