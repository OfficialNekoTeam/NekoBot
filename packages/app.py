from __future__ import annotations

from types import ModuleType

from .providers import ProviderRegistry
from .runtime import FrameworkBinder, RuntimeRegistry
from .schema import ObjectSchema, SchemaRegistry


class NekoBotFramework:
    def __init__(self) -> None:
        self.schema_registry = SchemaRegistry()
        self.runtime_registry = RuntimeRegistry(schema_registry=self.schema_registry)
        self.binder = FrameworkBinder(self.runtime_registry)
        self.provider_registry = ProviderRegistry(
            runtime_registry=self.runtime_registry,
            schema_registry=self.schema_registry,
        )

    def register_schema(self, name: str, schema: ObjectSchema) -> None:
        self.runtime_registry.register_schema(name, schema)

    def bind_module(self, module: ModuleType) -> None:
        self.binder.bind_module(module)


def create_framework() -> NekoBotFramework:
    return NekoBotFramework()
