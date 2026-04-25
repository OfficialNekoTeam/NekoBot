from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from loguru import logger

from ..app import NekoBotFramework
from ..conversations.context import ConfigurationContext


@dataclass(slots=True)
class RunningPlatformInstance:
    platform_type: str
    instance_uuid: str
    adapter: object


class StartablePlatform(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...


class PlatformBootstrap:
    def __init__(self, framework: NekoBotFramework) -> None:
        self.framework: NekoBotFramework = framework
        self._instances: dict[str, RunningPlatformInstance] = {}
        self._register_defaults()

    @property
    def registry(self):  # type: ignore[override]
        return self.framework.platform_registry

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
                logger.error(
                    "PlatformBootstrap: skipping platform config with missing 'type' or 'instance_uuid': {}",
                    config,
                )
                continue
            try:
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
            except Exception as exc:
                logger.error(
                    "PlatformBootstrap: failed to start platform {!r} ({}): {}",
                    instance_uuid, platform_type, exc,
                )
                continue
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
            try:
                await adapter.stop()
            except Exception as exc:
                logger.error(
                    "PlatformBootstrap: error stopping platform {!r}: {}",
                    instance_uuid, exc,
                )

    def list_instances(self) -> tuple[RunningPlatformInstance, ...]:
        return tuple(self._instances.values())
