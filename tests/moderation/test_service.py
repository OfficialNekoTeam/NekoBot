from __future__ import annotations

from typing import override

from packages.moderation.base import ModerationBackend
from packages.moderation.service import ModerationService
from packages.moderation.types import (
    ModerationDecision,
    ModerationRequest,
    ModerationStage,
)


class FakeBackend(ModerationBackend):
    def __init__(self, name: str, decision: ModerationDecision) -> None:
        self.name: str = name
        self._decision: ModerationDecision = decision

    @override
    async def review(self, request: ModerationRequest) -> ModerationDecision:
        _ = request
        return self._decision


def test_moderation_service_lists_registered_backends() -> None:
    service = ModerationService()
    service.register_backend(
        FakeBackend("keywords", ModerationDecision(action="allow"))
    )
    service.register_backend(FakeBackend("baidu", ModerationDecision(action="allow")))

    assert service.list_backends() == ("baidu", "keywords")


async def test_moderation_service_uses_preferred_backend() -> None:
    service = ModerationService()
    service.register_backend(
        FakeBackend("keywords", ModerationDecision(action="allow", reason="ok"))
    )
    service.register_backend(
        FakeBackend("baidu", ModerationDecision(action="block", reason="blocked"))
    )

    decision = await service.review(
        ModerationRequest(stage=ModerationStage.INPUT, text="hello"),
        preferred_backend="baidu",
    )

    assert decision.action == "block"
    assert decision.reason == "blocked"


async def test_moderation_service_defaults_to_allow_when_no_backend_blocks() -> None:
    service = ModerationService()
    service.register_backend(
        FakeBackend("keywords", ModerationDecision(action="allow", reason="clean"))
    )

    decision = await service.review(
        ModerationRequest(stage=ModerationStage.OUTPUT, text="safe")
    )

    assert decision.allowed is True
    assert decision.action == "allow"


async def test_moderation_service_returns_first_blocking_decision() -> None:
    service = ModerationService()
    service.register_backend(
        FakeBackend("keywords", ModerationDecision(action="allow", reason="clean"))
    )
    service.register_backend(
        FakeBackend("baidu", ModerationDecision(action="block", reason="unsafe"))
    )

    decision = await service.review(
        ModerationRequest(stage=ModerationStage.FINAL_SEND, text="bad")
    )

    assert decision.action == "block"
    assert decision.reason == "unsafe"


async def test_moderation_service_returns_first_rewrite_decision() -> None:
    service = ModerationService()
    service.register_backend(
        FakeBackend(
            "rewrite",
            ModerationDecision(
                action="rewrite", rewritten_text="cleaned", reason="rewritten"
            ),
        )
    )

    decision = await service.review(
        ModerationRequest(stage=ModerationStage.OUTPUT, text="messy")
    )

    assert decision.action == "rewrite"
    assert decision.rewritten_text == "cleaned"


async def test_moderation_service_raises_for_unknown_preferred_backend() -> None:
    service = ModerationService()

    try:
        _ = await service.review(
            ModerationRequest(stage=ModerationStage.INPUT, text="hello"),
            preferred_backend="missing",
        )
    except KeyError as exc:
        assert "moderation backend not found" in str(exc)
    else:
        raise AssertionError("expected KeyError for missing moderation backend")
