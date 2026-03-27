from __future__ import annotations

from dataclasses import dataclass
import logging

from ..app import NekoBotFramework, create_framework
from ..conversations.context import ConfigurationContext
from ..platforms.bootstrap import PlatformBootstrap, RunningPlatformInstance
from ..platforms.registry import PlatformRegistry
from .config import BootstrapConfig, normalize_app_config


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BootstrappedRuntime:
    framework: NekoBotFramework
    configuration: ConfigurationContext
    platform_bootstrap: PlatformBootstrap
    running_platforms: tuple[RunningPlatformInstance, ...]

    async def stop(self) -> None:
        logger.info("Stopping %s platform instance(s)...", len(self.running_platforms))
        await self.platform_bootstrap.stop_platforms()
        logger.info("Platform shutdown complete")


async def bootstrap_runtime(
    app_config: BootstrapConfig | dict[object, object] | None = None,
    *,
    framework: NekoBotFramework | None = None,
    registry: PlatformRegistry | None = None,
) -> BootstrappedRuntime:
    framework = framework or create_framework()
    if app_config is None:
        normalized = BootstrapConfig()
    elif isinstance(app_config, BootstrapConfig):
        normalized = app_config
    else:
        normalized = normalize_app_config(app_config)

    configuration = framework.build_configuration_context(
        framework_config=normalized.framework_config,
        plugin_configs=normalized.plugin_configs,
        provider_configs=normalized.provider_configs,
        permission_config=normalized.permission_config,
        moderation_config=normalized.moderation_config,
        conversation_config=normalized.conversation_config,
        plugin_bindings=normalized.plugin_bindings,
    )
    logger.info(
        "Bootstrapping framework with %s configured platform instance(s)",
        len(normalized.platforms),
    )
    platform_bootstrap = PlatformBootstrap(framework, registry=registry)
    running_platforms = await platform_bootstrap.start_platforms(
        normalized.platforms,
        configuration=configuration,
    )
    if running_platforms:
        logger.info(
            "Started platform instances: %s",
            ", ".join(instance.instance_uuid for instance in running_platforms),
        )
    else:
        logger.info("No enabled platform instances configured")
    return BootstrappedRuntime(
        framework=framework,
        configuration=configuration,
        platform_bootstrap=platform_bootstrap,
        running_platforms=running_platforms,
    )
