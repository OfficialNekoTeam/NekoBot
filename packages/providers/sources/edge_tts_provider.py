"""edge-tts provider — 免费的微软 TTS（需要安装 edge-tts 包）。

安装：pip install edge-tts
"""
from __future__ import annotations

import io
from typing import cast, override

from ...decorators import provider
from ...schema import ObjectSchema, SchemaRegistry, StringField
from ..base import TTSProvider
from ..types import (
    ModelDescriptor,
    ProviderErrorInfo,
    ProviderInfo,
    ProviderKind,
    TTSRequest,
    TTSResponse,
    ValueMap,
)

EDGE_TTS_SCHEMA = ObjectSchema(
    fields={
        "default_voice": StringField(required=False),
    }
)

_EDGE_TTS_MODELS = (
    ModelDescriptor(id="edge-tts", display_name="Microsoft Edge TTS (free)", provider_name="edge_tts"),
)

_DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


@provider(
    name="edge_tts",
    kind=ProviderKind.TTS,
    description="免费微软 TTS（edge-tts），无需 API Key",
    config_schema_name="provider.edge_tts",
    capabilities=("tts",),
)
class EdgeTTSProvider(TTSProvider):
    def __init__(
        self,
        config: ValueMap | None = None,
        schema_registry: SchemaRegistry | None = None,
    ) -> None:
        super().__init__(config=config, schema_registry=schema_registry)

    @override
    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        try:
            import edge_tts  # type: ignore[import-untyped]
        except ImportError:
            return TTSResponse(
                error=ProviderErrorInfo(
                    code="missing_dependency",
                    message="edge-tts is not installed. Run: pip install edge-tts",
                )
            )

        text = request.text.strip()
        if not text:
            return TTSResponse(error=ProviderErrorInfo(code="empty_text", message="TTS input text is empty"))

        voice = (
            request.voice
            or cast(str | None, self.config.get("default_voice"))
            or _DEFAULT_VOICE
        )

        try:
            communicate = edge_tts.Communicate(text, voice)
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            audio_bytes = buf.getvalue()
            if not audio_bytes:
                return TTSResponse(
                    error=ProviderErrorInfo(code="empty_output", message="edge-tts returned no audio data")
                )
            return TTSResponse(audio_bytes=audio_bytes, mime_type="audio/mpeg")
        except Exception as exc:
            return TTSResponse(
                error=ProviderErrorInfo(code="edge_tts_error", message=str(exc))
            )

    @override
    def provider_info(self) -> ProviderInfo:
        info = super().provider_info()
        return ProviderInfo(
            name=info.name,
            kind=info.kind,
            description=info.description,
            capabilities=info.capabilities,
            models=_EDGE_TTS_MODELS,
        )
