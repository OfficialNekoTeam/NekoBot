from __future__ import annotations

import asyncio
import fnmatch
import json
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from .config import (
    DEFAULT_CONFIG_PATH,
    BootstrapConfig,
    load_app_config,
    save_app_config_raw,
)

if TYPE_CHECKING:
    from ..app import NekoBotFramework
    from ..conversations.context import ScopeExecution


CONFIGS_DIR = Path("data/configs")
ROUTING_PATH = Path("data/config_routing.json")


# ---------------------------------------------------------------------------
# Config entry
# ---------------------------------------------------------------------------


@dataclass
class ConfigEntry:
    id: str
    name: str
    description: str = ""
    path: str = ""


_DEFAULT_ENTRY = ConfigEntry(id="default", name="default", path=str(DEFAULT_CONFIG_PATH))


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class ConfigRouter:
    """Maps scope patterns to config UUIDs using fnmatch wildcards.

    Route key format: ``{platform_instance_uuid}:{scope}:{session_id}``

    Each segment may be ``*`` to match any value, or empty to skip matching.
    Priority follows insertion order — first match wins.
    """

    def __init__(self, routing_path: Path = ROUTING_PATH) -> None:
        self._path = routing_path
        self._table: dict[str, str] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._table = data
        except Exception as exc:
            logger.warning("ConfigRouter: failed to load routing table: {}", exc)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._table, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("ConfigRouter: failed to persist routing table: {}", exc)

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(instance_uuid: str, scope: str, session_id: str) -> str:
        return f"{instance_uuid}:{scope}:{session_id}"

    @staticmethod
    def _split_key(key: str) -> tuple[str, str, str] | None:
        parts = key.split(":", 2)
        return (parts[0], parts[1], parts[2]) if len(parts) == 3 else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, execution: ScopeExecution) -> str | None:
        """Return config_id for the execution context, or None to use default."""
        instance = execution.platform_instance_uuid or ""
        scope = execution.scope or ""
        session = execution.group_id or execution.chat_id or ""

        for pattern, config_id in self._table.items():
            parts = self._split_key(pattern)
            if parts is None:
                continue
            p_inst, p_scope, p_session = parts
            if (
                (not p_inst or fnmatch.fnmatchcase(instance, p_inst))
                and (not p_scope or fnmatch.fnmatchcase(scope, p_scope))
                and (not p_session or fnmatch.fnmatchcase(session, p_session))
            ):
                return config_id
        return None

    def add_route(
        self,
        instance_uuid: str,
        scope: str,
        session_id: str,
        config_id: str,
    ) -> None:
        self._table[self._make_key(instance_uuid, scope, session_id)] = config_id
        self._save()

    def remove_route(
        self,
        instance_uuid: str,
        scope: str,
        session_id: str,
    ) -> bool:
        key = self._make_key(instance_uuid, scope, session_id)
        if key not in self._table:
            return False
        del self._table[key]
        self._save()
        return True

    def list_routes(self) -> dict[str, str]:
        return dict(self._table)

    def replace_table(self, table: dict[str, str]) -> None:
        """Atomically replace the entire routing table."""
        for key in table:
            if self._split_key(key) is None:
                raise ValueError(
                    f"Invalid route key {key!r}. "
                    "Expected format: {{instance_uuid}}:{{scope}}:{{session_id}}"
                )
        self._table = dict(table)
        self._save()


# ---------------------------------------------------------------------------
# Config manager
# ---------------------------------------------------------------------------


