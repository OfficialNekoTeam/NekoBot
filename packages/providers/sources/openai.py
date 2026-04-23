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
        "base_url": StringField(required=False),
        "api_flavor": StringField(required=False),
        "store": BooleanField(required=False),
        "reasoning_effort": StringField(required=False),
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
            base_url=cast(str | None, self.config.get("base_url")),
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
        api_flavor = self.config.get("api_flavor", "chat_completions")
        if api_flavor == "responses":
            return await self._generate_via_responses(request)
        return await self._generate_via_chat(request)

    async def _generate_via_chat(self, request: ProviderRequest) -> ProviderResponse:
        client = self._require_client()
        model = self._resolve_model(request)
        if not model:
            raise ValueError("OpenAI provider requires a model")

        messages = self._build_messages(request)
        tools = self._build_tools(request.tools)
        
        # Reasoning effort for o1/o3
        reasoning_effort = self.config.get("reasoning_effort") or request.options.get("reasoning_effort")
        
        create_kwargs: dict[str, object] = {
            "model": model,
            "messages": messages,
            "stream": request.stream,
        }
        if tools:
            create_kwargs["tools"] = tools
        if reasoning_effort:
            create_kwargs["reasoning_effort"] = reasoning_effort

        try:
            response = cast(
                ChatCompletion,
                await client.chat.completions.create(**create_kwargs),
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

        # Reasoning extraction
        metadata: dict[str, object] = {"model": model}
        
        # DeepSeek reasoning_content
        reasoning_content = getattr(message, "reasoning_content", None)
        if reasoning_content:
            metadata["reasoning"] = reasoning_content
            
        # OpenAI reasoning tokens
        if response.usage and hasattr(response.usage, "completion_tokens_details"):
            details = response.usage.completion_tokens_details
            if hasattr(details, "reasoning_tokens") and details.reasoning_tokens:
                metadata["reasoning_tokens"] = details.reasoning_tokens

        return ProviderResponse(
            content=content,
            messages=[
                ChatMessage(
                    role="assistant",
                    content=content or "",
                    metadata=metadata,
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

    async def _generate_via_responses(self, request: ProviderRequest) -> ProviderResponse:
        client = self._require_client()
        model = self._resolve_model(request)
        if not model:
            raise ValueError("OpenAI provider requires a model")

        # This requires the responses experimental/new API. 
        # For compatible providers, we use the standard attribute access.
        try:
            responses_api = getattr(client, "responses", None)
            if not responses_api:
                raise RuntimeError("OpenAI SDK does not support Responses API or provider does not implement it")

            input_items = self._build_input_items(request)
            tools = self._build_tools(request.tools)
            
            store = self.config.get("store", False)
            reasoning_effort = self.config.get("reasoning_effort") or request.options.get("reasoning_effort")

            create_kwargs: dict[str, object] = {
                "model": model,
                "input": input_items,
                "store": store,
            }
            if tools:
                create_kwargs["tools"] = tools
            if reasoning_effort:
                create_kwargs["reasoning_effort"] = reasoning_effort

            response = await responses_api.create(**create_kwargs)
            
            # Parse responses API response (slightly different structure)
            # Typically returns a Response object with 'output_items'
            output_items = getattr(response, "output_items", [])
            content = ""
            tool_calls: list[ToolCall] = []
            reasoning = ""

            for item in output_items:
                if item.type == "message" and item.role == "assistant":
                    for part in item.content:
                        if part.type == "text":
                            content += part.text
                        elif part.type == "reasoning":
                            reasoning += part.reasoning
                elif item.type == "function_call":
                    tool_calls.append(ToolCall(
                        id=item.call_id,
                        name=item.name,
                        arguments=json.loads(item.arguments) if isinstance(item.arguments, str) else item.arguments
                    ))

            metadata: dict[str, object] = {"model": model, "response_id": response.id}
            if reasoning:
                metadata["reasoning"] = reasoning

            return ProviderResponse(
                content=content,
                messages=[ChatMessage(role="assistant", content=content, metadata=metadata)],
                tool_calls=tool_calls,
                finish_reason=getattr(response, "status", "completed"),
                usage=TokenUsage(
                    input_tokens=response.usage.input_tokens if hasattr(response, "usage") else 0,
                    output_tokens=response.usage.output_tokens if hasattr(response, "usage") else 0,
                    total_tokens=response.usage.total_tokens if hasattr(response, "usage") else 0,
                ),
                raw=response,
            )
        except Exception as exc:
            return ProviderResponse(
                finish_reason="error",
                error=ProviderErrorInfo(code="responses_api_error", message=str(exc)),
                raw=exc,
            )

    def _build_input_items(self, request: ProviderRequest) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        
        # System instructions
        if request.system_prompt:
            items.append({"type": "text", "text": request.system_prompt})
            
        # Initial prompt if any
        if request.prompt:
            items.append({"type": "user_message", "content": request.prompt})
            
        for message in request.messages:
            role = message.role
            content = message.content
            
            if role == "user":
                items.append({"type": "user_message", "content": content})
            elif role == "assistant":
                # Convert tool calls to individual items if present
                tool_calls = message.metadata.get("tool_calls")
                if tool_calls:
                    # Item-based API likes flat structure
                    if content:
                        items.append({
                            "type": "message", "role": "assistant",
                            "content": [{"type": "text", "text": content}],
                        })
                    for tc in tool_calls:
                        items.append({
                            "type": "function_call",
                            "call_id": tc.get("id"),
                            "name": tc.get("function", {}).get("name"),
                            "arguments": tc.get("function", {}).get("arguments"),
                        })
                else:
                    items.append({
                        "type": "message", "role": "assistant",
                        "content": [{"type": "text", "text": content}],
                    })
            elif role == "tool":
                items.append({
                    "type": "function_call_output",
                    "call_id": message.metadata.get("tool_call_id"),
                    "output": content
                })
        return items

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
        for idx, message in enumerate(request.messages):
            role = message.role
            content = message.content
            payload: dict[str, object] = {
                "role": role,
                "content": content,
            }
            if message.name:
                payload["name"] = message.name
            
            # 处理 tool_calls (assistant)
            tool_calls = message.metadata.get("tool_calls")
            if role == "assistant" and tool_calls:
                payload["tool_calls"] = tool_calls
            
            # 处理 tool_call_id (tool)
            tool_call_id = message.metadata.get("tool_call_id")
            if role == "tool" and tool_call_id:
                payload["tool_call_id"] = tool_call_id

            messages.append(cast(ChatCompletionMessageParam, cast(object, payload)))

        # If image_urls present, transform the last user message into multimodal content
        if request.image_urls and messages:
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                if not isinstance(msg, dict):
                    continue
                if cast(dict[object, object], msg).get("role") == "user":
                    text_content = cast(dict[object, object], msg).get("content", "")
                    content_parts: list[dict[str, object]] = []
                    if text_content:
                        content_parts.append({"type": "text", "text": str(text_content)})
                    for url in request.image_urls:
                        content_parts.append(
                            {"type": "image_url", "image_url": {"url": url}}
                        )
                    messages[i] = cast(
                        ChatCompletionMessageParam,
                        cast(object, {"role": "user", "content": content_parts}),
                    )
                    break

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
