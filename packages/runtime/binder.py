from __future__ import annotations

import inspect
from types import ModuleType
from typing import Any

from ..contracts import RegisteredPlugin, RegisteredProvider
from ..decorators.core import (
    COMMAND_SPEC_ATTR,
    CONFIG_SCHEMA_ATTR,
    EVENT_HANDLER_SPEC_ATTR,
    PERMISSION_SPEC_ATTR,
    PLUGIN_SPEC_ATTR,
    PROVIDER_SPEC_ATTR,
)
from .registry import RuntimeRegistry


class FrameworkBinder:
    def __init__(self, registry: RuntimeRegistry) -> None:
        self.registry = registry

    def bind_plugin_class(self, plugin_class: type[Any]) -> RegisteredPlugin:
        plugin_spec = getattr(plugin_class, PLUGIN_SPEC_ATTR, None)
        if plugin_spec is None:
            raise ValueError(
                f"plugin class is missing plugin metadata: {plugin_class.__name__}"
            )

        config_schema = getattr(plugin_class, CONFIG_SCHEMA_ATTR, None)
        permission_spec = getattr(plugin_class, PERMISSION_SPEC_ATTR, None)
        if config_schema is not None:
            plugin_spec = type(plugin_spec)(
                name=plugin_spec.name,
                version=plugin_spec.version,
                description=plugin_spec.description,
                config_schema=config_schema,
                permissions=permission_spec or plugin_spec.permissions,
                metadata=plugin_spec.metadata,
            )
        elif permission_spec is not None:
            plugin_spec = type(plugin_spec)(
                name=plugin_spec.name,
                version=plugin_spec.version,
                description=plugin_spec.description,
                config_schema=plugin_spec.config_schema,
                permissions=permission_spec,
                metadata=plugin_spec.metadata,
            )

        commands: list[tuple[str, Any]] = []
        event_handlers: list[tuple[str, Any]] = []

        for member_name, member in inspect.getmembers(plugin_class):
            command_spec = getattr(member, COMMAND_SPEC_ATTR, None)
            if command_spec is not None:
                permission = getattr(member, PERMISSION_SPEC_ATTR, None)
                if permission is not None:
                    command_spec = type(command_spec)(
                        name=command_spec.name,
                        description=command_spec.description,
                        aliases=command_spec.aliases,
                        argument_schema=command_spec.argument_schema,
                        permissions=permission,
                        metadata=command_spec.metadata,
                    )
                commands.append((member_name, command_spec))

            event_handler_spec = getattr(member, EVENT_HANDLER_SPEC_ATTR, None)
            if event_handler_spec is not None:
                permission = getattr(member, PERMISSION_SPEC_ATTR, None)
                if permission is not None:
                    event_handler_spec = type(event_handler_spec)(
                        event=event_handler_spec.event,
                        description=event_handler_spec.description,
                        payload_schema=event_handler_spec.payload_schema,
                        permissions=permission,
                        metadata=event_handler_spec.metadata,
                    )
                event_handlers.append((member_name, event_handler_spec))

        registered = RegisteredPlugin(
            plugin_class=plugin_class,
            spec=plugin_spec,
            commands=tuple(commands),
            event_handlers=tuple(event_handlers),
        )
        self.registry.register_plugin(registered)
        return registered

    def bind_provider_class(self, provider_class: type[Any]) -> RegisteredProvider:
        provider_spec = getattr(provider_class, PROVIDER_SPEC_ATTR, None)
        if provider_spec is None:
            raise ValueError(
                "provider class is missing provider metadata: "
                f"{provider_class.__name__}"
            )

        config_schema = getattr(provider_class, CONFIG_SCHEMA_ATTR, None)
        permission_spec = getattr(provider_class, PERMISSION_SPEC_ATTR, None)
        if config_schema is not None or permission_spec is not None:
            provider_spec = type(provider_spec)(
                name=provider_spec.name,
                kind=provider_spec.kind,
                description=provider_spec.description,
                config_schema=config_schema or provider_spec.config_schema,
                capabilities=provider_spec.capabilities,
                permissions=permission_spec or provider_spec.permissions,
                metadata=provider_spec.metadata,
            )

        registered = RegisteredProvider(
            provider_class=provider_class, spec=provider_spec
        )
        self.registry.register_provider(registered)
        return registered

    def bind_module(self, module: ModuleType) -> None:
        for _, member in inspect.getmembers(module):
            if inspect.isclass(member):
                if getattr(member, PLUGIN_SPEC_ATTR, None) is not None:
                    self.bind_plugin_class(member)
                if getattr(member, PROVIDER_SPEC_ATTR, None) is not None:
                    self.bind_provider_class(member)
