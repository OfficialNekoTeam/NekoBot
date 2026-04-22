from __future__ import annotations

import base64
import json
from typing import cast, override

from anthropic import (
    APIConnectionError,
    APIStatusError,
    AsyncAnthropic,
    RateLimitError,
)
from anthropic.types import Message, TextBlock, ToolUseBlock
from anthropic.types.message_param import MessageParam
from anthropic.types.tool_union_param import ToolUnionParam

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

ANTHROPIC_PROVIDER_SCHEMA = ObjectSchema(
    fields={
        "api_key": StringField(min_length=1),
        "default_model": StringField(required=False),
        "base_url": StringField(required=False),
        "max_tokens": IntegerField(required=False, minimum=1),
        "timeout_seconds": IntegerField(required=False, minimum=1),
        "enable_streaming": BooleanField(required=False),
    }
)

ANTHROPIC_MODELS = (
    ModelDescriptor(
        id="claude-sonnet-4-20250514",
        display_name="Claude Sonnet 4",
        provider_name="anthropic",
        capabilities=(ModelCapability(name="chat"), ModelCapability(name="tool_call")),
    ),
    ModelDescriptor(
        id="claude-3-7-sonnet-latest",
        display_name="Claude 3.7 Sonnet",
        provider_name="anthropic",
        capabilities=(ModelCapability(name="chat"), ModelCapability(name="tool_call")),
    ),
)


@provider(
    name="anthropic",
    kind=ProviderKind.CHAT,
    description="Anthropic Claude chat provider",
    config_schema_name="provider.anthropic",
    capabilities=("chat", "tool_call", "stream"),
    metadata={"models": ANTHROPIC_MODELS, "provider_family": "anthropic"},
)
class AnthropicChatProvider(ChatProvider):
    def __init__(
        self,
        config: ValueMap | None = None,
        schema_registry: SchemaRegistry | None = None,
    ) -> None:
        super().__init__(config=config, schema_registry=schema_registry)
        self._client: AsyncAnthropic | None = None

    @override
    async def setup(self) -> None:
        self._client = AsyncAnthropic(
            api_key=cast(str, self.config.get("api_key")),
            base_url=cast(str | None, self.config.get("base_url")),
            timeout=cast(int | None, self.config.get("timeout_seconds")),
        )

    @override
    async def teardown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _build_messages(self, request: ProviderRequest) -> list[MessageParam]:
        messages: list[MessageParam] = []
        
        # 处理初始 prompt
        if request.prompt:
            content = (
                await self._build_multimodal_content(request.prompt, request.image_urls)
                if request.image_urls
                else request.prompt
            )
            messages.append(
                cast(MessageParam, {"role": "user", "content": content})
            )

        # 处理历史消息
        for idx, message in enumerate(request.messages):
            role = message.role
            content: str | list[dict[str, object]] = message.content
            
            # 如果是最后一条 user 消息且有 image_urls
            is_last_user = (role == "user" and not any(m.role == "user" for m in request.messages[idx+1:]))
            if is_last_user and request.image_urls and not request.prompt:
                content = await self._build_multimodal_content(message.content, request.image_urls)

            if role == "assistant":
                blocks: list[dict[str, object]] = []
                if content:
                    blocks.append({"type": "text", "text": cast(str, content)})
                
                tool_calls = message.metadata.get("tool_calls")
                if isinstance(tool_calls, list):
                    for tc in tool_calls:
                        blocks.append({
                            "type": "tool_use",
                            "id": tc.get("id"),
                            "name": tc.get("function", {}).get("name"),
                            "input": (
                                base64.b64decode(tc.get("function", {}).get("arguments"))
                                if isinstance(tc.get("function", {}).get("arguments"), bytes)
                                else tc.get("function", {}).get("arguments")
                            ),
                        })
                        # Handle string arguments
                        if isinstance(blocks[-1]["input"], str):
                            try:
                                blocks[-1]["input"] = json.loads(blocks[-1]["input"])
                            except Exception:
                                pass
                
                messages.append(cast(MessageParam, {"role": "assistant", "content": blocks}))
            
            elif role == "tool":
                # Claude requires tool results to be in a 'user' message as tool_result blocks
                messages.append(cast(MessageParam, {
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": message.metadata.get("tool_call_id"),
                        "content": content,
                    }]
                }))
            
            else:
                messages.append(cast(MessageParam, {"role": role, "content": content}))
                
        return messages

    async def _build_multimodal_content(self, text: str | None, image_urls: list[str]) -> list[dict[str, object]]:
        content: list[dict[str, object]] = []
        if text:
            content.append({"type": "text", "text": text})
        
        for url in image_urls:
            if url.startswith("data:"):
                try:
                    header, data = url.split(",", 1)
                    mime_type = header.split(";")[0].split(":")[1]
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": data,
                        }
                    })
                except Exception:
                    continue
        return content

    @override
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        client = self._require_client()
        model = self._resolve_model(request)
        if not model:
            raise ValueError("Anthropic provider requires a model")

        messages = await self._build_messages(request)
        system = request.system_prompt or cast(
            str | None, request.options.get("system")
        )
        tools = self._build_tools(request.tools)

        create_kwargs: dict[str, object] = dict(
            model=model,
            max_tokens=self._resolve_max_tokens(request),
            messages=messages,
            stream=request.stream,
        )
        if system is not None:
            create_kwargs["system"] = system
        if tools:
            create_kwargs["tools"] = tools

        try:
            response = cast(Message, await client.messages.create(**create_kwargs))
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

        text_blocks = [
            block for block in response.content if isinstance(block, TextBlock)
        ]
        tool_blocks = [
            block for block in response.content if isinstance(block, ToolUseBlock)
        ]
        content = "\n".join(block.text for block in text_blocks).strip() or None
        tool_calls = [
            ToolCall(
                id=block.id,
                name=block.name,
                arguments=block.input,
            )
            for block in tool_blocks
        ]

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
            finish_reason=response.stop_reason,
            usage=TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
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
            models=ANTHROPIC_MODELS,
            metadata=info.metadata,
        )

    def _require_client(self) -> AsyncAnthropic:
        if self._client is None:
            raise RuntimeError("Anthropic provider is not initialized")
        return self._client

    def _resolve_model(self, request: ProviderRequest) -> str | None:
        if request.model:
            return request.model
        configured = self.config.get("default_model")
        if isinstance(configured, str) and configured:
            return configured
        return ANTHROPIC_MODELS[0].id if ANTHROPIC_MODELS else None

    def _resolve_max_tokens(self, request: ProviderRequest) -> int:
        configured = request.options.get("max_tokens")
        if isinstance(configured, int) and configured > 0:
            return configured
        default_tokens = self.config.get("max_tokens")
        if isinstance(default_tokens, int) and default_tokens > 0:
            return default_tokens
        return 1024

    def _build_tools(self, tools: list[ToolDefinition]) -> list[ToolUnionParam]:
        payloads: list[ToolUnionParam] = []
        for tool in tools:
            payloads.append(
                cast(
                    ToolUnionParam,
                    cast(
                        object,
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.parameters,
                        },
                    ),
                )
            )
        return payloads
