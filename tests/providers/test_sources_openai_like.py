from __future__ import annotations

from typing import cast

from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
    Function,
)

from packages.providers.sources.openai import OPENAI_MODELS, OpenAIChatProvider
from packages.providers.sources.openai_compatible import OpenAICompatibleChatProvider
from packages.providers.types import ChatMessage, ProviderRequest, ToolDefinition


class OpenAIHarness(OpenAIChatProvider):
    def resolve_model_for_test(self, request: ProviderRequest) -> str | None:
        return self._resolve_model(request)

    def build_messages_for_test(self, request: ProviderRequest):
        return self._build_messages(request)

    def build_tools_for_test(self, tools: list[ToolDefinition]):
        return self._build_tools(tools)

    def parse_tool_calls_for_test(self, tool_calls: object):
        return self._parse_tool_calls(tool_calls)


class OpenAICompatibleHarness(OpenAICompatibleChatProvider):
    pass


def test_openai_resolve_model_prefers_request_model() -> None:
    provider = OpenAIHarness(config={"api_key": "x", "default_model": "gpt-4.1"})
    request = ProviderRequest(model="gpt-4.1-mini")

    assert provider.resolve_model_for_test(request) == "gpt-4.1-mini"


def test_openai_resolve_model_falls_back_to_config_then_default_catalog() -> None:
    configured = OpenAIHarness(config={"api_key": "x", "default_model": "gpt-4.1"})
    fallback = OpenAIHarness(config={"api_key": "x"})

    assert configured.resolve_model_for_test(ProviderRequest()) == "gpt-4.1"
    assert fallback.resolve_model_for_test(ProviderRequest()) == OPENAI_MODELS[0].id


def test_openai_build_messages_includes_system_prompt_prompt_and_named_messages() -> (
    None
):
    provider = OpenAIHarness(config={"api_key": "x"})
    request = ProviderRequest(
        prompt="user prompt",
        system_prompt="system prompt",
        messages=[
            ChatMessage(role="assistant", content="reply", name="bot"),
        ],
    )

    messages = provider.build_messages_for_test(request)
    system_message = cast(dict[str, object], cast(object, messages[0]))
    user_message = cast(dict[str, object], cast(object, messages[1]))
    assistant_message = cast(dict[str, object], cast(object, messages[2]))

    assert system_message["role"] == "system"
    assert system_message["content"] == "system prompt"
    assert user_message["role"] == "user"
    assert user_message["content"] == "user prompt"
    assert assistant_message["role"] == "assistant"
    assert assistant_message.get("content") == "reply"
    assert assistant_message.get("name") == "bot"


def test_openai_build_tools_maps_tool_definitions_to_function_payloads() -> None:
    provider = OpenAIHarness(config={"api_key": "x"})
    tools = [
        ToolDefinition(
            name="weather",
            description="Get weather",
            parameters={"type": "object", "properties": {"city": {"type": "string"}}},
        )
    ]

    payload = provider.build_tools_for_test(tools)
    tool_payload = cast(dict[str, object], cast(object, payload[0]))
    function_payload = cast(dict[str, object], tool_payload["function"])

    assert tool_payload["type"] == "function"
    assert function_payload["name"] == "weather"
    assert function_payload.get("description") == "Get weather"


def test_openai_parse_tool_calls_extracts_arguments_from_json() -> None:
    provider = OpenAIHarness(config={"api_key": "x"})
    tool_calls = [
        ChatCompletionMessageFunctionToolCall(
            id="call-1",
            type="function",
            function=Function(name="weather", arguments='{"city":"Tokyo"}'),
        ),
        ChatCompletionMessageFunctionToolCall(
            id="call-2",
            type="function",
            function=Function(name="echo", arguments='"raw-value"'),
        ),
    ]

    parsed = provider.parse_tool_calls_for_test(tool_calls)

    assert parsed[0].id == "call-1"
    assert parsed[0].name == "weather"
    assert parsed[0].arguments == {"city": "Tokyo"}
    assert parsed[1].arguments == {"value": "raw-value"}


def test_openai_compatible_provider_info_marks_base_url_requirement() -> None:
    provider = OpenAICompatibleHarness(
        config={"api_key": "x", "base_url": "https://example.com"}
    )

    info = provider.provider_info()

    assert info.name == "openai_compatible"
    assert info.models == ()
    assert info.metadata["requires_base_url"] is True
