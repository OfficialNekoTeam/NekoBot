from __future__ import annotations

from typing import TypeAlias, cast

from packages.app import NekoBotFramework
from packages.bootstrap.config import BootstrapConfig
from packages.bootstrap.runtime import bootstrap_runtime
from packages.platforms.registry import PlatformRegistry

ValueMap: TypeAlias = dict[str, object]


class FakeAdapter:
    def __init__(self, config: ValueMap, **kwargs: object) -> None:
        self.config: ValueMap = config
        self.kwargs: dict[str, object] = kwargs
        self.started: bool = False
        self.stopped: bool = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


def create_fake_adapter(config: ValueMap, **kwargs: object) -> FakeAdapter:
    return FakeAdapter(config, **kwargs)


async def test_bootstrap_runtime_starts_and_stops_platforms() -> None:
    framework = NekoBotFramework()
    registry = PlatformRegistry()
    registry.register(
        platform_type="fake",
        module_path="tests.bootstrap.test_main_bootstrap",
        factory_name="create_fake_adapter",
    )
    config = BootstrapConfig(platforms=[{"type": "fake", "instance_uuid": "bot-a"}])

    runtime = await bootstrap_runtime(config, framework=framework, registry=registry)

    assert len(runtime.running_platforms) == 1
    adapter = cast(FakeAdapter, runtime.running_platforms[0].adapter)
    assert adapter.started is True

    await runtime.stop()

    assert adapter.stopped is True


async def test_bootstrap_runtime_builds_configuration_context() -> None:
    framework = NekoBotFramework()
    registry = PlatformRegistry()
    registry.register(
        platform_type="fake",
        module_path="tests.bootstrap.test_main_bootstrap",
        factory_name="create_fake_adapter",
    )
    config = BootstrapConfig(
        framework_config={"default_provider": "openai"},
        conversation_config={"isolation_mode": "per_user"},
        platforms=[{"type": "fake", "instance_uuid": "bot-a"}],
    )

    runtime = await bootstrap_runtime(config, framework=framework, registry=registry)

    assert runtime.configuration.resolve_provider_name() == "openai"
    assert runtime.configuration.isolation_mode == "per_user"

    await runtime.stop()

    adapter = cast(FakeAdapter, runtime.running_platforms[0].adapter)
    assert adapter.stopped is True
