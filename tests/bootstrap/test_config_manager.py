from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from packages.app import NekoBotFramework
from packages.bootstrap.manager import ConfigManager, ConfigRouter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dirs(tmp_path: Path):
    default_cfg = tmp_path / "config.json"
    default_cfg.write_text(
        json.dumps(
            {
                "framework_config": {"web_port": 6285},
                "provider_configs": {},
                "plugin_configs": {},
                "plugin_bindings": {},
                "platforms": [],
                "conversation_config": {},
                "permission_config": {},
                "moderation_config": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    configs_dir = tmp_path / "configs"
    routing_path = tmp_path / "routing.json"
    return default_cfg, configs_dir, routing_path


@pytest.fixture
def framework():
    return NekoBotFramework()


@pytest.fixture
def manager(framework, tmp_dirs):
    default_cfg, configs_dir, routing_path = tmp_dirs
    return ConfigManager(
        framework,
        default_path=default_cfg,
        configs_dir=configs_dir,
        routing_path=routing_path,
    )


# ---------------------------------------------------------------------------
# ConfigRouter
# ---------------------------------------------------------------------------


def test_router_add_and_resolve(tmp_path):
    router = ConfigRouter(tmp_path / "routing.json")
    router.add_route("qq_bot_1", "group", "12345", "uuid-abc")

    @dataclass
    class FakeExecution:
        platform_instance_uuid: str | None = "qq_bot_1"
        scope: str = "group"
        group_id: str | None = "12345"
        chat_id: str | None = None

    assert router.resolve(FakeExecution()) == "uuid-abc"


def test_router_wildcard_scope(tmp_path):
    router = ConfigRouter(tmp_path / "routing.json")
    router.add_route("*", "group", "*", "uuid-global")

    @dataclass
    class FakeExecution:
        platform_instance_uuid: str | None = "any_instance"
        scope: str = "group"
        group_id: str | None = "any_group"
        chat_id: str | None = None

    assert router.resolve(FakeExecution()) == "uuid-global"


def test_router_no_match_returns_none(tmp_path):
    router = ConfigRouter(tmp_path / "routing.json")
    router.add_route("qq_bot_1", "group", "12345", "uuid-abc")

    @dataclass
    class FakeExecution:
        platform_instance_uuid: str | None = "other_bot"
        scope: str = "private"
        group_id: str | None = None
        chat_id: str | None = "99999"

    assert router.resolve(FakeExecution()) is None


def test_router_remove_route(tmp_path):
    router = ConfigRouter(tmp_path / "routing.json")
    router.add_route("bot", "group", "111", "cfg-1")
    assert router.remove_route("bot", "group", "111") is True
    assert router.list_routes() == {}


def test_router_replace_table_validates_keys(tmp_path):
    router = ConfigRouter(tmp_path / "routing.json")
    with pytest.raises(ValueError):
        router.replace_table({"bad_key_no_colons": "cfg-1"})


def test_router_persists_to_disk(tmp_path):
    path = tmp_path / "routing.json"
    router = ConfigRouter(path)
    router.add_route("bot", "group", "111", "cfg-1")

    router2 = ConfigRouter(path)
    assert router2.list_routes() == {"bot:group:111": "cfg-1"}


# ---------------------------------------------------------------------------
# ConfigManager — config CRUD
# ---------------------------------------------------------------------------


def test_manager_default_config_loaded(manager):
    cfg = manager.get_config("default")
    assert cfg is not None
    assert cfg.framework_config.get("web_port") == 6285


def test_manager_create_and_get_config(manager):
    entry = manager.create_config("test-profile", description="For testing")
    assert entry.id != "default"
    assert entry.name == "test-profile"

    loaded = manager.get_config(entry.id)
    assert loaded is not None
    assert loaded.framework_config.get("web_port") == 6285


def test_manager_list_configs_includes_default(manager):
    manager.create_config("profile-a")
    ids = [e.id for e in manager.list_configs()]
    assert "default" in ids
    assert any(e.name == "profile-a" for e in manager.list_configs())


async def test_manager_delete_config(manager):
    entry = manager.create_config("to-delete")
    result = await manager.delete_config(entry.id)
    assert result is True
    assert manager.get_config(entry.id) is None


async def test_manager_delete_default_raises(manager):
    with pytest.raises(ValueError):
        await manager.delete_config("default")


def test_manager_rename_config(manager):
    entry = manager.create_config("old-name")
    ok = manager.rename_config(entry.id, "new-name", description="updated")
    assert ok is True
    assert manager.get_entry(entry.id).name == "new-name"
    assert manager.get_entry(entry.id).description == "updated"


def test_manager_index_persists(tmp_dirs, framework):
    default_cfg, configs_dir, routing_path = tmp_dirs
    m1 = ConfigManager(framework, default_cfg, configs_dir, routing_path)
    entry = m1.create_config("persisted")

    m2 = ConfigManager(framework, default_cfg, configs_dir, routing_path)
    ids = [e.id for e in m2.list_configs()]
    assert entry.id in ids


# ---------------------------------------------------------------------------
# ConfigManager — section patching
# ---------------------------------------------------------------------------


async def test_manager_set_provider(manager):
    await manager.set_provider("openai", {"api_key": "sk-test", "model": "gpt-4o"})
    providers = manager.get_providers()
    assert providers["openai"]["api_key"] == "sk-test"


async def test_manager_delete_provider(manager):
    await manager.set_provider("anthropic", {"api_key": "sk-ant"})
    deleted = await manager.delete_provider("anthropic")
    assert deleted is True
    assert "anthropic" not in manager.get_providers()


async def test_manager_delete_nonexistent_provider(manager):
    result = await manager.delete_provider("nonexistent")
    assert result is False


async def test_manager_set_plugin_config(manager):
    await manager.set_plugin_config("my_plugin", {"timeout": 30})
    configs = manager.get_plugin_configs()
    assert configs["my_plugin"]["timeout"] == 30


async def test_manager_upsert_platform(manager):
    await manager.upsert_platform(
        "bot-1",
        {"type": "onebot_v11", "instance_uuid": "bot-1", "enabled": True},
    )
    platforms = manager.get_platforms()
    assert any(p["instance_uuid"] == "bot-1" for p in platforms)


async def test_manager_upsert_platform_updates_existing(manager):
    cfg_v1 = {"type": "onebot_v11", "instance_uuid": "bot-1", "port": 6700}
    cfg_v2 = {"type": "onebot_v11", "instance_uuid": "bot-1", "port": 7700}
    await manager.upsert_platform("bot-1", cfg_v1)
    await manager.upsert_platform("bot-1", cfg_v2)
    platforms = manager.get_platforms()
    assert len([p for p in platforms if p["instance_uuid"] == "bot-1"]) == 1
    assert platforms[0]["port"] == 7700


async def test_manager_delete_platform(manager):
    await manager.upsert_platform("bot-x", {"instance_uuid": "bot-x"})
    deleted = await manager.delete_platform("bot-x")
    assert deleted is True
    assert all(p.get("instance_uuid") != "bot-x" for p in manager.get_platforms())


# ---------------------------------------------------------------------------
# ConfigManager — route-aware lookup
# ---------------------------------------------------------------------------


def test_manager_get_config_for_routes_correctly(manager):
    @dataclass
    class FakeExecution:
        platform_instance_uuid: str | None = "qq_bot_1"
        scope: str = "group"
        group_id: str | None = "777"
        chat_id: str | None = None

    entry = manager.create_config("vip-group")
    manager.router.add_route("qq_bot_1", "group", "777", entry.id)

    cfg = manager.get_config_for(FakeExecution())
    assert cfg is manager.get_config(entry.id)


def test_manager_get_config_for_falls_back_to_default(manager):
    @dataclass
    class FakeExecution:
        platform_instance_uuid: str | None = "unknown"
        scope: str = "private"
        group_id: str | None = None
        chat_id: str | None = "42"

    cfg = manager.get_config_for(FakeExecution())
    assert cfg is manager.get_config("default")
