"""Unit tests for packages.llm.handler — LLMHandler wake logic, command dispatch,
image URL forwarding, retry/recall flow, and quoted message injection."""

from __future__ import annotations

from dataclasses import replace
from typing import override
from unittest.mock import patch

from packages.app import NekoBotFramework
from packages.contracts.specs import ProviderSpec, RegisteredProvider
from packages.conversations.context import ConfigurationContext, ConversationContext
from packages.llm.handler import LLMHandler, _noop_recall
from packages.providers.base import ChatProvider
from packages.providers.types import (
    ProviderErrorInfo,
    ProviderRequest,
    ProviderResponse,
)
from packages.runtime.context import ExecutionContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class EchoProvider(ChatProvider):
    """Returns the last user message content prefixed with 'echo:'."""

    @override
    @classmethod
    def provider_spec(cls) -> ProviderSpec:
        return ProviderSpec(name="echo", kind="chat", capabilities=("chat",))

    @override
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        last = request.messages[-1].content if request.messages else ""
        return ProviderResponse(content=f"echo:{last}")


class ErrorProvider(ChatProvider):
    """Returns a provider error (retryable by default)."""

    retryable: bool = True
    code: str = "connection_error"

    @override
    @classmethod
    def provider_spec(cls) -> ProviderSpec:
        return ProviderSpec(name="error", kind="chat", capabilities=("chat",))

    @override
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            error=ProviderErrorInfo(
                code=type(self).code,
                message="simulated error",
                retryable=type(self).retryable,
            )
        )


class SucceedAfterFirstProvider(ChatProvider):
    """Fails on first call, succeeds on second."""

    calls: int = 0

    @override
    @classmethod
    def provider_spec(cls) -> ProviderSpec:
        return ProviderSpec(name="succeed-after-first", kind="chat", capabilities=("chat",))

    @override
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        type(self).calls += 1
        if type(self).calls == 1:
            return ProviderResponse(error=ProviderErrorInfo(code="rate_limit", message="slow down", retryable=True))
        return ProviderResponse(content="retry-ok")


def _make_framework(provider_class: type[ChatProvider] | None = None) -> NekoBotFramework:
    fw = NekoBotFramework()
    cls = provider_class or EchoProvider
    fw.runtime_registry.register_provider(RegisteredProvider(provider_class=cls, spec=cls.provider_spec()))
    return fw


def _make_configuration(
    framework: NekoBotFramework,
    *,
    provider: str = "echo",
    extra_plugin_config: dict[str, object] | None = None,
) -> ConfigurationContext:
    plugin_cfg: dict[str, object] = {"wake_keywords": ["cat"]}
    if extra_plugin_config:
        plugin_cfg.update(extra_plugin_config)
    return framework.build_configuration_context(
        framework_config={"default_provider": provider},
        plugin_configs={"llm_chat": plugin_cfg},
    )


def _make_private_execution() -> ExecutionContext:
    return ExecutionContext(
        event_name="message.private",
        actor_id="user-1",
        platform="onebot_v11",
        platform_instance_uuid="inst-1",
        scope="private",
        is_authenticated=True,
    )


def _make_group_execution(*, self_id: str = "bot-99") -> ExecutionContext:
    return ExecutionContext(
        event_name="message.group",
        actor_id="user-1",
        platform="onebot_v11",
        platform_instance_uuid="inst-1",
        scope="group",
        group_id="group-42",
        chat_id="group-42",
        is_authenticated=True,
        metadata={"onebot_self_id": self_id},
    )


async def _make_conversation(framework: NekoBotFramework, cfg: ConfigurationContext) -> ConversationContext:
    return await framework.build_conversation_context(_make_private_execution(), cfg)


async def _run_handler(
    handler: LLMHandler,
    *,
    payload: dict[str, object],
    execution: ExecutionContext | None = None,
    configuration: ConfigurationContext | None = None,
    conversation: ConversationContext | None = None,
    reply: object = None,
    recall: object = None,
) -> list[str]:
    """Drive handle() and collect all replies."""
    replies: list[str] = []

    async def _reply(msg: str) -> str | None:
        replies.append(msg)
        return f"msg-id-{len(replies)}"

    fw = handler.framework
    cfg = configuration or _make_configuration(fw)
    exc = execution or _make_private_execution()
    conv = conversation or await _make_conversation(fw, cfg)

    await handler.handle(
        payload=payload,
        execution=exc,
        configuration=cfg,
        conversation=conv,
        reply=reply or _reply,
        recall=recall or _noop_recall,
    )
    return replies


