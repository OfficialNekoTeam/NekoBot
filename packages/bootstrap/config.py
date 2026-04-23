from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from loguru import logger

from ..providers.types import ValueMap
from .crypto import decrypt_secrets, encrypt_secrets
from .defaults import DEFAULT_CONFIG, INITIAL_CONFIG_TEMPLATE

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
    
    # 如果文件不存在，直接生成全新默认配置
    if not config_path.exists():
        logger.warning(f"配置文件 {config_path} 不存在，正在生成默认模板...")
        save_app_config_raw(INITIAL_CONFIG_TEMPLATE, config_path)
        return normalize_app_config(INITIAL_CONFIG_TEMPLATE)
    
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"解析配置文件失败: {e}，将使用内存默认值")
        return normalize_app_config(DEFAULT_CONFIG)

    if not isinstance(payload, dict):
        raise ValueError("app config root must be an object")
    
    # 检查配置完整性，自动补全缺失项
    if check_config_integrity(payload, DEFAULT_CONFIG):
        logger.info("检测到配置项缺失或版本更新，正在同步文件...")
        save_app_config_raw(payload, config_path)
    
    # 动态解密包含 ENC: 的机密项
    decrypted_payload = decrypt_secrets(payload)
    return normalize_app_config(cast(dict[object, object], decrypted_payload))

def check_config_integrity(current: dict[str, Any], reference: dict[str, Any]) -> bool:
    """递归检查配置完整性，返回是否有字段被补全。"""
    has_update = False
    for key, ref_val in reference.items():
        if key not in current:
            current[key] = ref_val
            has_update = True
            logger.debug(f"补全配置项: {key}")
        elif isinstance(ref_val, dict) and isinstance(current.get(key), dict):
            if check_config_integrity(current[key], ref_val):
                has_update = True
    return has_update

def save_app_config_raw(payload: dict[str, Any], path: Path) -> None:
    """直接保存原始字典到文件（包含加密逻辑）。"""
    encrypted = encrypt_secrets(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(encrypted, indent=4, ensure_ascii=False), encoding="utf-8")

def save_app_config(config: BootstrapConfig, path: str | Path | None = None) -> None:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    import dataclasses
    raw = dataclasses.asdict(config)
    save_app_config_raw(raw, config_path)


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
