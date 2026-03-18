from __future__ import annotations

from .base import ModerationBackend
from .types import ModerationDecision, ModerationRequest


class ModerationService:
    def __init__(self) -> None:
        self._backends: dict[str, ModerationBackend] = {}

    def register_backend(self, backend: ModerationBackend) -> None:
        self._backends[backend.name] = backend

    def list_backends(self) -> tuple[str, ...]:
        return tuple(sorted(self._backends.keys()))

    async def review(
        self,
        request: ModerationRequest,
        preferred_backend: str | None = None,
    ) -> ModerationDecision:
        if preferred_backend is not None:
            backend = self._backends.get(preferred_backend)
            if backend is None:
                raise KeyError(f"moderation backend not found: {preferred_backend}")
            return await backend.review(request)

        for backend in self._backends.values():
            decision = await backend.review(request)
            if not decision.allowed or decision.rewritten_text is not None:
                return decision

        return ModerationDecision(
            action="allow", reason="no moderation backend blocked content"
        )