# ===========================================================================
# Wake logic
# ===========================================================================


async def test_private_chat_always_wakes() -> None:
    fw = _make_framework()
    handler = LLMHandler(fw)
    replies = await _run_handler(
        handler,
        payload={"plain_text": "hello", "effective_text": "hello"},
        execution=_make_private_execution(),
    )
    assert len(replies) == 1
    assert replies[0].startswith("echo:")


async def test_group_no_trigger_does_not_respond() -> None:
    fw = _make_framework()
    handler = LLMHandler(fw)
    replies = await _run_handler(
        handler,
        payload={"plain_text": "random text", "effective_text": "random text", "segments": []},
        execution=_make_group_execution(),
    )
    assert replies == []


async def test_group_wake_keyword_triggers_response() -> None:
    fw = _make_framework()
    cfg = _make_configuration(fw, extra_plugin_config={"wake_keywords": ["cat"]})
    handler = LLMHandler(fw)
    replies = await _run_handler(
        handler,
        payload={"plain_text": "cat hello", "effective_text": "cat hello", "segments": []},
        execution=_make_group_execution(),
        configuration=cfg,
    )
    assert len(replies) == 1


async def test_group_at_mention_triggers_response() -> None:
    fw = _make_framework()
    handler = LLMHandler(fw)
    # @bot segment in payload
    segments = [{"type": "at", "data": {"qq": "bot-99"}}]
    raw_event = {"self_id": "bot-99"}
    replies = await _run_handler(
        handler,
        payload={
            "plain_text": "hello",
            "effective_text": "hello",
            "segments": segments,
            "raw_event": raw_event,
        },
        execution=_make_group_execution(self_id="bot-99"),
    )
    assert len(replies) == 1


async def test_group_reply_to_self_triggers_response() -> None:
    """is_reply_to_self=True in payload must wake the bot in group chat."""
    fw = _make_framework()
    handler = LLMHandler(fw)
    replies = await _run_handler(
        handler,
        payload={
            "plain_text": "what did you say",
            "effective_text": "what did you say",
            "segments": [],
            "is_reply_to_self": True,
        },
        execution=_make_group_execution(),
    )
    assert len(replies) == 1


async def test_empty_plain_text_skipped() -> None:
    """Empty text must be silently ignored even when is_reply_to_self is set."""
    fw = _make_framework()
    handler = LLMHandler(fw)
    replies = await _run_handler(
        handler,
        payload={"plain_text": "   ", "segments": [], "is_reply_to_self": True},
        execution=_make_group_execution(),
    )
    assert replies == []


# ===========================================================================
# Command dispatch
# ===========================================================================


async def test_command_reset_clears_history() -> None:
    fw = _make_framework()
    cfg = _make_configuration(fw)
    conv = await _make_conversation(fw, cfg)
    # Pre-populate history
    conv = replace(
        conv,
        history=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ],
    )
    handler = LLMHandler(fw)
    replies = await _run_handler(
        handler,
        payload={"plain_text": "/reset", "effective_text": "/reset"},
        configuration=cfg,
        conversation=conv,
    )
    assert any("[OK]" in r for r in replies)
    # History should be cleared in the framework's store after reset
    stored = await fw.conversation_store.get_conversation(conv.conversation_key.value if conv.conversation_key else "")
    if stored is not None:
        assert stored.history == []


async def test_command_llm_off_on_toggles_reply() -> None:
    fw = _make_framework()
    cfg = _make_configuration(fw)
    handler = LLMHandler(fw)

    off_replies = await _run_handler(
        handler,
        payload={"plain_text": "/llm off", "effective_text": "/llm off"},
        configuration=cfg,
    )
    assert any("[OFF]" in r for r in off_replies)

    on_replies = await _run_handler(
        handler,
        payload={"plain_text": "/llm on", "effective_text": "/llm on"},
        configuration=cfg,
    )
    assert any("[ON]" in r for r in on_replies)


