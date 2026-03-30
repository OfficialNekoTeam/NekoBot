from __future__ import annotations

import asyncio
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
        # In-flight setup tasks — lockless dedup for concurrent first-get calls.
        # Key is present only while ensure_setup() is awaited; removed on completion.
        self._pending: dict[str, asyncio.Task[BaseProvider]] = {}

    async def configure(self, provider_name: str, config: ValueMap) -> None:
        registered = self.get_registered(provider_name)
        if registered.spec.config_schema is not None:
            self.schema_registry.validate(registered.spec.config_schema.name, config)
        self._configs[provider_name] = dict(config)
        # Cancel any in-flight setup before replacing the instance
        pending = self._pending.pop(provider_name, None)
        if pending is not None:
            pending.cancel()
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
        # Fast path: already initialised
        if provider_name in self._instances:
            instance = self._instances[provider_name]
            await instance.ensure_setup()
            return instance

        # Dedup concurrent first-get calls without a lock.
        # All code up to the task assignment is synchronous → atomic in asyncio.
        if provider_name not in self._pending:
            registered = self.get_registered(provider_name)
            provider_class = cast(type[BaseProvider], registered.provider_class)
            new_instance = provider_class(
                config=self._configs.get(provider_name, {}),
                schema_registry=self.schema_registry,
            )

            async def _setup(
                inst: BaseProvider = new_instance,
                name: str = provider_name,
            ) -> BaseProvider:
                await inst.ensure_setup()
                self._instances[name] = inst
                self._pending.pop(name, None)
                return inst

            self._pending[provider_name] = asyncio.create_task(_setup())

        return await self._pending[provider_name]

    async def shutdown_provider(self, provider_name: str) -> None:
        pending = self._pending.pop(provider_name, None)
        if pending is not None:
            pending.cancel()
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
