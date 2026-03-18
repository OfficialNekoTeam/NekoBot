from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ProviderKind:
    CHAT = "chat"
    EMBEDDING = "embedding"
    TTS = "tts"
    STT = "stt"
    RERANK = "rerank"


@dataclass(frozen=True)
class ModelCapability:
    name: str
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelDescriptor:
    id: str
    display_name: str | None = None
    provider_name: str | None = None
    kind: str = ProviderKind.CHAT
    capabilities: tuple[ModelCapability, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    kind: str
    description: str = ""
    capabilities: tuple[str, ...] = ()
    models: tuple[ModelDescriptor, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


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
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderRequest:
    model: str | None = None
    prompt: str | None = None
    system_prompt: str | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    stream: bool = False
    options: dict[str, Any] = field(default_factory=dict)
    context: ProviderContext | None = None


@dataclass(slots=True)
class ProviderResponse:
    content: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    raw: Any = None


@dataclass(slots=True)
class EmbeddingRequest:
    model: str | None = None
    inputs: list[str] = field(default_factory=list)
    context: ProviderContext | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EmbeddingResponse:
    vectors: list[list[float]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    raw: Any = None


@dataclass(slots=True)
class TTSRequest:
    model: str | None = None
    text: str = ""
    voice: str | None = None
    context: ProviderContext | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TTSResponse:
    audio_bytes: bytes = b""
    mime_type: str = "audio/mpeg"
    raw: Any = None


@dataclass(slots=True)
class STTRequest:
    model: str | None = None
    audio_bytes: bytes = b""
    mime_type: str | None = None
    context: ProviderContext | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class STTResponse:
    text: str = ""
    raw: Any = None


@dataclass(slots=True)
class RerankRequest:
    model: str | None = None
    query: str = ""
    documents: list[str] = field(default_factory=list)
    top_k: int | None = None
    context: ProviderContext | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RerankResponse:
    rankings: list[dict[str, Any]] = field(default_factory=list)
    raw: Any = None