async def test_command_help_contains_key_commands() -> None:
    fw = _make_framework()
    handler = LLMHandler(fw)
    replies = await _run_handler(
        handler,
        payload={"plain_text": "/help", "effective_text": "/help"},
    )
    assert len(replies) == 1
    text = replies[0]
    assert "/reset" in text
    assert "/llm" in text
    assert "/sid" in text


async def test_command_sid_shows_conversation_key() -> None:
    fw = _make_framework()
    cfg = _make_configuration(fw)
    conv = await _make_conversation(fw, cfg)
    handler = LLMHandler(fw)
    replies = await _run_handler(
        handler,
        payload={"plain_text": "/sid", "effective_text": "/sid"},
        configuration=cfg,
        conversation=conv,
    )
    assert len(replies) == 1
    assert "[SID]" in replies[0]


async def test_unknown_command_does_not_reach_llm() -> None:
    """/foobar should be silently dropped — not echoed back by the LLM."""
    fw = _make_framework()
    handler = LLMHandler(fw)
    replies = await _run_handler(
        handler,
        payload={"plain_text": "/foobar", "effective_text": "/foobar"},
    )
    assert replies == []


async def test_command_llm_model_switch() -> None:
    fw = _make_framework()
    cfg = _make_configuration(fw)
    handler = LLMHandler(fw)
    replies = await _run_handler(
        handler,
        payload={"plain_text": "/llm model gpt-4o", "effective_text": "/llm model gpt-4o"},
        configuration=cfg,
    )
    assert any("gpt-4o" in r for r in replies)


# ===========================================================================
# Image URLs forwarded to provider
# ===========================================================================


async def test_image_urls_forwarded_to_invoke_provider() -> None:
    """image_urls in payload must reach the provider as ProviderRequest.image_urls."""
    fw = _make_framework()
    cfg = _make_configuration(fw)

    captured_requests: list[ProviderRequest] = []

    original_generate = EchoProvider.generate

    async def capturing_generate(self: EchoProvider, request: ProviderRequest) -> ProviderResponse:
        captured_requests.append(request)
        return await original_generate(self, request)

    with patch.object(EchoProvider, "generate", capturing_generate):
        handler = LLMHandler(fw)
        await _run_handler(
            handler,
            payload={
                "plain_text": "describe this",
                "effective_text": "describe this",
                "image_urls": ["https://example.com/img.jpg"],
            },
            configuration=cfg,
        )

    assert len(captured_requests) == 1
    assert captured_requests[0].image_urls == ["https://example.com/img.jpg"]


async def test_no_image_urls_means_empty_list_in_provider() -> None:
    fw = _make_framework()
    cfg = _make_configuration(fw)
    captured: list[ProviderRequest] = []

    async def capturing_generate(self: EchoProvider, request: ProviderRequest) -> ProviderResponse:
        captured.append(request)
        return ProviderResponse(content="ok")

    with patch.object(EchoProvider, "generate", capturing_generate):
        handler = LLMHandler(fw)
        await _run_handler(
            handler,
            payload={"plain_text": "hello", "effective_text": "hello"},
            configuration=cfg,
        )

    assert captured[0].image_urls == []


# ===========================================================================
# quoted_text injection
# ===========================================================================


async def test_quoted_text_injected_into_messages() -> None:
    fw = _make_framework()
    _make_configuration(fw)
    captured: list[ProviderRequest] = []

    async def capturing_generate(self: EchoProvider, request: ProviderRequest) -> ProviderResponse:
        captured.append(request)
        return ProviderResponse(content="ok")

    with patch.object(EchoProvider, "generate", capturing_generate):
        handler = LLMHandler(fw)
        await _run_handler(
            handler,
            payload={
                "plain_text": "what does that say",
                "effective_text": "what does that say",
                "quoted_text": "original quoted content here",
            },
        )

    assert len(captured) == 1
    # quoted_text is merged into system_prompt via extra_context, not a separate message
    assert captured[0].system_prompt is not None
    assert "original quoted content here" in captured[0].system_prompt, (
        "quoted_text not found in system_prompt"
    )


