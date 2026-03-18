from __future__ import annotations

from typing import Any

from ..contracts import PluginSpec
from ..decorators.core import PLUGIN_SPEC_ATTR
from ..permissions import PermissionDecision
from ..runtime.context import PluginContext
from ..schema import SchemaRegistry


class BasePlugin:
    def __init__(
        self,
        context: PluginContext,
        schema_registry: SchemaRegistry | None = None,
    ) -> None:
        self.context = context
        self.schema_registry = schema_registry
        self._spec = self._resolve_spec()
        self._validate_config()

    @classmethod
    def plugin_spec(cls) -> PluginSpec:
        spec = getattr(cls, PLUGIN_SPEC_ATTR, None)
        if spec is None:
            raise ValueError(f"plugin class is missing plugin metadata: {cls.__name__}")
        return spec

    @property
    def spec(self) -> PluginSpec:
        return self._spec

    @property
    def name(self) -> str:
        return self._spec.name

    @property
    def version(self) -> str:
        return self._spec.version

    async def setup(self) -> None:
        return None

    async def teardown(self) -> None:
        return None

    async def on_event(self, event_name: str, payload: dict[str, Any]) -> None:
        return None

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.context.get_config(key, default)

    async def reply(self, message: str) -> None:
        await self.context.reply(message)

    async def request_provider(self, provider_name: str, **kwargs: Any) -> Any:
        return await self.context.request_provider(provider_name, **kwargs)

    async def schedule_task(self, task_name: str, payload: dict[str, Any]) -> Any:
        return await self.context.schedule_task(task_name, payload)

    def check_permissions(self, *permissions: str, require_all: bool = True) -> bool:
        return self.context.check_permissions(*permissions, require_all=require_all)

    def permission_decision(
        self, *permissions: str, require_all: bool = True
    ) -> PermissionDecision:
        return self.context.permission_decision(*permissions, require_all=require_all)

    def _resolve_spec(self) -> PluginSpec:
        return self.plugin_spec()

    def _validate_config(self) -> None:
        if self.schema_registry is None:
            return

        if self._spec.config_schema is None:
            return

        self.schema_registry.validate(
            self._spec.config_schema.name, self.context.config
        )
