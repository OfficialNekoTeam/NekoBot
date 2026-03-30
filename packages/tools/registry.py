from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from loguru import logger

from ..providers.types import ToolCall, ToolDefinition


@dataclass
class ToolEntry:
    """单个工具的运行时记录。"""
    name: str
    description: str
    parameters_schema: dict[str, Any]
    # handler 签名：(plugin_instance_or_none, **kwargs) -> object
    # plugin backend 时第一个位置参数是插件实例；MCP backend 时为 None
    handler: Callable[..., Awaitable[object]]
    plugin_name: str          # 来源插件名，卸载时批量清理
    backend: str = "plugin"   # "plugin" 或 "mcp:<server_name>"


@runtime_checkable
class ToolBackend(Protocol):
    """外部工具后端（MCP server 等）实现的协议。"""

    async def list_tools(self) -> list[ToolEntry]: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> object: ...


class ToolRegistry:
    """运行时工具注册表。

    管理插件注册的 Agent Tool 以及外部 MCP server 工具，
    对 LLMHandler 提供统一的工具列表和调用接口。
    """

    def __init__(self) -> None:
        # plugin_name -> list[ToolEntry]
        self._plugin_tools: dict[str, list[ToolEntry]] = {}
        # server_name -> ToolBackend
        self._backends: dict[str, ToolBackend] = {}

    # ------------------------------------------------------------------
    # Plugin tool 注册（由 FrameworkBinder 调用）
    # ------------------------------------------------------------------

    def register_tool(
        self,
        *,
        plugin_name: str,
        tool_name: str,
        description: str,
        parameters_schema: dict[str, Any],
        handler: Callable[..., Awaitable[object]],
    ) -> None:
        entry = ToolEntry(
            name=tool_name,
            description=description,
            parameters_schema=parameters_schema,
            handler=handler,
            plugin_name=plugin_name,
            backend="plugin",
        )
        self._plugin_tools.setdefault(plugin_name, []).append(entry)
        logger.debug("ToolRegistry: registered tool {!r} from plugin {!r}", tool_name, plugin_name)

    def unregister_plugin(self, plugin_name: str) -> int:
        """注销某插件的所有工具，返回注销数量。"""
        removed = self._plugin_tools.pop(plugin_name, [])
        if removed:
            logger.debug("ToolRegistry: unregistered {} tool(s) from plugin {!r}", len(removed), plugin_name)
        return len(removed)

    # ------------------------------------------------------------------
    # MCP / 外部 backend
    # ------------------------------------------------------------------

    def add_backend(self, name: str, backend: ToolBackend) -> None:
        self._backends[name] = backend
        logger.info("ToolRegistry: added tool backend {!r}", name)

    def remove_backend(self, name: str) -> None:
        self._backends.pop(name, None)
        logger.info("ToolRegistry: removed tool backend {!r}", name)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """返回所有可用工具的 ToolDefinition 列表（供 provider 注入）。"""
        defs: list[ToolDefinition] = []
        seen: set[str] = set()

        for entries in self._plugin_tools.values():
            for e in entries:
                if e.name not in seen:
                    defs.append(ToolDefinition(
                        name=e.name,
                        description=e.description,
                        parameters=e.parameters_schema,
                    ))
                    seen.add(e.name)

        # MCP backend 工具在调用时才拉取，避免 get_tool_definitions 变成 async
        # 通过 _backend_tool_cache 缓存（由 sync_backend 方法填充）
        for entry in self._backend_cache.values():
            if entry.name not in seen:
                defs.append(ToolDefinition(
                    name=entry.name,
                    description=entry.description,
                    parameters=entry.parameters_schema,
                ))
                seen.add(entry.name)

        return defs

    async def sync_backends(self) -> None:
        """拉取所有外部 backend 的最新工具列表，更新缓存。"""
        new_cache: dict[str, ToolEntry] = {}
        for backend_name, backend in self._backends.items():
            try:
                entries = await backend.list_tools()
                for e in entries:
                    new_cache[e.name] = e
                logger.debug("ToolRegistry: synced {} tool(s) from backend {!r}", len(entries), backend_name)
            except Exception as exc:
                logger.warning("ToolRegistry: failed to sync backend {!r}: {}", backend_name, exc)
        self._backend_cache = new_cache

    # ------------------------------------------------------------------
    # 工具调用分发
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        tool_call: ToolCall,
        plugin_instance: object | None = None,
    ) -> object:
        """执行工具调用，返回结果（字符串化供 LLM 使用）。"""
        name = tool_call.name
        args = dict(tool_call.arguments)

        # 优先查 plugin tools
        for entries in self._plugin_tools.values():
            for e in entries:
                if e.name == name:
                    try:
                        if plugin_instance is not None:
                            result = await e.handler(plugin_instance, **args)
                        else:
                            result = await e.handler(**args)
                        return _serialize_result(result)
                    except Exception as exc:
                        logger.error("ToolRegistry: tool {!r} raised: {}", name, exc)
                        return json.dumps({"error": str(exc)})

        # 查 backend cache
        cached = self._backend_cache.get(name)
        if cached is not None:
            backend_name = cached.backend.removeprefix("mcp:")
            backend = self._backends.get(backend_name)
            if backend is not None:
                try:
                    result = await backend.call_tool(name, args)
                    return _serialize_result(result)
                except Exception as exc:
                    logger.error("ToolRegistry: backend tool {!r} raised: {}", name, exc)
                    return json.dumps({"error": str(exc)})

        logger.warning("ToolRegistry: unknown tool {!r}", name)
        return json.dumps({"error": f"unknown tool: {name}"})

    def __len__(self) -> int:
        total = sum(len(v) for v in self._plugin_tools.values())
        return total + len(self._backend_cache)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    @property
    def _backend_cache(self) -> dict[str, ToolEntry]:
        if not hasattr(self, "_backend_cache_dict"):
            self._backend_cache_dict: dict[str, ToolEntry] = {}
        return self._backend_cache_dict

    @_backend_cache.setter
    def _backend_cache(self, value: dict[str, ToolEntry]) -> None:
        self._backend_cache_dict = value


def _serialize_result(result: object) -> str:
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(result)