# ===========================================================================
# Retry + recall flow
# ===========================================================================


async def test_retryable_error_triggers_retry() -> None:
    SucceedAfterFirstProvider.calls = 0
    fw = _make_framework(SucceedAfterFirstProvider)
    cfg = _make_configuration(fw, provider="succeed-after-first")

    recalled_ids: list[str] = []
    replies: list[str] = []
    msg_counter = 0

    async def reply(msg: str) -> str | None:
        nonlocal msg_counter
        msg_counter += 1
        replies.append(msg)
        return f"id-{msg_counter}"

    async def recall(msg_id: str) -> None:
        recalled_ids.append(msg_id)

    handler = LLMHandler(fw)
    await handler.handle(
        payload={"plain_text": "hello", "effective_text": "hello"},
        execution=_make_private_execution(),
        configuration=cfg,
        conversation=await _make_conversation(fw, cfg),
        reply=reply,
        recall=recall,
    )

    # First reply is the error message, second is the successful retry
    assert len(replies) == 2
    assert "[ERR:" in replies[0]
    assert "重试" in replies[0]
    assert replies[1] == "retry-ok"
    # Error message should have been recalled
    assert recalled_ids == ["id-1"]


async def test_non_retryable_error_no_retry() -> None:
    ErrorProvider.retryable = False
    ErrorProvider.code = "auth_error"
    fw = _make_framework(ErrorProvider)
    cfg = _make_configuration(fw, provider="error")

    recalled_ids: list[str] = []
    replies: list[str] = []

    async def reply(msg: str) -> str | None:
        replies.append(msg)
        return "id-1"

    async def recall(msg_id: str) -> None:
        recalled_ids.append(msg_id)

    handler = LLMHandler(fw)
    await handler.handle(
        payload={"plain_text": "hello", "effective_text": "hello"},
        execution=_make_private_execution(),
        configuration=cfg,
        conversation=await _make_conversation(fw, cfg),
        reply=reply,
        recall=recall,
    )

    assert len(replies) == 1
    assert "[ERR:auth_error]" in replies[0]
    assert "重试" not in replies[0]
    assert recalled_ids == []


# ===========================================================================
# Multimodal message building (OpenAI provider)
# ===========================================================================


async def test_openai_build_messages_multimodal() -> None:
    """ProviderRequest.image_urls must cause the last user message to become
    a content list with text + image_url blocks."""
    from packages.providers.sources.openai import OpenAIChatProvider
    from packages.providers.types import ChatMessage, ProviderContext

    provider = OpenAIChatProvider(config={"api_key": "x", "default_model": "gpt-4o"})
    request = ProviderRequest(
        messages=[
            ChatMessage(role="user", content="what is in this image"),
        ],
        image_urls=["https://example.com/cat.jpg"],
        context=ProviderContext(provider_name="openai", model="gpt-4o"),
    )

    messages = provider._build_messages(request)

    # Last user message should be multimodal
    last = messages[-1]
    assert isinstance(last, dict)
    content = last["content"]  # type: ignore[index]
    assert isinstance(content, list)
    types = [block["type"] for block in content]  # type: ignore[index]
    assert "text" in types
    assert "image_url" in types
    img_blocks = [b for b in content if b["type"] == "image_url"]  # type: ignore[index]
    assert img_blocks[0]["image_url"]["url"] == "https://example.com/cat.jpg"  # type: ignore[index]


async def test_openai_build_messages_no_images_stays_string() -> None:
    """Without image_urls, content must remain a plain string."""
    from packages.providers.sources.openai import OpenAIChatProvider
    from packages.providers.types import ChatMessage, ProviderContext

    provider = OpenAIChatProvider(config={"api_key": "x", "default_model": "gpt-4o"})
    request = ProviderRequest(
        messages=[ChatMessage(role="user", content="hello")],
        image_urls=[],
        context=ProviderContext(provider_name="openai", model="gpt-4o"),
    )
    messages = provider._build_messages(request)
    last = messages[-1]
    assert last["content"] == "hello"  # type: ignore[index]
