from __future__ import annotations

from ..contracts import RegisteredPlugin, RegisteredProvider
from ..schema import ObjectSchema, SchemaRegistry
from .dispatch_registry import CommandRegistry, EventHandlerRegistry


class RuntimeRegistry:
    def __init__(
        self,
        schema_registry: SchemaRegistry | None = None,
        command_registry: CommandRegistry | None = None,
        event_handler_registry: EventHandlerRegistry | None = None,
    ) -> None:
        self.schema_registry: SchemaRegistry = schema_registry if schema_registry is not None else SchemaRegistry()
        self.command_registry: CommandRegistry = command_registry if command_registry is not None else CommandRegistry()
        self.event_handler_registry: EventHandlerRegistry = (
            event_handler_registry if event_handler_registry is not None else EventHandlerRegistry()
        )
        self.plugins: dict[str, RegisteredPlugin] = {}
        self.providers: dict[str, RegisteredProvider] = {}

    def register_schema(self, name: str, schema: ObjectSchema) -> None:
        self.schema_registry.register(name, schema)

    def register_plugin(self, registered_plugin: RegisteredPlugin) -> None:
        name = registered_plugin.spec.name
        if name in self.plugins:
            raise ValueError(f"plugin already registered: {name}")
        self.plugins[name] = registered_plugin
        if registered_plugin.commands:
            self.command_registry.register(name, registered_plugin.commands)
        if registered_plugin.event_handlers:
            self.event_handler_registry.register(name, registered_plugin.event_handlers)

    def unregister_plugin(self, plugin_name: str) -> bool:
        if plugin_name not in self.plugins:
            return False
        del self.plugins[plugin_name]
        self.command_registry.unregister_plugin(plugin_name)
        self.event_handler_registry.unregister_plugin(plugin_name)
        return True

    def register_provider(self, registered_provider: RegisteredProvider) -> None:
        name = registered_provider.spec.name
        if name in self.providers:
            raise ValueError(f"provider already registered: {name}")
        self.providers[name] = registered_provider
