from __future__ import annotations

import json
from typing import cast, override

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageParam,
    ChatCompletionToolUnionParam,
)
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)

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

OPENAI_PROVIDER_SCHEMA = ObjectSchema(
    fields={
        "api_key": StringField(min_length=1),
        "default_model": StringField(required=False),
        "organization": StringField(required=False),
        "project": StringField(required=False),
        "timeout_seconds": IntegerField(required=False, minimum=1),
        "enable_streaming": BooleanField(required=False),
    }
)

OPENAI_MODELS = (
    ModelDescriptor(
        id="gpt-4.1-mini",
        display_name="GPT-4.1 mini",
        provider_name="openai",
        capabilities=(ModelCapability(name="chat"), ModelCapability(name="tool_call")),
    ),
    ModelDescriptor(
        id="gpt-4.1",
        display_name="GPT-4.1",
        provider_name="openai",
        capabilities=(ModelCapability(name="chat"), ModelCapability(name="tool_call")),
    ),
)


@provider(
    name="openai",
    kind=ProviderKind.CHAT,
    description="Official OpenAI chat provider",
    config_schema_name="provider.openai",
    capabilities=("chat", "tool_call", "stream"),
    metadata={"models": OPENAI_MODELS, "provider_family": "openai"},
)
class OpenAIChatProvider(ChatProvider):
    def __init__(
        self,
        config: ValueMap | None = None,
        schema_registry: SchemaRegistry | None = None,
    ) -> None:
        super().__init__(config=config, schema_registry=schema_registry)
        self._client: AsyncOpenAI | None = None

    @override
    async def setup(self) -> None:
        self._client = AsyncOpenAI(
            api_key=cast(str, self.config.get("api_key")),
            organization=cast(str | None, self.config.get("organization")),
            project=cast(str | None, self.config.get("project")),
            timeout=cast(int | None, self.config.get("timeout_seconds")),
        )

    @override
    async def teardown(self) -> None:
        if self._client is None:
            return
        await self._client.close()
        self._client = None

    @override
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        client = self._require_client()
        model = self._resolve_model(request)
        if not model:
            raise ValueError("OpenAI provider requires a model")

        messages = self._build_messages(request)
        tools = self._build_tools(request.tools)
        try:
            if tools:
                response = cast(
                    ChatCompletion,
                    await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        tools=tools,
                        stream=request.stream,
                    ),
                )
            else:
                response = cast(
                    ChatCompletion,
                    await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        stream=request.stream,
                    ),
                )
        except RateLimitError as exc:
            return ProviderResponse(
                finish_reason="error",
                error=ProviderErrorInfo(
                    code="rate_limit",
                    message=str(exc),
                    retryable=True,
                ),
                raw=exc,
            )
        except APIConnectionError as exc:
            return ProviderResponse(
                finish_reason="error",
                error=ProviderErrorInfo(
                    code="connection_error",
                    message=str(exc),
                    retryable=True,
                ),
                raw=exc,
            )
        except APIStatusError as exc:
            return ProviderResponse(
                finish_reason="error",
                error=ProviderErrorInfo(
                    code=f"api_status_{exc.status_code}",
                    message=str(exc),
                    retryable=500 <= exc.status_code < 600,
                ),
                raw=exc,
            )

        choice = response.choices[0]
        message = choice.message
        content = message.content if isinstance(message.content, str) else None
        tool_calls = self._parse_tool_calls(message.tool_calls)

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
            finish_reason=choice.finish_reason,
            usage=TokenUsage(
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
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
            models=OPENAI_MODELS,
            metadata=info.metadata,
        )

    def _require_client(self) -> AsyncOpenAI:
        if self._client is None:
            raise RuntimeError("OpenAI provider is not initialized")
        return self._client

    def _resolve_model(self, request: ProviderRequest) -> str | None:
        if request.model:
            return request.model
        configured = self.config.get("default_model")
        if isinstance(configured, str) and configured:
            return configured
        return OPENAI_MODELS[0].id if OPENAI_MODELS else None

    def _build_messages(
        self, request: ProviderRequest
    ) -> list[ChatCompletionMessageParam]:
        messages: list[ChatCompletionMessageParam] = []
        if request.system_prompt:
            messages.append(
                cast(
                    ChatCompletionMessageParam,
                    cast(object, {"role": "system", "content": request.system_prompt}),
                )
            )
        if request.prompt:
            messages.append(
                cast(
                    ChatCompletionMessageParam,
                    cast(object, {"role": "user", "content": request.prompt}),
                )
            )
        for message in request.messages:
            payload: dict[str, object] = {
                "role": message.role,
                "content": message.content,
            }
            if message.name:
                payload["name"] = message.name
            messages.append(cast(ChatCompletionMessageParam, cast(object, payload)))
        return messages

    def _build_tools(
        self, tools: list[ToolDefinition]
    ) -> list[ChatCompletionToolUnionParam]:
        payloads: list[ChatCompletionToolUnionParam] = []
        for tool in tools:
            payloads.append(
                cast(
                    ChatCompletionToolUnionParam,
                    cast(
                        object,
                        {
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.parameters,
                            },
                        },
                    ),
                )
            )
        return payloads

    def _parse_tool_calls(self, tool_calls: object) -> list[ToolCall]:
        if not isinstance(tool_calls, list):
            return []
        parsed: list[ToolCall] = []
        for raw_call in cast(list[object], tool_calls):
            if not isinstance(raw_call, ChatCompletionMessageFunctionToolCall):
                continue
            call = raw_call
            function = call.function
            name = function.name
            arguments_raw = function.arguments
            try:
                arguments: object = cast(object, json.loads(arguments_raw))
            except (TypeError, json.JSONDecodeError):
                arguments = {"raw": arguments_raw}
            arguments_map: ValueMap
            if isinstance(arguments, dict):
                mapping = cast(dict[object, object], arguments)
                arguments_map = {
                    str(key): value
                    for key, value in mapping.items()
                    if isinstance(key, str)
                }
            else:
                arguments_map = {"value": arguments}
            parsed.append(
                ToolCall(
                    id=call.id,
                    name=name,
                    arguments=arguments_map,
                )
            )
        return parsed
