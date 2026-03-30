from __future__ import annotations

import inspect
from collections.abc import Callable
from types import ModuleType
from typing import cast

from ..contracts import RegisteredPlugin, RegisteredProvider
from ..contracts.specs import (
    AgentToolSpec,
    CommandSpec,
    EventHandlerSpec,
    PermissionSpec,
    PluginSpec,
    ProviderSpec,
    SchemaRef,
)
from ..decorators.core import (
    AGENT_TOOL_SPEC_ATTR,
    COMMAND_SPEC_ATTR,
    CONFIG_SCHEMA_ATTR,
    EVENT_HANDLER_SPEC_ATTR,
    PERMISSION_SPEC_ATTR,
    PLUGIN_SPEC_ATTR,
    PROVIDER_SPEC_ATTR,
)
from .dispatch_registry import CommandRegistry, EventHandlerRegistry
from .registry import RuntimeRegistry


class FrameworkBinder:
    def __init__(self, registry: RuntimeRegistry) -> None:
        self.registry: RuntimeRegistry = registry
        # 延迟引入避免循环依赖，由 NekoBotFramework 在初始化后注入
        self._tool_registry: object | None = None
        self._command_registry: CommandRegistry | None = None
        self._event_handler_registry: EventHandlerRegistry | None = None

    def bind_plugin_class(self, plugin_class: type[object]) -> RegisteredPlugin:
        plugin_spec = cast(object, getattr(plugin_class, PLUGIN_SPEC_ATTR, None))
        if plugin_spec is None:
            raise ValueError(
                f"plugin class is missing plugin metadata: {plugin_class.__name__}"
            )
        plugin_spec = cast(PluginSpec, plugin_spec)

        config_schema = cast(object, getattr(plugin_class, CONFIG_SCHEMA_ATTR, None))
        permission_spec = cast(
            object, getattr(plugin_class, PERMISSION_SPEC_ATTR, None)
        )
        if config_schema is not None:
            plugin_spec = PluginSpec(
                name=plugin_spec.name,
                version=plugin_spec.version,
                description=plugin_spec.description,
                config_schema=cast(SchemaRef, config_schema),
                permissions=cast(PermissionSpec | None, permission_spec)
                or plugin_spec.permissions,
                metadata=plugin_spec.metadata,
            )
        elif permission_spec is not None:
            plugin_spec = PluginSpec(
                name=plugin_spec.name,
                version=plugin_spec.version,
                description=plugin_spec.description,
                config_schema=plugin_spec.config_schema,
                permissions=cast(PermissionSpec, permission_spec),
                metadata=plugin_spec.metadata,
            )

        commands: list[tuple[str, CommandSpec]] = []
        event_handlers: list[tuple[str, EventHandlerSpec]] = []
        agent_tools: list[tuple[str, AgentToolSpec]] = []

        members = cast(list[tuple[str, object]], inspect.getmembers(plugin_class))
        for member_name, member in members:
            command_spec = cast(object, getattr(member, COMMAND_SPEC_ATTR, None))
            if command_spec is not None:
                permission = cast(object, getattr(member, PERMISSION_SPEC_ATTR, None))
                typed_command_spec = cast(CommandSpec, command_spec)
                if permission is not None:
                    typed_command_spec = CommandSpec(
                        name=typed_command_spec.name,
                        description=typed_command_spec.description,
                        aliases=typed_command_spec.aliases,
                        argument_schema=typed_command_spec.argument_schema,
                        permissions=cast(PermissionSpec, permission),
                        metadata=typed_command_spec.metadata,
                    )
                commands.append((member_name, typed_command_spec))

            event_handler_spec = cast(
                object, getattr(member, EVENT_HANDLER_SPEC_ATTR, None)
            )
            if event_handler_spec is not None:
                permission = cast(object, getattr(member, PERMISSION_SPEC_ATTR, None))
                typed_event_spec = cast(EventHandlerSpec, event_handler_spec)
                if permission is not None:
                    typed_event_spec = EventHandlerSpec(
                        event=typed_event_spec.event,
                        description=typed_event_spec.description,
                        payload_schema=typed_event_spec.payload_schema,
                        permissions=cast(PermissionSpec, permission),
                        metadata=typed_event_spec.metadata,
                    )
                event_handlers.append((member_name, typed_event_spec))

            agent_tool_spec = cast(object, getattr(member, AGENT_TOOL_SPEC_ATTR, None))
            if agent_tool_spec is not None:
                agent_tools.append((member_name, cast(AgentToolSpec, agent_tool_spec)))

        registered = RegisteredPlugin(
            plugin_class=plugin_class,
            spec=plugin_spec,
            commands=tuple(commands),
            event_handlers=tuple(event_handlers),
            agent_tools=tuple(agent_tools),
        )
        self.registry.register_plugin(registered)

        # 注册命令 / 事件到分发注册表
        if self._command_registry is not None and registered.commands:
            self._command_registry.register(plugin_spec.name, registered.commands)
        if self._event_handler_registry is not None and registered.event_handlers:
            self._event_handler_registry.register(plugin_spec.name, registered.event_handlers)

        # 注册 agent tools 到 ToolRegistry（如果已挂载）
        if self._tool_registry is not None:
            from ..tools.registry import ToolRegistry
            tr = cast(ToolRegistry, self._tool_registry)
            for method_name, tool_spec in registered.agent_tools:
                unbound = getattr(plugin_class, method_name, None)
                if callable(unbound):
                    tr.register_tool(
                        plugin_name=plugin_spec.name,
                        tool_name=tool_spec.name,
                        description=tool_spec.description,
                        parameters_schema=dict(tool_spec.parameters_schema),
                        handler=cast(Callable[..., object], unbound),
                    )

        return registered

    def bind_provider_class(self, provider_class: type[object]) -> RegisteredProvider:
        provider_spec = cast(object, getattr(provider_class, PROVIDER_SPEC_ATTR, None))
        if provider_spec is None:
            raise ValueError(
                "provider class is missing provider metadata: "
                + provider_class.__name__
            )
        provider_spec = cast(ProviderSpec, provider_spec)

        config_schema = cast(object, getattr(provider_class, CONFIG_SCHEMA_ATTR, None))
        permission_spec = cast(
            object, getattr(provider_class, PERMISSION_SPEC_ATTR, None)
        )
        if config_schema is not None or permission_spec is not None:
            provider_spec = ProviderSpec(
                name=provider_spec.name,
                kind=provider_spec.kind,
                description=provider_spec.description,
                config_schema=cast(SchemaRef | None, config_schema)
                or provider_spec.config_schema,
                capabilities=provider_spec.capabilities,
                permissions=cast(PermissionSpec | None, permission_spec)
                or provider_spec.permissions,
                metadata=provider_spec.metadata,
            )

        registered = RegisteredProvider(
            provider_class=provider_class, spec=provider_spec
        )
        self.registry.register_provider(registered)
        return registered

    def bind_module(self, module: ModuleType) -> None:
        members = cast(list[tuple[str, object]], inspect.getmembers(module))
        for _, member in members:
            if inspect.isclass(member):
                if getattr(member, PLUGIN_SPEC_ATTR, None) is not None:
                    _ = self.bind_plugin_class(cast(type[object], member))
                if getattr(member, PROVIDER_SPEC_ATTR, None) is not None:
                    _ = self.bind_provider_class(cast(type[object], member))
