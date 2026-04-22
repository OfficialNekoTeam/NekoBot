from __future__ import annotations

from typing import cast

from anthropic.types import TextBlock, ToolUseBlock
from google.genai import types

from packages.providers.sources.anthropic import ANTHROPIC_MODELS, AnthropicChatProvider
from packages.providers.sources.gemini import GEMINI_MODELS, GeminiChatProvider
from packages.providers.types import ChatMessage, ProviderRequest, ToolDefinition


class AnthropicHarness(AnthropicChatProvider):
    def resolve_model_for_test(self, request: ProviderRequest) -> str | None:
        return self._resolve_model(request)

    def resolve_max_tokens_for_test(self, request: ProviderRequest) -> int:
        return self._resolve_max_tokens(request)

    async def build_messages_for_test(self, request: ProviderRequest):
        return await self._build_messages(request)

    def build_tools_for_test(self, tools: list[ToolDefinition]):
        return self._build_tools(tools)


class GeminiHarness(GeminiChatProvider):
    def resolve_model_for_test(self, request: ProviderRequest) -> str | None:
        return self._resolve_model(request)

    def resolve_max_output_tokens_for_test(
        self, request: ProviderRequest
    ) -> int | None:
        return self._resolve_max_output_tokens(request)

    def build_contents_for_test(self, request: ProviderRequest):
        return self._build_contents(request)

    def build_tools_for_test(self, tools: list[ToolDefinition]):
        return self._build_tools(tools)

    def parse_tool_calls_for_test(self, response: object):
        return self._parse_tool_calls(response)


class FakeGeminiCandidate:
    def __init__(self, content: types.Content) -> None:
        self.content: types.Content = content


class FakeGeminiResponse:
    def __init__(self, candidates: list[FakeGeminiCandidate]) -> None:
        self.candidates: list[FakeGeminiCandidate] = candidates


def test_anthropic_resolve_model_prefers_request_and_config_then_catalog() -> None:
    configured = AnthropicHarness(
        config={"api_key": "x", "default_model": "claude-3-7-sonnet-latest"}
    )
    fallback = AnthropicHarness(config={"api_key": "x"})

    assert (
        configured.resolve_model_for_test(ProviderRequest(model="claude-custom"))
        == "claude-custom"
    )
    assert (
        configured.resolve_model_for_test(ProviderRequest())
        == "claude-3-7-sonnet-latest"
    )
    assert fallback.resolve_model_for_test(ProviderRequest()) == ANTHROPIC_MODELS[0].id


def test_anthropic_resolve_max_tokens_prefers_request_then_config_then_default() -> (
    None
):
    provider = AnthropicHarness(config={"api_key": "x", "max_tokens": 2048})

    assert (
        provider.resolve_max_tokens_for_test(
            ProviderRequest(options={"max_tokens": 512})
        )
        == 512
    )
    assert provider.resolve_max_tokens_for_test(ProviderRequest()) == 2048
    assert (
        AnthropicHarness(config={"api_key": "x"}).resolve_max_tokens_for_test(
            ProviderRequest()
        )
        == 1024
    )


async def test_anthropic_build_messages_and_tools() -> None:
    provider = AnthropicHarness(config={"api_key": "x"})
    request = ProviderRequest(
        prompt="hello",
        messages=[ChatMessage(role="assistant", content="world")],
        tools=[
            ToolDefinition(
                name="weather", description="Get weather", parameters={"type": "object"}
            )
        ],
    )

    messages = await provider.build_messages_for_test(request)
    tools = provider.build_tools_for_test(request.tools)
    first_message = cast(dict[str, object], cast(object, messages[0]))
    second_message = cast(dict[str, object], cast(object, messages[1]))
    first_tool = cast(dict[str, object], cast(object, tools[0]))

    assert first_message["role"] == "user"
    assert first_message["content"] == "hello"
    assert second_message["role"] == "assistant"
    assert first_tool["name"] == "weather"
    assert first_tool.get("input_schema") == {"type": "object"}


def test_anthropic_provider_info_includes_models() -> None:
    provider = AnthropicHarness(config={"api_key": "x"})

    info = provider.provider_info()

    assert info.models == ANTHROPIC_MODELS
    assert info.metadata["provider_family"] == "anthropic"


def test_gemini_resolve_model_and_max_output_tokens() -> None:
    provider = GeminiHarness(
        config={
            "api_key": "x",
            "default_model": "gemini-2.5-pro",
            "max_output_tokens": 2048,
        }
    )

    assert (
        provider.resolve_model_for_test(ProviderRequest(model="gemini-custom"))
        == "gemini-custom"
    )
    assert provider.resolve_model_for_test(ProviderRequest()) == "gemini-2.5-pro"
    assert (
        provider.resolve_max_output_tokens_for_test(
            ProviderRequest(options={"max_output_tokens": 256})
        )
        == 256
    )
    assert provider.resolve_max_output_tokens_for_test(ProviderRequest()) == 2048


def test_gemini_build_contents_and_tools() -> None:
    provider = GeminiHarness(config={"api_key": "x"})
    request = ProviderRequest(
        prompt="hello",
        messages=[ChatMessage(role="assistant", content="world")],
        tools=[
            ToolDefinition(
                name="weather", description="Get weather", parameters={"type": "object"}
            )
        ],
    )

    contents = provider.build_contents_for_test(request)
    tools = provider.build_tools_for_test(request.tools)

    assert contents[0].role == "user"
    assert contents[0].parts is not None
    assert contents[0].parts[0].text == "hello"
    assert contents[1].role == "model"
    assert contents[1].parts is not None
    assert contents[1].parts[0].text == "world"
    assert tools[0].function_declarations is not None
    assert tools[0].function_declarations[0].name == "weather"


def test_gemini_parse_tool_calls_extracts_function_call_data() -> None:
    provider = GeminiHarness(config={"api_key": "x"})
    response = FakeGeminiResponse(
        candidates=[
            FakeGeminiCandidate(
                types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            functionCall=types.FunctionCall(
                                name="weather",
                                args={"city": "Tokyo"},
                            )
                        )
                    ],
                )
            )
        ]
    )

    tool_calls = provider.parse_tool_calls_for_test(response)

    assert len(tool_calls) == 1
    assert tool_calls[0].name == "weather"
    assert tool_calls[0].arguments == {"city": "Tokyo"}


def test_gemini_provider_info_includes_models() -> None:
    provider = GeminiHarness(config={"api_key": "x"})

    info = provider.provider_info()

    assert info.models == GEMINI_MODELS
    assert info.metadata["provider_family"] == "gemini"


def test_anthropic_tool_blocks_can_be_parsed_like_runtime_blocks() -> None:
    text_block = TextBlock(type="text", text="hello")
    tool_block = ToolUseBlock(
        type="tool_use",
        id="tool-1",
        name="weather",
        input={"city": "Tokyo"},
    )

    assert text_block.text == "hello"
    assert tool_block.name == "weather"
    assert tool_block.input == {"city": "Tokyo"}