class ConfigManager:
    """Multi-config CRUD with scope-based routing.

    The "default" config lives at ``data/config.json``.
    Named configs are stored as ``data/configs/<uuid>.json``.
    A :class:`ConfigRouter` maps ``instance:scope:session`` patterns to config UUIDs.

    Usage::

        cfg = manager.get_config_for(execution)   # route-aware lookup
        await manager.set_provider("openai", {...})
        entry = manager.create_config("group-a", description="Config for group A")
        manager.router.add_route("qq_bot_1", "group", "12345678", entry.id)
    """

    def __init__(
        self,
        framework: NekoBotFramework,
        default_path: Path = DEFAULT_CONFIG_PATH,
        configs_dir: Path = CONFIGS_DIR,
        routing_path: Path = ROUTING_PATH,
    ) -> None:
        self._framework = framework
        self._default_path = default_path
        self._configs_dir = configs_dir
        self._configs_dir.mkdir(parents=True, exist_ok=True)

        self._entries: dict[str, ConfigEntry] = {}
        self._configs: dict[str, BootstrapConfig] = {}
        self.router: ConfigRouter = ConfigRouter(routing_path)
        # per-config write lock — prevents concurrent read-modify-write races
        self._locks: dict[str, asyncio.Lock] = {}

        self._load_all()

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        self._entries["default"] = _DEFAULT_ENTRY
        self._configs["default"] = load_app_config(self._default_path)

        index_path = self._configs_dir / "index.json"
        if not index_path.exists():
            return
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            known = ConfigEntry.__dataclass_fields__
            for item in index:
                entry = ConfigEntry(**{k: v for k, v in item.items() if k in known})
                cfg_path = self._configs_dir / entry.path
                if cfg_path.exists():
                    self._entries[entry.id] = entry
                    self._configs[entry.id] = load_app_config(cfg_path)
                else:
                    logger.warning("ConfigManager: missing config file: {}", cfg_path)
        except Exception as exc:
            logger.warning("ConfigManager: failed to load index: {}", exc)

    def _save_index(self) -> None:
        index = [
            asdict(e) for e in self._entries.values() if e.id != "default"
        ]
        index_path = self._configs_dir / "index.json"
        try:
            index_path.write_text(
                json.dumps(index, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("ConfigManager: failed to persist config index: {}", exc)

    # ------------------------------------------------------------------
    # Hot-reload
    # ------------------------------------------------------------------

    async def _apply(self, config_id: str) -> None:
        """Reload from disk and trigger framework observers for the default config."""
        try:
            path = (
                self._default_path
                if config_id == "default"
                else self._configs_dir / self._entries[config_id].path
            )
            refreshed = load_app_config(path)
            self._configs[config_id] = refreshed
            if config_id == "default":
                await self._framework.update_framework_config(refreshed, save=False)
        except Exception as exc:
            logger.error("ConfigManager: failed to apply config {!r}: {}", config_id, exc)
            raise

    # ------------------------------------------------------------------
    # Config CRUD
    # ------------------------------------------------------------------

    def list_configs(self) -> list[ConfigEntry]:
        return list(self._entries.values())

    def get_entry(self, config_id: str) -> ConfigEntry | None:
        return self._entries.get(config_id)

    def get_config(self, config_id: str = "default") -> BootstrapConfig | None:
        return self._configs.get(config_id)

    def get_config_for(self, execution: ScopeExecution) -> BootstrapConfig:
        """Route-aware config lookup; falls back to default."""
        config_id = self.router.resolve(execution)
        if config_id and config_id in self._configs:
            return self._configs[config_id]
        return self._configs["default"]

    def create_config(
        self,
        name: str,
        description: str = "",
        base_id: str = "default",
    ) -> ConfigEntry:
        """Create a new named config cloned from base_id."""
        config_id = str(uuid.uuid4())
        filename = f"{config_id}.json"
        cfg_path = self._configs_dir / filename

        base = self._configs.get(base_id) or self._configs["default"]
        save_app_config_raw(asdict(base), cfg_path)

        entry = ConfigEntry(id=config_id, name=name, description=description, path=filename)
        self._entries[config_id] = entry
        self._configs[config_id] = load_app_config(cfg_path)
        self._save_index()
        logger.info("ConfigManager: created config {!r} ({})", name, config_id)
        return entry

    async def delete_config(self, config_id: str) -> bool:
        if config_id == "default":
            raise ValueError("Cannot delete the default config")
        entry = self._entries.pop(config_id, None)
        if entry is None:
            return False
        self._configs.pop(config_id, None)
        cfg_path = self._configs_dir / entry.path
        if cfg_path.exists():
            cfg_path.unlink()
        self._save_index()
        logger.info("ConfigManager: deleted config {!r} ({})", entry.name, config_id)
        return True

    def rename_config(
        self,
        config_id: str,
        name: str,
        description: str | None = None,
    ) -> bool:
        entry = self._entries.get(config_id)
        if entry is None:
            return False
        self._entries[config_id] = ConfigEntry(
            id=entry.id,
            name=name,
            description=description if description is not None else entry.description,
            path=entry.path,
        )
        self._save_index()
        return True

    # ------------------------------------------------------------------
    # Section patching helpers
    # ------------------------------------------------------------------

    def _get_raw(self, config_id: str) -> dict:
        path = (
            self._default_path
            if config_id == "default"
            else self._configs_dir / self._entries[config_id].path
        )
        return json.loads(path.read_text(encoding="utf-8"))

    def _config_path(self, config_id: str) -> Path:
        return (
            self._default_path
            if config_id == "default"
            else self._configs_dir / self._entries[config_id].path
        )

    async def _patch_section(self, config_id: str, section: str, value: object) -> None:
        """Lock-safe full-section overwrite."""
        if config_id not in self._entries:
            raise KeyError(f"Config {config_id!r} not found")
        lock = self._locks.setdefault(config_id, asyncio.Lock())
        async with lock:
            try:
                raw = self._get_raw(config_id)
                raw[section] = value
                save_app_config_raw(raw, self._config_path(config_id))
            except Exception as exc:
                logger.error(
                    "ConfigManager: failed to write config {!r} section {!r}: {}",
                    config_id, section, exc,
                )
                raise
            await self._apply(config_id)

    async def _mutate_section(
        self, config_id: str, section: str, fn: Callable[[object], object]
    ) -> None:
        """Lock-safe read-modify-write: fn receives current section value, returns new value."""
        if config_id not in self._entries:
            raise KeyError(f"Config {config_id!r} not found")
        lock = self._locks.setdefault(config_id, asyncio.Lock())
        async with lock:
            try:
                raw = self._get_raw(config_id)
                raw[section] = fn(raw.get(section))
                save_app_config_raw(raw, self._config_path(config_id))
            except Exception as exc:
                logger.error(
                    "ConfigManager: failed to mutate config {!r} section {!r}: {}",
                    config_id, section, exc,
                )
                raise
            await self._apply(config_id)

    # ------------------------------------------------------------------
    # Top-level section setters
    # ------------------------------------------------------------------

    async def set_framework_config(
        self, cfg: dict, config_id: str = "default"
    ) -> None:
        await self._patch_section(config_id, "framework_config", cfg)

    async def set_conversation_config(
        self, cfg: dict, config_id: str = "default"
    ) -> None:
        await self._patch_section(config_id, "conversation_config", cfg)

    async def set_moderation_config(
        self, cfg: dict, config_id: str = "default"
    ) -> None:
        await self._patch_section(config_id, "moderation_config", cfg)

    async def set_permission_config(
        self, cfg: dict, config_id: str = "default"
    ) -> None:
        await self._patch_section(config_id, "permission_config", cfg)

    # ------------------------------------------------------------------
    # Provider CRUD
    # ------------------------------------------------------------------

    def get_providers(self, config_id: str = "default") -> dict:
        cfg = self._configs.get(config_id)
        return dict(cfg.provider_configs) if cfg else {}

    async def set_provider(
        self, name: str, cfg: dict, config_id: str = "default"
    ) -> None:
        def _set(current: object) -> object:
            providers = dict(current) if isinstance(current, dict) else {}
            providers[name] = cfg
            return providers
        await self._mutate_section(config_id, "provider_configs", _set)

    async def delete_provider(self, name: str, config_id: str = "default") -> bool:
        found = False

        def _delete(current: object) -> object:
            nonlocal found
            providers = dict(current) if isinstance(current, dict) else {}
            found = name in providers
            providers.pop(name, None)
            return providers

        await self._mutate_section(config_id, "provider_configs", _delete)
        return found

    # ------------------------------------------------------------------
    # Plugin config CRUD
    # ------------------------------------------------------------------

    def get_plugin_configs(self, config_id: str = "default") -> dict:
        cfg = self._configs.get(config_id)
        return dict(cfg.plugin_configs) if cfg else {}

    async def set_plugin_config(
        self, plugin_name: str, cfg: dict, config_id: str = "default"
    ) -> None:
        def _set(current: object) -> object:
            plugin_configs = dict(current) if isinstance(current, dict) else {}
            plugin_configs[plugin_name] = cfg
            return plugin_configs
        await self._mutate_section(config_id, "plugin_configs", _set)

    # ------------------------------------------------------------------
    # Plugin binding CRUD
    # ------------------------------------------------------------------

    def get_plugin_bindings(self, config_id: str = "default") -> dict:
        cfg = self._configs.get(config_id)
        return dict(cfg.plugin_bindings) if cfg else {}

    async def set_plugin_binding(
        self, plugin_name: str, binding: dict, config_id: str = "default"
    ) -> None:
        def _set(current: object) -> object:
            bindings = dict(current) if isinstance(current, dict) else {}
            bindings[plugin_name] = binding
            return bindings
        await self._mutate_section(config_id, "plugin_bindings", _set)

    # ------------------------------------------------------------------
    # Platform CRUD
    # ------------------------------------------------------------------

    def get_platforms(self, config_id: str = "default") -> list[dict]:
        cfg = self._configs.get(config_id)
        return list(cfg.platforms) if cfg else []

    async def upsert_platform(
        self, instance_uuid: str, cfg: dict, config_id: str = "default"
    ) -> None:
        def _upsert(current: object) -> object:
            platforms: list[dict] = list(current) if isinstance(current, list) else []
            for i, p in enumerate(platforms):
                if p.get("instance_uuid") == instance_uuid:
                    platforms[i] = cfg
                    return platforms
            platforms.append(cfg)
            return platforms
        await self._mutate_section(config_id, "platforms", _upsert)

    async def delete_platform(
        self, instance_uuid: str, config_id: str = "default"
    ) -> bool:
        found = False

        def _delete(current: object) -> object:
            nonlocal found
            platforms: list[dict] = list(current) if isinstance(current, list) else []
            new_platforms = [p for p in platforms if p.get("instance_uuid") != instance_uuid]
            found = len(new_platforms) < len(platforms)
            return new_platforms

        await self._mutate_section(config_id, "platforms", _delete)
        return found
