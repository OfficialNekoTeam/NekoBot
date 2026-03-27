from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from ..providers.types import ValueMap

ScopedValueMap = dict[str, ValueMap]


@dataclass(frozen=True)
class BootstrapConfig:
    framework_config: ValueMap = field(default_factory=dict)
    plugin_configs: ScopedValueMap = field(default_factory=dict)
    provider_configs: ScopedValueMap = field(default_factory=dict)
    permission_config: ValueMap = field(default_factory=dict)
    moderation_config: ValueMap = field(default_factory=dict)
    conversation_config: ValueMap = field(default_factory=dict)
    plugin_bindings: ScopedValueMap = field(default_factory=dict)
    platforms: list[ValueMap] = field(default_factory=list)


DEFAULT_CONFIG_PATH = Path("data/config.json")


def load_app_config(path: str | Path | None = None) -> BootstrapConfig:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return BootstrapConfig()
    payload = cast(object, json.loads(config_path.read_text(encoding="utf-8")))
    if not isinstance(payload, dict):
        raise ValueError("app config root must be an object")
    return normalize_app_config(cast(dict[object, object], payload))


def normalize_app_config(raw: dict[object, object]) -> BootstrapConfig:
    return BootstrapConfig(
        framework_config=_value_map(raw.get("framework_config")),
        plugin_configs=_scoped_value_map(raw.get("plugin_configs")),
        provider_configs=_scoped_value_map(raw.get("provider_configs")),
        permission_config=_value_map(raw.get("permission_config")),
        moderation_config=_value_map(raw.get("moderation_config")),
        conversation_config=_value_map(raw.get("conversation_config")),
        plugin_bindings=_scoped_value_map(raw.get("plugin_bindings")),
        platforms=_platform_list(raw.get("platforms")),
    )


def _platform_list(value: object) -> list[ValueMap]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    return [
        _value_map(cast(dict[object, object], item))
        for item in items
        if isinstance(item, dict)
    ]


def _scoped_value_map(value: object) -> ScopedValueMap:
    if not isinstance(value, dict):
        return {}
    mapping = cast(dict[object, object], value)
    return {
        key: _value_map(cast(dict[object, object], item))
        for key, item in mapping.items()
        if isinstance(key, str) and isinstance(item, dict)
    }


def _value_map(value: object) -> ValueMap:
    if not isinstance(value, dict):
        return {}
    mapping = cast(dict[object, object], value)
    return {str(key): item for key, item in mapping.items() if isinstance(key, str)}
