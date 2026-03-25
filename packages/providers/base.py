from __future__ import annotations

from abc import ABC, abstractmethod
from typing import cast

from ..contracts import ProviderSpec
from ..decorators.core import PROVIDER_SPEC_ATTR
from ..schema import SchemaRegistry
from .types import (
    EmbeddingRequest,
    EmbeddingResponse,
    ProviderInfo,
    ProviderRequest,
    ProviderResponse,
    RerankRequest,
    RerankResponse,
    STTRequest,
    STTResponse,
    TTSRequest,
    TTSResponse,
    ValueMap,
)


class BaseProvider(ABC):
    def __init__(
        self,
        config: ValueMap | None = None,
        schema_registry: SchemaRegistry | None = None,
    ) -> None:
        self.config: ValueMap = self._resolve_config(config or {})
        self.schema_registry: SchemaRegistry | None = schema_registry
        self._spec: ProviderSpec = self.provider_spec()
        self._is_setup: bool = False
        self._validate_config()

    @classmethod
    def provider_spec(cls) -> ProviderSpec:
        spec = cast(object, getattr(cls, PROVIDER_SPEC_ATTR, None))
        if spec is None:
            raise ValueError(
                f"provider class is missing provider metadata: {cls.__name__}"
            )
        return cast(ProviderSpec, spec)

    @property
    def spec(self) -> ProviderSpec:
        return self._spec

    @property
    def name(self) -> str:
        return self._spec.name

    @property
    def kind(self) -> str:
        return self._spec.kind

    def provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self._spec.name,
            kind=self._spec.kind,
            description=self._spec.description,
            capabilities=self._spec.capabilities,
            metadata=self._spec.metadata,
        )

    async def setup(self) -> None:
        return None

    async def teardown(self) -> None:
        return None

    async def ensure_setup(self) -> None:
        if self._is_setup:
            return
        await self.setup()
        self._is_setup = True

    async def close(self) -> None:
        if not self._is_setup:
            return
        await self.teardown()
        self._is_setup = False

    def supports_capability(self, capability: str) -> bool:
        return capability in self._spec.capabilities

    def update_config(self, config: ValueMap) -> None:
        self.config = self._resolve_config(config)
        self._validate_config()

    def _resolve_config(self, config: ValueMap) -> ValueMap:
        spec = self.provider_spec()
        default_config = cast(object, spec.metadata.get("default_config", {}))
        merged: ValueMap = {}
        if isinstance(default_config, dict):
            merged.update(cast(ValueMap, default_config))
        merged.update(config)
        return merged

    def _validate_config(self) -> None:
        if self.schema_registry is None:
            return
        if self._spec.config_schema is None:
            return
        self.schema_registry.validate(self._spec.config_schema.name, self.config)


class ChatProvider(BaseProvider, ABC):
    @abstractmethod
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError


class EmbeddingProvider(BaseProvider, ABC):
    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise NotImplementedError


class TTSProvider(BaseProvider, ABC):
    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        raise NotImplementedError


class STTProvider(BaseProvider, ABC):
    @abstractmethod
    async def transcribe(self, request: STTRequest) -> STTResponse:
        raise NotImplementedError


class RerankProvider(BaseProvider, ABC):
    @abstractmethod
    async def rerank(self, request: RerankRequest) -> RerankResponse:
        raise NotImplementedError
