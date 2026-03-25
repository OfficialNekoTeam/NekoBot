from __future__ import annotations

from packages.conversations.context import ConfigurationContext
from packages.runtime.context import ExecutionContext


def test_configuration_context_resolves_provider_name_with_conversation_override() -> (
    None
):
    context = ConfigurationContext(
        framework_config={"default_provider": "openai"},
        conversation_config={"provider_name": "anthropic"},
    )

    assert context.resolve_provider_name() == "anthropic"


def test_configuration_context_falls_back_to_framework_default_provider() -> None:
    context = ConfigurationContext(framework_config={"default_provider": "gemini"})

    assert context.resolve_provider_name() == "gemini"


def test_configuration_context_resolves_moderation_strategy() -> None:
    context = ConfigurationContext(
        framework_config={"moderation_strategy": "keywords"},
        moderation_config={"strategy": "baidu_aip"},
    )

    assert context.resolve_moderation_strategy() == "baidu_aip"


def test_plugin_binding_can_disable_plugin() -> None:
    context = ConfigurationContext(plugin_bindings={"demo": {"enabled": False}})

    assert context.is_plugin_enabled("demo") is False


def test_plugin_binding_matches_scope_constraints() -> None:
    context = ConfigurationContext(
        plugin_bindings={
            "demo": {
                "enabled": True,
                "scopes": ["group"],
                "platforms": ["onebot"],
                "platform_instances": ["instance-1"],
                "enabled_chats": ["group-42"],
            }
        }
    )
    execution = ExecutionContext(
        scope="group",
        platform="onebot",
        platform_instance_uuid="instance-1",
        chat_id="group-42",
        group_id="group-42",
    )

    assert context.is_plugin_enabled("demo", execution=execution) is True


def test_plugin_binding_respects_disabled_chats() -> None:
    context = ConfigurationContext(
        plugin_bindings={
            "demo": {
                "enabled": True,
                "disabled_chats": ["group-42"],
            }
        }
    )
    execution = ExecutionContext(scope="group", chat_id="group-42", group_id="group-42")

    assert context.is_plugin_enabled("demo", execution=execution) is False
