"""Tests for @command decorator dispatch and PluginReloader."""
from __future__ import annotations

from packages.app import NekoBotFramework
from packages.decorators import command, event_handler, plugin
from packages.platforms.onebot_v11.dispatch import OneBotV11Dispatcher
from packages.platforms.onebot_v11.message_codec import OneBotV11MessageCodec
from packages.platforms.types import PlatformEvent, Scene
from packages.plugins import BasePlugin, PluginReloader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(plain_text: str = "", *, self_id: str = "bot") -> PlatformEvent:
    return PlatformEvent(
        event_type="message",
        event_name="message.group",
        scene=Scene.GROUP,
        platform="onebot",
        platform_instance_uuid="inst-1",
        self_id=self_id,
        user_id="user-1",
        group_id="group-1",
        chat_id="group-1",
        message_id="msg-1",
        plain_text=plain_text,
    )


def _make_dispatcher(framework: NekoBotFramework) -> OneBotV11Dispatcher:
    async def send_callable(t: object, s: object) -> dict[str, object]:
        return {"status": "ok", "data": {"message_id": 1}}

    return OneBotV11Dispatcher(
        framework,
        send_callable=send_callable,  # type: ignore[arg-type]
        message_codec=OneBotV11MessageCodec(),
    )


# ---------------------------------------------------------------------------
# @command dispatch
# ---------------------------------------------------------------------------


async def test_command_decorator_routes_to_handler() -> None:
    """@command method is called when message matches /cmd_name."""
    called: list[dict[str, object]] = []

    @plugin(name="cmd-plugin")
    class CmdPlugin(BasePlugin):
        @command(name="ping", description="reply pong")
        async def do_ping(self, payload: dict[str, object]) -> None:
            called.append(payload)
            await self.context.reply("pong")

    framework = NekoBotFramework()
    framework.binder.bind_plugin_class(CmdPlugin)
    dispatcher = _make_dispatcher(framework)

    await dispatcher.dispatch_event(_event("/ping"))

    assert len(called) == 1
    assert called[0]["command_name"] == "ping"
    assert called[0]["command_args"] == []


async def test_command_receives_args() -> None:
    """command_args contains tokens after the command name."""
    received_args: list[list[str]] = []

    @plugin(name="args-plugin")
    class ArgsPlugin(BasePlugin):
        @command(name="say")
        async def do_say(self, payload: dict[str, object]) -> None:
            received_args.append(list(payload["command_args"]))  # type: ignore[arg-type]

    framework = NekoBotFramework()
    framework.binder.bind_plugin_class(ArgsPlugin)
    dispatcher = _make_dispatcher(framework)

    await dispatcher.dispatch_event(_event("/say hello world"))

    assert received_args == [["hello", "world"]]


async def test_command_alias_matches() -> None:
    """@command aliases are also matched."""
    called: list[str] = []

    @plugin(name="alias-plugin")
    class AliasPlugin(BasePlugin):
        @command(name="hello", aliases=("hi", "hey"))
        async def do_hello(self, payload: dict[str, object]) -> None:
            called.append(str(payload["command_name"]))

    framework = NekoBotFramework()
    framework.binder.bind_plugin_class(AliasPlugin)
    dispatcher = _make_dispatcher(framework)

    await dispatcher.dispatch_event(_event("/hi"))

    assert called == ["hi"]


async def test_command_does_not_trigger_event_handler() -> None:
    """When a command matches, event handlers on the same plugin are NOT called."""
    event_called: list[bool] = []
    cmd_called: list[bool] = []

    @plugin(name="mixed-plugin")
    class MixedPlugin(BasePlugin):
        @command(name="foo")
        async def do_foo(self, payload: dict[str, object]) -> None:
            cmd_called.append(True)

        @event_handler(event="message.group")
        async def on_group_msg(self, payload: dict[str, object]) -> None:
            event_called.append(True)

    framework = NekoBotFramework()
    framework.binder.bind_plugin_class(MixedPlugin)
    dispatcher = _make_dispatcher(framework)

    await dispatcher.dispatch_event(_event("/foo"))

    assert cmd_called == [True]
    assert event_called == []


