from __future__ import annotations

from ..contracts import RegisteredPlugin, RegisteredProvider
from ..schema import ObjectSchema, SchemaRegistry


class RuntimeRegistry:
    def __init__(self, schema_registry: SchemaRegistry | None = None) -> None:
        self.schema_registry: SchemaRegistry = schema_registry or SchemaRegistry()
        self.plugins: dict[str, RegisteredPlugin] = {}
        self.providers: dict[str, RegisteredProvider] = {}

    def register_schema(self, name: str, schema: ObjectSchema) -> None:
        self.schema_registry.register(name, schema)

    def register_plugin(self, registered_plugin: RegisteredPlugin) -> None:
        name = registered_plugin.spec.name
        if name in self.plugins:
            raise ValueError(f"plugin already registered: {name}")
        self.plugins[name] = registered_plugin

    def unregister_plugin(self, plugin_name: str) -> bool:
        if plugin_name not in self.plugins:
            return False
        del self.plugins[plugin_name]
        return True

    def register_provider(self, registered_provider: RegisteredProvider) -> None:
        name = registered_provider.spec.name
        if name in self.providers:
            raise ValueError(f"provider already registered: {name}")
        self.providers[name] = registered_provider
