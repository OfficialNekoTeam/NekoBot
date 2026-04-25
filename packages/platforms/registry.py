from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Protocol, TypeAlias, cast

PlatformConfigMap: TypeAlias = dict[str, object]


class PlatformFactory(Protocol):
    def __call__(self, config: PlatformConfigMap, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class PlatformRegistryEntry:
    platform_type: str
    # module_path + factory_name: 内置平台的惰性加载方式
    module_path: str | None = None
    factory_name: str | None = None
    # adapter_class: @platform 装饰器注册的直接类
    adapter_class: type | None = None


class PlatformRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, PlatformRegistryEntry] = {}

    def register(
        self,
        *,
        platform_type: str,
        module_path: str,
        factory_name: str,
    ) -> None:
        if platform_type in self._entries:
            raise ValueError(f"platform type already registered: {platform_type}")
        self._entries[platform_type] = PlatformRegistryEntry(
            platform_type=platform_type,
            module_path=module_path,
            factory_name=factory_name,
        )

    def register_class(self, platform_type: str, adapter_class: type) -> None:
        """直接注册适配器类（用于 @platform 装饰器）。"""
        if platform_type in self._entries:
            raise ValueError(f"platform type already registered: {platform_type}")
        self._entries[platform_type] = PlatformRegistryEntry(
            platform_type=platform_type,
            adapter_class=adapter_class,
        )

    def get_entry(self, platform_type: str) -> PlatformRegistryEntry:
        try:
            return self._entries[platform_type]
        except KeyError as exc:
            raise KeyError(f"platform type not registered: {platform_type}") from exc

    def create(
        self,
        platform_type: str,
        config: PlatformConfigMap,
        **kwargs: object,
    ) -> object:
        entry = self.get_entry(platform_type)
        if entry.adapter_class is not None:
            return entry.adapter_class(config, **kwargs)
        module = import_module(entry.module_path or "")
        factory = cast(PlatformFactory, getattr(module, entry.factory_name or ""))
        return factory(config, **kwargs)

    def list_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries.keys()))
