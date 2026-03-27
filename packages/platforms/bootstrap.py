from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from ..app import NekoBotFramework
from ..conversations.context import ConfigurationContext
from .registry import PlatformRegistry


@dataclass(slots=True)
class RunningPlatformInstance:
    platform_type: str
    instance_uuid: str
    adapter: object


class StartablePlatform(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...


class PlatformBootstrap:
    def __init__(
        self,
        framework: NekoBotFramework,
        registry: PlatformRegistry | None = None,
    ) -> None:
        self.framework: NekoBotFramework = framework
        self.registry: PlatformRegistry = registry or PlatformRegistry()
        self._instances: dict[str, RunningPlatformInstance] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        if "onebot_v11" not in self.registry.list_types():
            self.registry.register(
                platform_type="onebot_v11",
                module_path="packages.platforms.onebot_v11",
                factory_name="create_onebot_v11_adapter",
            )

    async def start_platforms(
        self,
        platform_configs: list[dict[str, object]],
        configuration: ConfigurationContext | None = None,
    ) -> tuple[RunningPlatformInstance, ...]:
        configuration = configuration or self.framework.build_configuration_context()
        started: list[RunningPlatformInstance] = []
        for config in platform_configs:
            if not bool(config.get("enabled", True)):
                continue
            platform_type = config.get("type")
            instance_uuid = config.get("instance_uuid")
            if not isinstance(platform_type, str) or not isinstance(instance_uuid, str):
                raise ValueError(
                    "platform config requires string 'type' and 'instance_uuid'"
                )
            adapter = cast(
                StartablePlatform,
                self.registry.create(
                    platform_type,
                    config,
                    framework=self.framework,
                    configuration=configuration,
                ),
            )
            await adapter.start()
            running = RunningPlatformInstance(
                platform_type=platform_type,
                instance_uuid=instance_uuid,
                adapter=adapter,
            )
            self._instances[instance_uuid] = running
            started.append(running)
        return tuple(started)

    async def stop_platforms(self) -> None:
        for instance_uuid in tuple(self._instances.keys()):
            running = self._instances.pop(instance_uuid)
            adapter = cast(StartablePlatform, running.adapter)
            await adapter.stop()

    def list_instances(self) -> tuple[RunningPlatformInstance, ...]:
        return tuple(self._instances.values())
