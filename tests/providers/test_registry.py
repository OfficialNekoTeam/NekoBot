from __future__ import annotations

from typing import override

from packages.contracts.specs import ProviderSpec, RegisteredProvider, SchemaRef
from packages.providers.base import ChatProvider
from packages.providers.registry import ProviderRegistry
from packages.providers.types import ProviderRequest, ProviderResponse
from packages.runtime.registry import RuntimeRegistry
from packages.schema import ObjectSchema, SchemaRegistry, StringField


class FakeChatProvider(ChatProvider):
    setup_calls: int = 0
    teardown_calls: int = 0

    @override
    @classmethod
    def provider_spec(cls) -> ProviderSpec:
        return ProviderSpec(
            name="fake-provider",
            kind="chat",
            description="Fake provider for tests",
            config_schema=None,
            capabilities=("chat",),
            metadata={"default_config": {"region": "default"}},
        )

    @override
    async def setup(self) -> None:
        type(self).setup_calls += 1

    @override
    async def teardown(self) -> None:
        type(self).teardown_calls += 1

    @override
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(content="ok")


class SchemaBackedProvider(FakeChatProvider):
    @override
    @classmethod
    def provider_spec(cls) -> ProviderSpec:
        return ProviderSpec(
            name="schema-provider",
            kind="chat",
            description="Schema-backed provider",
            config_schema=None,
            capabilities=("chat",),
            metadata={},
        )


async def test_provider_registry_get_reuses_cached_instance() -> None:
    runtime_registry = RuntimeRegistry()
    runtime_registry.register_provider(
        RegisteredProvider(
            provider_class=FakeChatProvider, spec=FakeChatProvider.provider_spec()
        )
    )
    registry = ProviderRegistry(
        runtime_registry=runtime_registry, schema_registry=SchemaRegistry()
    )

    first = await registry.get("fake-provider")
    second = await registry.get("fake-provider")

    assert first is second
    assert FakeChatProvider.setup_calls == 1


async def test_provider_registry_reconfigure_tears_down_cached_instance() -> None:
    FakeChatProvider.setup_calls = 0
    FakeChatProvider.teardown_calls = 0
    runtime_registry = RuntimeRegistry()
    runtime_registry.register_provider(
        RegisteredProvider(
            provider_class=FakeChatProvider, spec=FakeChatProvider.provider_spec()
        )
    )
    registry = ProviderRegistry(
        runtime_registry=runtime_registry, schema_registry=SchemaRegistry()
    )

    first = await registry.get("fake-provider")
    await registry.configure("fake-provider", {"region": "cn"})
    second = await registry.get("fake-provider")

    assert first is not second
    assert FakeChatProvider.teardown_calls == 1
    assert FakeChatProvider.setup_calls == 2


async def test_provider_registry_validates_config_when_schema_is_declared() -> None:
    schema_registry = SchemaRegistry()
    schema_registry.register(
        "provider.schema-provider",
        ObjectSchema(fields={"api_key": StringField(min_length=1)}),
    )
    runtime_registry = RuntimeRegistry(schema_registry=schema_registry)
    runtime_registry.register_provider(
        RegisteredProvider(
            provider_class=SchemaBackedProvider,
            spec=ProviderSpec(
                name="schema-provider",
                kind="chat",
                description="Schema-backed provider",
                config_schema=SchemaRef("provider.schema-provider"),
                capabilities=("chat",),
                metadata={},
            ),
        )
    )
    registry = ProviderRegistry(
        runtime_registry=runtime_registry, schema_registry=schema_registry
    )

    await registry.configure("schema-provider", {"api_key": "secret"})

    provider = await registry.get("schema-provider")
    assert provider.config["api_key"] == "secret"


async def test_provider_registry_shutdown_all_closes_instances() -> None:
    FakeChatProvider.setup_calls = 0
    FakeChatProvider.teardown_calls = 0
    runtime_registry = RuntimeRegistry()
    runtime_registry.register_provider(
        RegisteredProvider(
            provider_class=FakeChatProvider, spec=FakeChatProvider.provider_spec()
        )
    )
    registry = ProviderRegistry(
        runtime_registry=runtime_registry, schema_registry=SchemaRegistry()
    )

    _ = await registry.get("fake-provider")
    await registry.shutdown_all()

    assert FakeChatProvider.teardown_calls == 1


async def test_provider_registry_list_infos_marks_configured_providers() -> None:
    runtime_registry = RuntimeRegistry()
    runtime_registry.register_provider(
        RegisteredProvider(
            provider_class=FakeChatProvider, spec=FakeChatProvider.provider_spec()
        )
    )
    registry = ProviderRegistry(
        runtime_registry=runtime_registry, schema_registry=SchemaRegistry()
    )
    await registry.configure("fake-provider", {"region": "us"})

    infos = registry.list_infos()

    assert len(infos) == 1
    assert infos[0].name == "fake-provider"
    assert infos[0].metadata["configured"] is True