async def test_non_command_message_skips_command_and_hits_event_handler() -> None:
    """Plain text that doesn't match a command falls through to event_handler."""
    event_called: list[bool] = []
    cmd_called: list[bool] = []

    @plugin(name="passthrough-plugin")
    class PassPlugin(BasePlugin):
        @command(name="foo")
        async def do_foo(self, payload: dict[str, object]) -> None:
            cmd_called.append(True)

        @event_handler(event="message.group")
        async def on_group_msg(self, payload: dict[str, object]) -> None:
            event_called.append(True)

    framework = NekoBotFramework()
    framework.binder.bind_plugin_class(PassPlugin)
    dispatcher = _make_dispatcher(framework)

    await dispatcher.dispatch_event(_event("hello world"))

    assert cmd_called == []
    assert event_called == [True]


async def test_custom_command_prefix_from_config() -> None:
    """command_prefix from framework_config is respected."""
    called: list[str] = []

    @plugin(name="prefix-plugin")
    class PrefixPlugin(BasePlugin):
        @command(name="test")
        async def do_test(self, payload: dict[str, object]) -> None:
            called.append(str(payload["command_name"]))

    framework = NekoBotFramework()
    framework.binder.bind_plugin_class(PrefixPlugin)
    dispatcher = _make_dispatcher(framework)
    configuration = framework.build_configuration_context(
        framework_config={"command_prefix": "!"}
    )

    await dispatcher.dispatch_event(_event("!test"), configuration)

    assert called == ["test"]


# ---------------------------------------------------------------------------
# PluginReloader
# ---------------------------------------------------------------------------


async def test_plugin_reloader_load_and_unload() -> None:
    """load() registers plugin; unload() removes it."""
    framework = NekoBotFramework()
    reloader = PluginReloader(framework)

    reloader.load("tests.plugins._fixture_plugin")

    assert "fixture-plugin" in framework.runtime_registry.plugins

    reloader.unload("tests.plugins._fixture_plugin")

    assert "fixture-plugin" not in framework.runtime_registry.plugins


async def test_plugin_reloader_reload() -> None:
    """reload() unregisters old, re-registers new — no duplicate error."""
    framework = NekoBotFramework()
    reloader = PluginReloader(framework)

    reloader.load("tests.plugins._fixture_plugin")
    assert "fixture-plugin" in framework.runtime_registry.plugins

    reloader.reload("tests.plugins._fixture_plugin")

    assert "fixture-plugin" in framework.runtime_registry.plugins
    assert reloader.loaded_plugins["fixture-plugin"] == "tests.plugins._fixture_plugin"


async def test_plugin_reloader_reload_by_name() -> None:
    """reload_plugin(name) works via name → module mapping."""
    framework = NekoBotFramework()
    reloader = PluginReloader(framework)

    reloader.load("tests.plugins._fixture_plugin")
    ok = reloader.reload_plugin("fixture-plugin")

    assert ok is True
    assert "fixture-plugin" in framework.runtime_registry.plugins


async def test_plugin_reloader_reload_unknown_name_returns_false() -> None:
    framework = NekoBotFramework()
    reloader = PluginReloader(framework)
    assert reloader.reload_plugin("no-such-plugin") is False


async def test_plugin_reloader_load_directory(tmp_path: object) -> None:
    """load_directory() discovers subdirs with __init__.py and loads their plugins."""
    from pathlib import Path

    base = Path(str(tmp_path))  # type: ignore[arg-type]

    # Valid plugin package
    pkg = base / "myplugin"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "from packages.decorators import plugin\n"
        "from packages.plugins import BasePlugin\n"
        "\n"
        "@plugin(name='dir-plugin', version='1.0.0')\n"
        "class DirPlugin(BasePlugin):\n"
        "    pass\n"
    )

    # Dir without __init__.py — should be skipped
    bad = base / "notaplugin"
    bad.mkdir()
    (bad / "main.py").write_text("")

    framework = NekoBotFramework()
    reloader = PluginReloader(framework)
    results = await reloader.load_directory(base)

    assert "myplugin" in results
    assert "dir-plugin" in results["myplugin"]
    assert "dir-plugin" in framework.runtime_registry.plugins
    assert "notaplugin" not in results
