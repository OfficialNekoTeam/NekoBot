from __future__ import annotations

import inspect
import types
import typing
from collections.abc import Callable
from typing import Any, TypeVar, get_args, get_origin, get_type_hints

from ..contracts import (
    AgentToolSpec,
    CommandSpec,
    EventHandlerSpec,
    PermissionSpec,
    PlatformSpec,
    PluginSpec,
    ProviderSpec,
    SchemaRef,
)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Signature → JSON Schema inference
# ---------------------------------------------------------------------------

_PY_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    bytes: "string",  # treat as base64 string at the schema level
}


def _is_optional(annotation: object) -> tuple[bool, object]:
    """Return (is_optional, inner_type).

    Handles ``X | None`` (Python 3.10+ union) and ``Optional[X]``
    (which is ``Union[X, None]``).
    """
    origin = get_origin(annotation)
    # Union / Optional
    if origin is typing.Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return True, args[0]
        return True, annotation  # multi-union, leave as-is
    # X | None  (types.UnionType, Python 3.10+)
    if isinstance(annotation, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return True, args[0]
        return True, annotation
    return False, annotation


def _annotation_to_json_schema(annotation: object) -> dict[str, Any]:
    """Convert a single Python type annotation to a JSON Schema fragment."""
    if annotation is inspect.Parameter.empty or annotation is None:
        return {}

    optional, inner = _is_optional(annotation)
    if optional:
        annotation = inner

    origin = get_origin(annotation)

    # list[X]
    if origin is list:
        item_args = get_args(annotation)
        schema: dict[str, Any] = {"type": "array"}
        if item_args:
            schema["items"] = _annotation_to_json_schema(item_args[0])
        return schema

    # dict[K, V]
    if origin is dict:
        return {"type": "object"}

    # Plain types
    if isinstance(annotation, type):
        json_type = _PY_TO_JSON.get(annotation)
        if json_type:
            return {"type": json_type}

    return {}


def _schema_from_fn(fn: Callable[..., Any]) -> dict[str, Any]:
    """Build a JSON Schema ``object`` from a function's type annotations.

    ``self`` / ``cls`` are skipped. Parameters without annotations produce
    an unconstrained property (``{}``). Parameters with default values are
    omitted from ``required``.
    """
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}

    sig = inspect.signature(fn)
    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        annotation = hints.get(param_name, inspect.Parameter.empty)
        optional_flag, _ = _is_optional(annotation)
        prop_schema = _annotation_to_json_schema(annotation)

        # Use the docstring of the param if available via Annotated metadata
        # (plain annotations have no per-param doc, so we leave description empty)
        properties[param_name] = prop_schema

        has_default = param.default is not inspect.Parameter.empty
        if not has_default and not optional_flag:
            required.append(param_name)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


PLUGIN_SPEC_ATTR = "__nekobot_plugin_spec__"
COMMAND_SPEC_ATTR = "__nekobot_command_spec__"
EVENT_HANDLER_SPEC_ATTR = "__nekobot_event_handler_spec__"
PROVIDER_SPEC_ATTR = "__nekobot_provider_spec__"
PERMISSION_SPEC_ATTR = "__nekobot_permission_spec__"
CONFIG_SCHEMA_ATTR = "__nekobot_config_schema__"
AGENT_TOOL_SPEC_ATTR = "__nekobot_agent_tool_spec__"
PLATFORM_SPEC_ATTR = "__nekobot_platform_spec__"


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
    priority: int = 0,
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
                priority=priority,
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


def agent_tool(
    *,
    name: str | None = None,
    description: str = "",
    metadata: dict[str, Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """将插件方法声明为 Agent 可调用工具（function calling）。

    参数 schema 从函数类型注解自动推导，无需手写 JSON Schema dict。

    用法::

        @agent_tool(description="搜索互联网获取最新信息")
        async def search_web(self, query: str, max_results: int = 5) -> str:
            ...

    工具方法第一个参数为 ``self``（BasePlugin 实例），其余参数由 LLM 传入。
    返回值会作为工具结果回传给 LLM。
    """
    def decorator(target: Callable[..., Any]) -> Callable[..., Any]:
        setattr(
            target,
            AGENT_TOOL_SPEC_ATTR,
            AgentToolSpec(
                name=name or target.__name__,
                description=description,
                parameters_schema=_schema_from_fn(target),
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


def platform(
    *,
    platform_type: str,
    description: str = "",
    metadata: dict[str, Any] | None = None,
) -> Callable[[type[T]], type[T]]:
    """将一个适配器类注册为可用的平台类型。

    被装饰的类必须实现 ``async start()`` 和 ``async stop()``，
    构造函数签名为 ``__init__(self, config, *, framework, configuration, **kwargs)``。

    注册后，用户可在 ``config.json`` 的 ``platforms`` 列表中使用该 platform_type 名称::

        @platform(platform_type="my_platform", description="自定义平台适配器")
        class MyPlatformAdapter:
            def __init__(self, config, *, framework, configuration, **kwargs): ...
            async def start(self) -> None: ...
            async def stop(self) -> None: ...
    """
    def decorator(target: type[T]) -> type[T]:
        setattr(
            target,
            PLATFORM_SPEC_ATTR,
            PlatformSpec(
                platform_type=platform_type,
                description=description,
                metadata=metadata or {},
            ),
        )
        return target

    return decorator
