from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from ..contracts import (
    CommandSpec,
    EventHandlerSpec,
    PermissionSpec,
    PluginSpec,
    ProviderSpec,
    SchemaRef,
)

T = TypeVar("T")

PLUGIN_SPEC_ATTR = "__nekobot_plugin_spec__"
COMMAND_SPEC_ATTR = "__nekobot_command_spec__"
EVENT_HANDLER_SPEC_ATTR = "__nekobot_event_handler_spec__"
PROVIDER_SPEC_ATTR = "__nekobot_provider_spec__"
PERMISSION_SPEC_ATTR = "__nekobot_permission_spec__"
CONFIG_SCHEMA_ATTR = "__nekobot_config_schema__"


def plugin(
    *,
    name: str,
    version: str = "0.1.0",
    description: str = "",
    metadata: dict[str, Any] | None = None,
) -> Callable[[type[T]], type[T]]:
    def decorator(target: type[T]) -> type[T]:
        setattr(
            target,
            PLUGIN_SPEC_ATTR,
            PluginSpec(
                name=name,
                version=version,
                description=description,
                metadata=metadata or {},
            ),
        )
        return target

    return decorator


def command(
    *,
    name: str | None = None,
    description: str = "",
    aliases: tuple[str, ...] = (),
    argument_schema: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(target: Callable[..., Any]) -> Callable[..., Any]:
        setattr(
            target,
            COMMAND_SPEC_ATTR,
            CommandSpec(
                name=name or target.__name__,
                description=description,
                aliases=aliases,
                argument_schema=SchemaRef(argument_schema) if argument_schema else None,
                metadata=metadata or {},
            ),
        )
        return target

    return decorator


def event_handler(
    *,
    event: str,
    description: str = "",
    payload_schema: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(target: Callable[..., Any]) -> Callable[..., Any]:
        setattr(
            target,
            EVENT_HANDLER_SPEC_ATTR,
            EventHandlerSpec(
                event=event,
                description=description,
                payload_schema=SchemaRef(payload_schema) if payload_schema else None,
                metadata=metadata or {},
            ),
        )
        return target

    return decorator


def provider(
    *,
    name: str,
    kind: str,
    description: str = "",
    config_schema_name: str | None = None,
    capabilities: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
) -> Callable[[type[T]], type[T]]:
    def decorator(target: type[T]) -> type[T]:
        setattr(
            target,
            PROVIDER_SPEC_ATTR,
            ProviderSpec(
                name=name,
                kind=kind,
                description=description,
                config_schema=SchemaRef(config_schema_name)
                if config_schema_name
                else None,
                capabilities=capabilities,
                metadata=metadata or {},
            ),
        )
        return target

    return decorator


def requires_permissions(
    *permissions: str, require_all: bool = True
) -> Callable[[T], T]:
    def decorator(target: T) -> T:
        setattr(
            target,
            PERMISSION_SPEC_ATTR,
            PermissionSpec(permissions=tuple(permissions), require_all=require_all),
        )
        return target

    return decorator


def config_schema(schema_name: str) -> Callable[[T], T]:
    def decorator(target: T) -> T:
        setattr(target, CONFIG_SCHEMA_ATTR, SchemaRef(schema_name))
        return target

    return decorator
