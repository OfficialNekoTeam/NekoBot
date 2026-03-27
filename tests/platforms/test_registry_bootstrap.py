from __future__ import annotations

from typing import TypeAlias, cast

from packages.app import NekoBotFramework
from packages.platforms.bootstrap import PlatformBootstrap
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


def test_platform_registry_registers_and_lists_types() -> None:
    registry = PlatformRegistry()
    registry.register(
        platform_type="fake",
        module_path="tests.platforms.test_registry_bootstrap",
        factory_name="create_fake_adapter",
    )

    assert registry.list_types() == ("fake",)


async def test_platform_bootstrap_starts_enabled_instances() -> None:
    framework = NekoBotFramework()
    registry = PlatformRegistry()
    registry.register(
        platform_type="fake",
        module_path="tests.platforms.test_registry_bootstrap",
        factory_name="create_fake_adapter",
    )
    bootstrap = PlatformBootstrap(framework, registry=registry)

    instances = await bootstrap.start_platforms(
        [
            {"type": "fake", "instance_uuid": "instance-a", "enabled": True},
            {"type": "fake", "instance_uuid": "instance-b", "enabled": False},
        ]
    )

    assert len(instances) == 1
    assert instances[0].instance_uuid == "instance-a"
    adapter = cast(FakeAdapter, instances[0].adapter)
    assert adapter.started is True


async def test_platform_bootstrap_stops_running_instances() -> None:
    framework = NekoBotFramework()
    registry = PlatformRegistry()
    registry.register(
        platform_type="fake",
        module_path="tests.platforms.test_registry_bootstrap",
        factory_name="create_fake_adapter",
    )
    bootstrap = PlatformBootstrap(framework, registry=registry)
    instances = await bootstrap.start_platforms(
        [{"type": "fake", "instance_uuid": "instance-a", "enabled": True}]
    )

    await bootstrap.stop_platforms()

    adapter = cast(FakeAdapter, instances[0].adapter)
    assert adapter.stopped is True
    assert bootstrap.list_instances() == ()
