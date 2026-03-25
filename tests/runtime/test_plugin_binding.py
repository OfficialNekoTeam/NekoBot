from __future__ import annotations

from packages.conversations.context import ConfigurationContext
from packages.permissions.constants import ScopeName
from packages.runtime.context import ExecutionContext, build_effective_plugin_binding


def _execution_context(**overrides: object) -> ExecutionContext:
    context = ExecutionContext(
        platform="onebot",
        platform_instance_uuid="instance-1",
        scope=ScopeName.GROUP,
        chat_id="group-42",
        group_id="group-42",
        actor_id="user-7",
    )
    for key, value in overrides.items():
        setattr(context, key, value)
    return context


def test_effective_plugin_binding_merges_base_and_override_config() -> None:
    configuration = ConfigurationContext(
        plugin_configs={"demo": {"temperature": 0.2, "mode": "base"}},
        plugin_bindings={
            "demo": {
                "enabled": True,
                "config": {"temperature": 0.8},
                "source": "group-override",
            }
        },
    )

    binding = build_effective_plugin_binding("demo", configuration)

    assert binding.enabled is True
    assert binding.config == {"temperature": 0.8, "mode": "base"}
    assert binding.metadata == {"source": "group-override"}


def test_effective_plugin_binding_respects_scope_constraints() -> None:
    configuration = ConfigurationContext(
        plugin_bindings={
            "demo": {
                "enabled": True,
                "scopes": [ScopeName.GROUP],
                "platforms": ["onebot"],
                "platform_instances": ["instance-1"],
                "enabled_chats": ["group-42"],
            }
        }
    )
    execution = _execution_context()

    binding = build_effective_plugin_binding("demo", configuration, execution)

    assert binding.enabled is True


def test_effective_plugin_binding_disables_when_chat_not_allowed() -> None:
    configuration = ConfigurationContext(
        plugin_bindings={
            "demo": {
                "enabled": True,
                "enabled_chats": ["group-43"],
            }
        }
    )
    execution = _execution_context(chat_id="group-42", group_id="group-42")

    binding = build_effective_plugin_binding("demo", configuration, execution)

    assert binding.enabled is False


def test_effective_plugin_binding_disabled_flag_overrides_base_config() -> None:
    configuration = ConfigurationContext(
        plugin_configs={"demo": {"mode": "base"}},
        plugin_bindings={"demo": {"enabled": False, "config": {"mode": "override"}}},
    )

    binding = build_effective_plugin_binding("demo", configuration)

    assert binding.enabled is False
    assert binding.config == {"mode": "override"}
