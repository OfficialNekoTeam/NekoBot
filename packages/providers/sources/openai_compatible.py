from __future__ import annotations

from typing import cast, override

from openai import AsyncOpenAI

from ...decorators import provider
from ...schema import BooleanField, IntegerField, ObjectSchema, StringField
from ..types import ProviderInfo, ProviderKind
from .openai import OpenAIChatProvider

OPENAI_COMPATIBLE_PROVIDER_SCHEMA = ObjectSchema(
    fields={
        "api_key": StringField(min_length=1),
        "base_url": StringField(min_length=1),
        "default_model": StringField(required=False),
        "timeout_seconds": IntegerField(required=False, minimum=1),
        "enable_streaming": BooleanField(required=False),
    }
)


@provider(
    name="openai_compatible",
    kind=ProviderKind.CHAT,
    description="OpenAI-compatible chat provider",
    config_schema_name="provider.openai_compatible",
    capabilities=("chat", "tool_call", "stream"),
    metadata={"provider_family": "openai_compatible"},
)
class OpenAICompatibleChatProvider(OpenAIChatProvider):
    _client: AsyncOpenAI | None

    @override
    async def setup(self) -> None:
        self._client = AsyncOpenAI(
            api_key=cast(str, self.config.get("api_key")),
            base_url=cast(str, self.config.get("base_url")),
            timeout=cast(int | None, self.config.get("timeout_seconds")),
        )

    @override
    def provider_info(self) -> ProviderInfo:
        info = super().provider_info()
        return ProviderInfo(
            name=info.name,
            kind=info.kind,
            description=info.description,
            capabilities=info.capabilities,
            models=(),
            metadata={**info.metadata, "requires_base_url": True},
        )
