from __future__ import annotations

from typing import override

import pytest

from packages.app import NekoBotFramework
from packages.contracts.specs import PermissionSpec, ProviderSpec, RegisteredProvider
from packages.permissions import PermissionDecision, PermissionEngine, PermissionRule
from packages.permissions.constants import PermissionName, ScopeName
from packages.providers.base import ChatProvider
from packages.providers.types import (
    ChatMessage,
    ProviderContext,
    ProviderRequest,
    ProviderResponse,
)
from packages.runtime.context import ExecutionContext


class FrameworkHarness(NekoBotFramework):
    def build_request_for_test(
        self,
        *,
        provider_name: str,
        provider_context: ProviderContext,
        model: str | None = None,
        **kwargs: object,
    ) -> ProviderRequest:
        return self._build_provider_request(
            provider_name=provider_name,
            provider_context=provider_context,
            model=model,
            **kwargs,
        )

    def enforce_provider_permissions_for_test(
        self,
        *,
        provider_name: str,
        execution: ExecutionContext,
        permission_engine: PermissionEngine | None,
    ) -> PermissionDecision:
        return self._enforce_provider_permissions(
            provider_name=provider_name,
            execution=execution,
            permission_engine=permission_engine,
        )


class FakeChatProvider(ChatProvider):
    @override
    @classmethod
    def provider_spec(cls) -> ProviderSpec:
        return ProviderSpec(
            name="fake-chat",
            kind="chat",
            description="Fake chat provider",
            capabilities=("chat",),
            metadata={},
        )

    @override
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(content=request.prompt or "")


@pytest.mark.asyncio
async def test_build_provider_request_coerces_messages_and_tools() -> None:
    framework = FrameworkHarness()
    provider_context = await framework.build_provider_context(
        provider_name="fake-chat",
        execution=framework.build_execution_context(
            platform="onebot",
            platform_instance_uuid="instance-1",
            scope=ScopeName.GROUP,
            chat_id="group-42",
            actor_id="user-7",
        ),
    )

    request = framework.build_request_for_test(
        provider_name="fake-chat",
        provider_context=provider_context,
        prompt="hello",
        messages=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "there", "name": "bot"},
            {"role": 1, "content": "ignored"},
        ],
        tools=[
            {
                "name": "weather",
                "description": "Get weather",
                "parameters": {"type": "object"},
            },
            {"name": 1},
        ],
        stream=True,
        temperature=0.2,
    )

    assert request.prompt == "hello"
    assert request.stream is True
    assert len(request.messages) == 2
    assert request.messages[0] == ChatMessage(role="user", content="hi")
    assert request.messages[1].name == "bot"
    assert len(request.tools) == 1
    assert request.tools[0].name == "weather"
    assert request.options["provider_name"] == "fake-chat"
    assert request.options["temperature"] == 0.2


@pytest.mark.asyncio
async def test_build_plugin_context_raises_when_plugin_disabled() -> None:
    framework = FrameworkHarness()
    execution = framework.build_execution_context(
        platform="onebot",
        platform_instance_uuid="instance-1",
        scope=ScopeName.GROUP,
        chat_id="group-42",
        actor_id="user-7",
    )
    configuration = framework.build_configuration_context(
        plugin_bindings={"demo": {"enabled": False}}
    )

    with pytest.raises(ValueError, match="plugin is disabled"):
        _ = await framework.build_plugin_context(
            plugin_name="demo",
            execution=execution,
            configuration=configuration,
        )


def test_enforce_provider_permissions_allows_with_matching_rule() -> None:
    framework = FrameworkHarness()
    engine = PermissionEngine(
        rules=(
            PermissionRule(
                permissions=(PermissionName.PROVIDER_USE,),
                scopes=(ScopeName.GROUP,),
                resource_kinds=("provider",),
            ),
        )
    )
    execution = framework.build_execution_context(
        platform="onebot",
        platform_instance_uuid="instance-1",
        scope=ScopeName.GROUP,
        chat_id="group-42",
        actor_id="user-7",
    )

    decision = framework.enforce_provider_permissions_for_test(
        provider_name="openai",
        execution=execution,
        permission_engine=engine,
    )

    assert isinstance(decision, PermissionDecision)
    assert decision.allowed is True


def test_enforce_provider_permissions_raises_when_denied() -> None:
    framework = FrameworkHarness()
    execution = framework.build_execution_context(
        platform="onebot",
        platform_instance_uuid="instance-1",
        scope=ScopeName.GROUP,
        chat_id="group-42",
        actor_id="user-7",
    )
    framework.runtime_registry.register_provider(
        RegisteredProvider(
            provider_class=FakeChatProvider,
            spec=ProviderSpec(
                name="fake-chat",
                kind="chat",
                permissions=PermissionSpec(permissions=("provider.custom",)),
            ),
        )
    )
    engine = PermissionEngine(
        rules=(
            PermissionRule(
                permissions=("provider.custom",),
                allow=False,
                resource_kinds=("provider",),
                resources=("fake-chat",),
            ),
        )
    )

    with pytest.raises(PermissionError, match="provider access denied"):
        _ = framework.enforce_provider_permissions_for_test(
            provider_name="fake-chat",
            execution=execution,
            permission_engine=engine,
        )
