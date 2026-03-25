from __future__ import annotations

from typing import cast

from ..contracts import RegisteredProvider
from ..runtime import RuntimeRegistry
from ..schema import SchemaRegistry
from .base import BaseProvider
from .types import ProviderInfo, ValueMap


class ProviderRegistry:
    def __init__(
        self,
        runtime_registry: RuntimeRegistry,
        schema_registry: SchemaRegistry,
    ) -> None:
        self.runtime_registry: RuntimeRegistry = runtime_registry
        self.schema_registry: SchemaRegistry = schema_registry
        self._configs: dict[str, ValueMap] = {}
        self._instances: dict[str, BaseProvider] = {}

    async def configure(self, provider_name: str, config: ValueMap) -> None:
        registered = self.get_registered(provider_name)
        if registered.spec.config_schema is not None:
            self.schema_registry.validate(registered.spec.config_schema.name, config)
        self._configs[provider_name] = dict(config)
        instance = self._instances.pop(provider_name, None)
        if instance is not None:
            await instance.close()

    def register_instance(self, provider_name: str, instance: BaseProvider) -> None:
        self._instances[provider_name] = instance

    def get_registered(self, provider_name: str) -> RegisteredProvider:
        try:
            return self.runtime_registry.providers[provider_name]
        except KeyError as exc:
            raise KeyError(f"provider not registered: {provider_name}") from exc

    async def get(self, provider_name: str) -> BaseProvider:
        if provider_name in self._instances:
            instance = self._instances[provider_name]
            await instance.ensure_setup()
            return instance

        registered = self.get_registered(provider_name)
        provider_class = cast(type[BaseProvider], registered.provider_class)
        instance = provider_class(
            config=self._configs.get(provider_name, {}),
            schema_registry=self.schema_registry,
        )
        await instance.ensure_setup()
        self._instances[provider_name] = instance
        return instance

    async def shutdown_provider(self, provider_name: str) -> None:
        instance = self._instances.pop(provider_name, None)
        if instance is None:
            return
        await instance.close()

    async def shutdown_all(self) -> None:
        for provider_name in tuple(self._instances.keys()):
            await self.shutdown_provider(provider_name)

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
