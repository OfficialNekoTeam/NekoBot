from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SchemaRef:
    name: str


@dataclass(frozen=True)
class PermissionSpec:
    permissions: tuple[str, ...]
    require_all: bool = True


@dataclass(frozen=True)
class ConfigSchemaSpec:
    schema: SchemaRef


@dataclass(frozen=True)
class PluginSpec:
    name: str
    version: str = "0.1.0"
    description: str = ""
    config_schema: SchemaRef | None = None
    permissions: PermissionSpec | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommandSpec:
    name: str
    description: str = ""
    aliases: tuple[str, ...] = ()
    argument_schema: SchemaRef | None = None
    permissions: PermissionSpec | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventHandlerSpec:
    event: str
    description: str = ""
    payload_schema: SchemaRef | None = None
    permissions: PermissionSpec | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    kind: str
    description: str = ""
    config_schema: SchemaRef | None = None
    capabilities: tuple[str, ...] = ()
    permissions: PermissionSpec | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentToolSpec:
    name: str
    description: str = ""
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    permissions: PermissionSpec | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlatformSpec:
    platform_type: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RegisteredPlugin:
    plugin_class: type[Any]
    spec: PluginSpec
    commands: tuple[tuple[str, CommandSpec], ...] = ()
    event_handlers: tuple[tuple[str, EventHandlerSpec], ...] = ()
    agent_tools: tuple[tuple[str, AgentToolSpec], ...] = ()


@dataclass(frozen=True)
class RegisteredProvider:
    provider_class: type[Any]
    spec: ProviderSpec
