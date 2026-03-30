from __future__ import annotations

import io
from typing import cast, override

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from ...decorators import provider
from ...schema import ObjectSchema, SchemaRegistry, StringField
from ..base import STTProvider, TTSProvider
from ..types import (
    ModelDescriptor,
    ProviderErrorInfo,
    ProviderInfo,
    ProviderKind,
    STTRequest,
    STTResponse,
    TTSRequest,
    TTSResponse,
    ValueMap,
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

OPENAI_TTS_SCHEMA = ObjectSchema(
    fields={
        "api_key": StringField(min_length=1),
        "default_model": StringField(required=False),
        "default_voice": StringField(required=False),
        "base_url": StringField(required=False),
    }
)

OPENAI_STT_SCHEMA = ObjectSchema(
    fields={
        "api_key": StringField(min_length=1),
        "default_model": StringField(required=False),
        "language": StringField(required=False),
        "base_url": StringField(required=False),
    }
)

# ---------------------------------------------------------------------------
# TTS — tts-1 / tts-1-hd
# ---------------------------------------------------------------------------

_TTS_MODELS = (
    ModelDescriptor(id="tts-1", display_name="OpenAI TTS-1", provider_name="openai_tts"),
    ModelDescriptor(id="tts-1-hd", display_name="OpenAI TTS-1 HD", provider_name="openai_tts"),
    ModelDescriptor(id="gpt-4o-mini-tts", display_name="GPT-4o Mini TTS", provider_name="openai_tts"),
)

_TTS_DEFAULT_VOICE = "alloy"
_TTS_DEFAULT_MODEL = "tts-1"


@provider(
    name="openai_tts",
    kind=ProviderKind.TTS,
    description="OpenAI Text-to-Speech (tts-1 / tts-1-hd / gpt-4o-mini-tts)",
    config_schema_name="provider.openai_tts",
    capabilities=("tts",),
)
class OpenAITTSProvider(TTSProvider):
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
            base_url=cast(str | None, self.config.get("base_url")) or None,
        )

    @override
    async def teardown(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    @override
    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        client = self._require_client()
        model = request.model or cast(str | None, self.config.get("default_model")) or _TTS_DEFAULT_MODEL
        voice = request.voice or cast(str | None, self.config.get("default_voice")) or _TTS_DEFAULT_VOICE
        text = request.text.strip()
        if not text:
            return TTSResponse(error=ProviderErrorInfo(code="empty_text", message="TTS input text is empty"))

        try:
            response = await client.audio.speech.create(
                model=model,
                voice=voice,  # type: ignore[arg-type]
                input=text,
                response_format="mp3",
            )
            audio_bytes = response.content
            return TTSResponse(audio_bytes=audio_bytes, mime_type="audio/mpeg")
        except RateLimitError as exc:
            return TTSResponse(error=ProviderErrorInfo(code="rate_limit", message=str(exc), retryable=True))
        except APIConnectionError as exc:
            return TTSResponse(error=ProviderErrorInfo(code="connection_error", message=str(exc), retryable=True))
        except APIStatusError as exc:
            return TTSResponse(error=ProviderErrorInfo(
                code=f"api_status_{exc.status_code}",
                message=str(exc),
                retryable=500 <= exc.status_code < 600,
            ))

    @override
    def provider_info(self) -> ProviderInfo:
        info = super().provider_info()
        return ProviderInfo(
            name=info.name,
            kind=info.kind,
            description=info.description,
            capabilities=info.capabilities,
            models=_TTS_MODELS,
        )

    def _require_client(self) -> AsyncOpenAI:
        if self._client is None:
            raise RuntimeError("OpenAI TTS provider is not initialized")
        return self._client


# ---------------------------------------------------------------------------
# STT — whisper-1
# ---------------------------------------------------------------------------

_STT_MODELS = (
    ModelDescriptor(id="whisper-1", display_name="OpenAI Whisper-1", provider_name="openai_stt"),
    ModelDescriptor(id="gpt-4o-transcribe", display_name="GPT-4o Transcribe", provider_name="openai_stt"),
    ModelDescriptor(id="gpt-4o-mini-transcribe", display_name="GPT-4o Mini Transcribe", provider_name="openai_stt"),
)

_STT_DEFAULT_MODEL = "whisper-1"


@provider(
    name="openai_stt",
    kind=ProviderKind.STT,
    description="OpenAI Speech-to-Text (Whisper)",
    config_schema_name="provider.openai_stt",
    capabilities=("stt",),
)
class OpenAISTTProvider(STTProvider):
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
            base_url=cast(str | None, self.config.get("base_url")) or None,
        )

    @override
    async def teardown(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    @override
    async def transcribe(self, request: STTRequest) -> STTResponse:
        client = self._require_client()
        model = request.model or cast(str | None, self.config.get("default_model")) or _STT_DEFAULT_MODEL
        language = cast(str | None, self.config.get("language")) or None

        if not request.audio_bytes:
            return STTResponse(error=ProviderErrorInfo(code="empty_audio", message="STT audio bytes are empty"))

        # 根据 mime_type 推断扩展名，Whisper 支持 mp3/mp4/mpeg/mpga/m4a/wav/webm/ogg/flac
        ext = _mime_to_ext(request.mime_type or "")

        try:
            audio_file = io.BytesIO(request.audio_bytes)
            audio_file.name = f"audio.{ext}"
            kwargs: dict[str, object] = {"model": model, "file": audio_file}  # type: ignore[dict-item]
            if language:
                kwargs["language"] = language
            result = await client.audio.transcriptions.create(**kwargs)  # type: ignore[arg-type]
            return STTResponse(text=result.text)
        except RateLimitError as exc:
            return STTResponse(error=ProviderErrorInfo(code="rate_limit", message=str(exc), retryable=True))
        except APIConnectionError as exc:
            return STTResponse(error=ProviderErrorInfo(code="connection_error", message=str(exc), retryable=True))
        except APIStatusError as exc:
            return STTResponse(error=ProviderErrorInfo(
                code=f"api_status_{exc.status_code}",
                message=str(exc),
                retryable=500 <= exc.status_code < 600,
            ))

    @override
    def provider_info(self) -> ProviderInfo:
        info = super().provider_info()
        return ProviderInfo(
            name=info.name,
            kind=info.kind,
            description=info.description,
            capabilities=info.capabilities,
            models=_STT_MODELS,
        )

    def _require_client(self) -> AsyncOpenAI:
        if self._client is None:
            raise RuntimeError("OpenAI STT provider is not initialized")
        return self._client


def _mime_to_ext(mime: str) -> str:
    _MAP = {
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/mp4": "mp4",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/ogg": "ogg",
        "audio/flac": "flac",
        "audio/webm": "webm",
        "audio/m4a": "m4a",
        "audio/x-m4a": "m4a",
        "audio/silk": "silk",
        "audio/amr": "amr",
    }
    return _MAP.get(mime.lower().split(";")[0].strip(), "mp3")
