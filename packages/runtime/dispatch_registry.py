"""Flat dispatch registries for commands and event handlers.

CommandRegistry:    cmd_name / alias (lowercase) → CommandEntry      O(1)
EventHandlerRegistry: registered_event → list[EventHandlerEntry]     O(k) where k = distinct event types
"""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.specs import CommandSpec, EventHandlerSpec


@dataclass(frozen=True)
class CommandEntry:
    plugin_name: str
    handler_name: str
    spec: CommandSpec


@dataclass(frozen=True)
class EventHandlerEntry:
    plugin_name: str
    handler_name: str
    spec: EventHandlerSpec


class CommandRegistry:
    """Flat O(1) command lookup index.

    Built from ``@command`` decorated methods at bind time; expands aliases
    automatically.  Unregistered atomically when a plugin is unloaded.
    """

    def __init__(self) -> None:
        # lowercase name/alias → entry
        self._index: dict[str, CommandEntry] = {}
        # plugin_name → set of keys registered for that plugin
        self._by_plugin: dict[str, set[str]] = {}

    def register(
        self,
        plugin_name: str,
        commands: tuple[tuple[str, CommandSpec], ...],
    ) -> None:
        keys: set[str] = set()
        for handler_name, spec in commands:
            entry = CommandEntry(
                plugin_name=plugin_name,
                handler_name=handler_name,
                spec=spec,
            )
            for name in (spec.name, *spec.aliases):
                key = name.lower()
                self._index[key] = entry
                keys.add(key)
        self._by_plugin[plugin_name] = keys

    def unregister_plugin(self, plugin_name: str) -> None:
        for key in self._by_plugin.pop(plugin_name, set()):
            self._index.pop(key, None)

    def resolve(self, cmd_name: str) -> CommandEntry | None:
        return self._index.get(cmd_name.lower())

    def __len__(self) -> int:
        return len(self._index)


class EventHandlerRegistry:
    """Event handler index grouped by registered event name.

    ``resolve(actual_event)`` returns all handlers whose registered event
    matches exactly or is a prefix of ``actual_event``
    (e.g. ``"message"`` matches ``"message.group"``).
    """

    def __init__(self) -> None:
        # registered_event → handlers
        self._index: dict[str, list[EventHandlerEntry]] = {}
        # plugin_name → list of registered event names (may repeat)
        self._by_plugin: dict[str, list[str]] = {}

    def register(
        self,
        plugin_name: str,
        event_handlers: tuple[tuple[str, EventHandlerSpec], ...],
    ) -> None:
        events: list[str] = []
        for handler_name, spec in event_handlers:
            entry = EventHandlerEntry(
                plugin_name=plugin_name,
                handler_name=handler_name,
                spec=spec,
            )
            self._index.setdefault(spec.event, []).append(entry)
            events.append(spec.event)
        self._by_plugin[plugin_name] = events

    def unregister_plugin(self, plugin_name: str) -> None:
        for event in self._by_plugin.pop(plugin_name, []):
            bucket = self._index.get(event)
            if bucket is None:
                continue
            remaining = [e for e in bucket if e.plugin_name != plugin_name]
            if remaining:
                self._index[event] = remaining
            else:
                del self._index[event]

    def resolve(self, actual_event: str) -> list[EventHandlerEntry]:
        """Return matching entries sorted by priority descending (higher runs first)."""
        results: list[EventHandlerEntry] = []
        for registered_event, entries in self._index.items():
            if registered_event == actual_event or actual_event.startswith(
                f"{registered_event}."
            ):
                results.extend(entries)
        results.sort(key=lambda e: e.spec.priority, reverse=True)
        return results

    def __len__(self) -> int:
        return sum(len(v) for v in self._index.values())
