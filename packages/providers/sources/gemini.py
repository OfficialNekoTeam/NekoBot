from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast, override

from google import genai
from google.genai import types

from ...decorators import provider
from ...schema import (
    BooleanField,
    IntegerField,
    ObjectSchema,
    SchemaRegistry,
    StringField,
)
from ..base import ChatProvider
from ..types import (
    ChatMessage,
    ModelCapability,
    ModelDescriptor,
    ProviderErrorInfo,
    ProviderInfo,
    ProviderKind,
    ProviderRequest,
    ProviderResponse,
    TokenUsage,
    ToolCall,
    ToolDefinition,
    ValueMap,
)

GEMINI_PROVIDER_SCHEMA = ObjectSchema(
    fields={
        "api_key": StringField(min_length=1),
        "default_model": StringField(required=False),
        "max_output_tokens": IntegerField(required=False, minimum=1),
        "timeout_seconds": IntegerField(required=False, minimum=1),
        "enable_streaming": BooleanField(required=False),
    }
)

GEMINI_MODELS = (
    ModelDescriptor(
        id="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        provider_name="gemini",
        capabilities=(ModelCapability(name="chat"), ModelCapability(name="tool_call")),
    ),
    ModelDescriptor(
        id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        provider_name="gemini",
        capabilities=(ModelCapability(name="chat"), ModelCapability(name="tool_call")),
    ),
)


@provider(
    name="gemini",
    kind=ProviderKind.CHAT,
    description="Google Gemini chat provider",
    config_schema_name="provider.gemini",
    capabilities=("chat", "tool_call", "stream"),
    metadata={"models": GEMINI_MODELS, "provider_family": "gemini"},
)
class GeminiChatProvider(ChatProvider):
    def __init__(
        self,
        config: ValueMap | None = None,
        schema_registry: SchemaRegistry | None = None,
    ) -> None:
        super().__init__(config=config, schema_registry=schema_registry)
        self._client: genai.Client | None = None

    @override
    async def setup(self) -> None:
        self._client = genai.Client(api_key=cast(str, self.config.get("api_key")))

    @override
    async def teardown(self) -> None:
        self._client = None

    @override
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        client = self._require_client()
        model = self._resolve_model(request)
        if not model:
            raise ValueError("Gemini provider requires a model")

        config = types.GenerateContentConfig(
            system_instruction=request.system_prompt,
            max_output_tokens=self._resolve_max_output_tokens(request),
            tools=self._build_tools(request.tools) or None,
        )
        try:
            generate_content = cast(
                Callable[..., Awaitable[object]],
                getattr(client.aio.models, "generate_content"),
            )
            response = cast(
                types.GenerateContentResponse,
                await generate_content(
                    model=model,
                    contents=self._build_contents(request),
                    config=config,
                ),
            )
        except Exception as exc:
            return ProviderResponse(
                finish_reason="error",
                error=ProviderErrorInfo(
                    code="gemini_error",
                    message=str(exc),
                    retryable=False,
                ),
                raw=exc,
            )

        content = response.text or None
        tool_calls = self._parse_tool_calls(response)
        usage = response.usage_metadata

        return ProviderResponse(
            content=content,
            messages=[
                ChatMessage(
                    role="assistant",
                    content=content or "",
                    metadata={"model": model},
                )
            ],
            tool_calls=tool_calls,
            finish_reason=getattr(response, "finish_reason", None),
            usage=TokenUsage(
                input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
                total_tokens=getattr(usage, "total_token_count", 0) or 0,
            ),
            raw=response,
        )

    @override
    def provider_info(self) -> ProviderInfo:
        info = super().provider_info()
        return ProviderInfo(
            name=info.name,
            kind=info.kind,
            description=info.description,
            capabilities=info.capabilities,
            models=GEMINI_MODELS,
            metadata=info.metadata,
        )

    def _require_client(self) -> genai.Client:
        if self._client is None:
            raise RuntimeError("Gemini provider is not initialized")
        return self._client

    def _resolve_model(self, request: ProviderRequest) -> str | None:
        if request.model:
            return request.model
        configured = self.config.get("default_model")
        if isinstance(configured, str) and configured:
            return configured
        return GEMINI_MODELS[0].id if GEMINI_MODELS else None

    def _resolve_max_output_tokens(self, request: ProviderRequest) -> int | None:
        configured = request.options.get("max_output_tokens")
        if isinstance(configured, int) and configured > 0:
            return configured
        default_tokens = self.config.get("max_output_tokens")
        if isinstance(default_tokens, int) and default_tokens > 0:
            return default_tokens
        return None

    def _build_contents(self, request: ProviderRequest) -> list[types.Content]:
        contents: list[types.Content] = []
        if request.prompt:
            contents.append(
                types.Content(role="user", parts=[types.Part(text=request.prompt)])
            )
        for message in request.messages:
            role = "model" if message.role == "assistant" else message.role
            contents.append(
                types.Content(role=role, parts=[types.Part(text=message.content)])
            )
        return contents

    def _build_tools(self, tools: list[ToolDefinition]) -> list[types.Tool]:
        if not tools:
            return []
        declarations = [
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters_json_schema=tool.parameters,
            )
            for tool in tools
        ]
        return [types.Tool(function_declarations=declarations)]

    def _parse_tool_calls(self, response: object) -> list[ToolCall]:
        candidates = cast(object, getattr(response, "candidates", None))
        if not isinstance(candidates, list):
            return []
        parsed: list[ToolCall] = []
        for candidate in cast(list[object], candidates):
            content = cast(object, getattr(candidate, "content", None))
            parts = cast(object, getattr(content, "parts", None))
            if not isinstance(parts, list):
                continue
            for part in cast(list[object], parts):
                function_call = cast(object, getattr(part, "function_call", None))
                if function_call is None:
                    continue
                raw_args = cast(object, getattr(function_call, "args", {}))
                parsed.append(
                    ToolCall(
                        name=getattr(function_call, "name", ""),
                        arguments=cast(dict[str, object], raw_args)
                        if isinstance(raw_args, dict)
                        else {},
                    )
                )
        return parsed
