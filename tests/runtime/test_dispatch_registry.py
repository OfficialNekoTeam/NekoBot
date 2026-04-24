from __future__ import annotations

from packages.contracts.specs import CommandSpec, EventHandlerSpec
from packages.runtime.dispatch_registry import (
    CommandEntry,
    CommandRegistry,
    EventHandlerEntry,
    EventHandlerRegistry,
)


def _cmd_spec(name: str, aliases: tuple[str, ...] = ()) -> CommandSpec:
    return CommandSpec(name=name, aliases=aliases)


def _evt_spec(event: str) -> EventHandlerSpec:
    return EventHandlerSpec(event=event)


# ---------------------------------------------------------------------------
# CommandRegistry
# ---------------------------------------------------------------------------

def test_command_registry_empty_len() -> None:
    assert len(CommandRegistry()) == 0


def test_command_registry_register_and_resolve() -> None:
    reg = CommandRegistry()
    reg.register("plugin_a", (("handle_ping", _cmd_spec("ping")),))
    entry = reg.resolve("ping")
    assert entry is not None
    assert entry.plugin_name == "plugin_a"
    assert entry.handler_name == "handle_ping"


def test_command_registry_resolve_case_insensitive() -> None:
    reg = CommandRegistry()
    reg.register("p", (("h", _cmd_spec("PING")),))
    assert reg.resolve("ping") is not None
    assert reg.resolve("PING") is not None
    assert reg.resolve("Ping") is not None


def test_command_registry_aliases_registered() -> None:
    reg = CommandRegistry()
    reg.register("p", (("h", _cmd_spec("help", aliases=("?", "h"))),))
    assert reg.resolve("help") is not None
    assert reg.resolve("?") is not None
    assert reg.resolve("h") is not None


def test_command_registry_aliases_counted_in_len() -> None:
    reg = CommandRegistry()
    reg.register("p", (("h", _cmd_spec("help", aliases=("?",))),))
    assert len(reg) == 2  # "help" + "?"


def test_command_registry_resolve_unknown_returns_none() -> None:
    reg = CommandRegistry()
    assert reg.resolve("unknown") is None


def test_command_registry_multiple_commands() -> None:
    reg = CommandRegistry()
    reg.register(
        "plugin_a",
        (
            ("handle_ping", _cmd_spec("ping")),
            ("handle_pong", _cmd_spec("pong")),
        ),
    )
    assert reg.resolve("ping") is not None
    assert reg.resolve("pong") is not None
    assert len(reg) == 2


def test_command_registry_unregister_plugin_removes_commands() -> None:
    reg = CommandRegistry()
    reg.register("plugin_a", (("handle_ping", _cmd_spec("ping", aliases=("p",))),))
    assert len(reg) == 2
    reg.unregister_plugin("plugin_a")
    assert len(reg) == 0
    assert reg.resolve("ping") is None
    assert reg.resolve("p") is None


def test_command_registry_unregister_unknown_plugin_noop() -> None:
    reg = CommandRegistry()
    reg.unregister_plugin("ghost")  # must not raise


def test_command_registry_unregister_does_not_affect_other_plugins() -> None:
    reg = CommandRegistry()
    reg.register("plugin_a", (("h1", _cmd_spec("cmd_a")),))
    reg.register("plugin_b", (("h2", _cmd_spec("cmd_b")),))
    reg.unregister_plugin("plugin_a")
    assert reg.resolve("cmd_a") is None
    assert reg.resolve("cmd_b") is not None


def test_command_registry_last_registration_wins_for_same_name() -> None:
    reg = CommandRegistry()
    reg.register("plugin_a", (("h1", _cmd_spec("ping")),))
    reg.register("plugin_b", (("h2", _cmd_spec("ping")),))
    entry = reg.resolve("ping")
    assert entry is not None
    assert entry.plugin_name == "plugin_b"


def test_command_entry_fields() -> None:
    spec = _cmd_spec("ping")
    entry = CommandEntry(plugin_name="p", handler_name="h", spec=spec)
    assert entry.plugin_name == "p"
    assert entry.handler_name == "h"
    assert entry.spec is spec


# ---------------------------------------------------------------------------
# EventHandlerRegistry
# ---------------------------------------------------------------------------

def test_event_handler_registry_empty_len() -> None:
    assert len(EventHandlerRegistry()) == 0


def test_event_handler_registry_register_and_resolve_exact() -> None:
    reg = EventHandlerRegistry()
    reg.register("plugin_a", (("on_msg", _evt_spec("message")),))
    results = reg.resolve("message")
    assert len(results) == 1
    assert results[0].plugin_name == "plugin_a"
    assert results[0].handler_name == "on_msg"


def test_event_handler_registry_prefix_match() -> None:
    reg = EventHandlerRegistry()
    reg.register("plugin_a", (("on_msg", _evt_spec("message")),))
    results = reg.resolve("message.group")
    assert len(results) == 1
    assert results[0].handler_name == "on_msg"


def test_event_handler_registry_prefix_not_a_substring() -> None:
    reg = EventHandlerRegistry()
    reg.register("plugin_a", (("on_msg", _evt_spec("message")),))
    # "messagegroup" should NOT match "message" (no dot separator)
    assert reg.resolve("messagegroup") == []


def test_event_handler_registry_exact_and_prefix_both_match() -> None:
    reg = EventHandlerRegistry()
    reg.register("plugin_a", (("on_any_msg", _evt_spec("message")),))
    reg.register("plugin_b", (("on_group_msg", _evt_spec("message.group")),))
    results = reg.resolve("message.group")
    handler_names = {r.handler_name for r in results}
    assert "on_any_msg" in handler_names
    assert "on_group_msg" in handler_names


def test_event_handler_registry_no_match_returns_empty() -> None:
    reg = EventHandlerRegistry()
    reg.register("plugin_a", (("on_msg", _evt_spec("message")),))
    assert reg.resolve("notice") == []


def test_event_handler_registry_multiple_handlers_same_event() -> None:
    reg = EventHandlerRegistry()
    reg.register(
        "plugin_a",
        (
            ("h1", _evt_spec("message")),
            ("h2", _evt_spec("message")),
        ),
    )
    assert len(reg.resolve("message")) == 2


def test_event_handler_registry_len_counts_all_entries() -> None:
    reg = EventHandlerRegistry()
    reg.register(
        "plugin_a",
        (
            ("h1", _evt_spec("message")),
            ("h2", _evt_spec("notice")),
        ),
    )
    assert len(reg) == 2


def test_event_handler_registry_unregister_plugin() -> None:
    reg = EventHandlerRegistry()
    reg.register("plugin_a", (("on_msg", _evt_spec("message")),))
    reg.unregister_plugin("plugin_a")
    assert len(reg) == 0
    assert reg.resolve("message") == []


def test_event_handler_registry_unregister_unknown_plugin_noop() -> None:
    reg = EventHandlerRegistry()
    reg.unregister_plugin("ghost")  # must not raise


def test_event_handler_registry_unregister_only_removes_own_handlers() -> None:
    reg = EventHandlerRegistry()
    reg.register("plugin_a", (("h_a", _evt_spec("message")),))
    reg.register("plugin_b", (("h_b", _evt_spec("message")),))
    reg.unregister_plugin("plugin_a")
    results = reg.resolve("message")
    assert len(results) == 1
    assert results[0].plugin_name == "plugin_b"


def test_event_handler_entry_fields() -> None:
    spec = _evt_spec("message")
    entry = EventHandlerEntry(plugin_name="p", handler_name="h", spec=spec)
    assert entry.plugin_name == "p"
    assert entry.handler_name == "h"
    assert entry.spec is spec
