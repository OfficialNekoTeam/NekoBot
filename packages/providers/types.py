from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

ValueMap: TypeAlias = dict[str, object]


class ProviderKind:
    CHAT: str = "chat"
    EMBEDDING: str = "embedding"
    TTS: str = "tts"
    STT: str = "stt"
    RERANK: str = "rerank"


@dataclass(frozen=True)
class ModelCapability:
    name: str
    enabled: bool = True
    metadata: ValueMap = field(default_factory=dict)


@dataclass(frozen=True)
class ModelDescriptor:
    id: str
    display_name: str | None = None
    provider_name: str | None = None
    kind: str = ProviderKind.CHAT
    capabilities: tuple[ModelCapability, ...] = ()
    metadata: ValueMap = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    kind: str
    description: str = ""
    capabilities: tuple[str, ...] = ()
    models: tuple[ModelDescriptor, ...] = ()
    metadata: ValueMap = field(default_factory=dict)


@dataclass(slots=True)
class ProviderContext:
    provider_name: str
    model: str | None = None
    actor_id: str | None = None
    conversation_id: str | None = None
    platform: str | None = None
    platform_instance_uuid: str | None = None
    scope: str | None = None
    conversation_key: str | None = None
    session_key: str | None = None
    isolation_mode: str | None = None
    metadata: ValueMap = field(default_factory=dict)


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str
    name: str | None = None
    metadata: ValueMap = field(default_factory=dict)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str = ""
    parameters: ValueMap = field(default_factory=dict)
    metadata: ValueMap = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCall:
    id: str | None = None
    name: str = ""
    arguments: ValueMap = field(default_factory=dict)
    metadata: ValueMap = field(default_factory=dict)


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    metadata: ValueMap = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderErrorInfo:
    code: str
    message: str
    retryable: bool = False
    metadata: ValueMap = field(default_factory=dict)


@dataclass(slots=True)
class ProviderRequest:
    model: str | None = None
    prompt: str | None = None
    system_prompt: str | None = None
    messages: list[ChatMessage] = field(default_factory=list)
    tools: list[ToolDefinition] = field(default_factory=list)
    stream: bool = False
    options: ValueMap = field(default_factory=dict)
    context: ProviderContext | None = None


@dataclass(slots=True)
class ProviderResponse:
    content: str | None = None
    messages: list[ChatMessage] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    error: ProviderErrorInfo | None = None
    raw: object = None


@dataclass(slots=True)
class EmbeddingRequest:
    model: str | None = None
    inputs: list[str] = field(default_factory=list)
    context: ProviderContext | None = None
    options: ValueMap = field(default_factory=dict)


@dataclass(slots=True)
class EmbeddingResponse:
    vectors: list[list[float]] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    error: ProviderErrorInfo | None = None
    raw: object = None


@dataclass(slots=True)
class TTSRequest:
    model: str | None = None
    text: str = ""
    voice: str | None = None
    context: ProviderContext | None = None
    options: ValueMap = field(default_factory=dict)


@dataclass(slots=True)
class TTSResponse:
    audio_bytes: bytes = b""
    mime_type: str = "audio/mpeg"
    error: ProviderErrorInfo | None = None
    raw: object = None


@dataclass(slots=True)
class STTRequest:
    model: str | None = None
    audio_bytes: bytes = b""
    mime_type: str | None = None
    context: ProviderContext | None = None
    options: ValueMap = field(default_factory=dict)


@dataclass(slots=True)
class STTResponse:
    text: str = ""
    error: ProviderErrorInfo | None = None
    raw: object = None


@dataclass(slots=True)
class RerankRequest:
    model: str | None = None
    query: str = ""
    documents: list[str] = field(default_factory=list)
    top_k: int | None = None
    context: ProviderContext | None = None
    options: ValueMap = field(default_factory=dict)


@dataclass(slots=True)
class RerankResponse:
    rankings: list[ValueMap] = field(default_factory=list)
    error: ProviderErrorInfo | None = None
    raw: object = None
