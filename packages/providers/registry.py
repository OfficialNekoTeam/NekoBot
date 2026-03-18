from __future__ import annotations

from typing import Any

from ..contracts import RegisteredProvider
from ..runtime import RuntimeRegistry
from ..schema import SchemaRegistry
from .base import BaseProvider
from .types import ProviderInfo


class ProviderRegistry:
    def __init__(
        self,
        runtime_registry: RuntimeRegistry,
        schema_registry: SchemaRegistry,
    ) -> None:
        self.runtime_registry = runtime_registry
        self.schema_registry = schema_registry
        self._configs: dict[str, dict[str, Any]] = {}
        self._instances: dict[str, BaseProvider] = {}

    def configure(self, provider_name: str, config: dict[str, Any]) -> None:
        registered = self.get_registered(provider_name)
        if registered.spec.config_schema is not None:
            self.schema_registry.validate(registered.spec.config_schema.name, config)
        self._configs[provider_name] = dict(config)
        self._instances.pop(provider_name, None)

    def register_instance(self, provider_name: str, instance: BaseProvider) -> None:
        self._instances[provider_name] = instance

    def get_registered(self, provider_name: str) -> RegisteredProvider:
        try:
            return self.runtime_registry.providers[provider_name]
        except KeyError as exc:
            raise KeyError(f"provider not registered: {provider_name}") from exc

    def create(self, provider_name: str) -> BaseProvider:
        if provider_name in self._instances:
            return self._instances[provider_name]

        registered = self.get_registered(provider_name)
        provider_class = registered.provider_class
        instance = provider_class(
            config=self._configs.get(provider_name, {}),
            schema_registry=self.schema_registry,
        )
        self._instances[provider_name] = instance
        return instance

    def list_registered(self) -> tuple[str, ...]:
        return tuple(sorted(self.runtime_registry.providers.keys()))

    def list_infos(self) -> tuple[ProviderInfo, ...]:
        infos: list[ProviderInfo] = []
        for provider_name in self.list_registered():
            registered = self.get_registered(provider_name)
            config = self._configs.get(provider_name, {})
            info = ProviderInfo(
                name=registered.spec.name,
                kind=registered.spec.kind,
                description=registered.spec.description,
                capabilities=registered.spec.capabilities,
                metadata={**registered.spec.metadata, "configured": bool(config)},
            )
            infos.append(info)
        return tuple(infos)
