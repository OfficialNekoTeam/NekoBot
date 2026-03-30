from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from ..app import NekoBotFramework, create_framework
from ..conversations.context import ConfigurationContext
from ..permissions import PermissionEngine
from ..permissions.models import PermissionRule
from ..platforms.bootstrap import PlatformBootstrap, RunningPlatformInstance
from ..platforms.registry import PlatformRegistry
from ..plugins.reloader import PluginReloader
from ..providers.sources import (
    ANTHROPIC_PROVIDER_SCHEMA,
    EDGE_TTS_SCHEMA,
    GEMINI_PROVIDER_SCHEMA,
    OPENAI_COMPATIBLE_PROVIDER_SCHEMA,
    OPENAI_PROVIDER_SCHEMA,
    OPENAI_STT_SCHEMA,
    OPENAI_TTS_SCHEMA,
    AnthropicChatProvider,
    EdgeTTSProvider,
    GeminiChatProvider,
    OpenAIChatProvider,
    OpenAICompatibleChatProvider,
    OpenAISTTProvider,
    OpenAITTSProvider,
)
from .config import BootstrapConfig, normalize_app_config


@dataclass(slots=True)
class BootstrappedRuntime:
    framework: NekoBotFramework
    configuration: ConfigurationContext
    platform_bootstrap: PlatformBootstrap
    running_platforms: tuple[RunningPlatformInstance, ...]
    plugin_reloader: PluginReloader | None = None

    async def stop(self) -> None:
        if self.plugin_reloader is not None:
            self.plugin_reloader.stop_watch()
        logger.info("Stopping {} platform instance(s)...", len(self.running_platforms))
        await self.platform_bootstrap.stop_platforms()
        logger.info("Platform shutdown complete")


def _register_builtin_providers(framework: NekoBotFramework) -> None:
    framework.schema_registry.register("provider.openai", OPENAI_PROVIDER_SCHEMA)
    framework.schema_registry.register("provider.anthropic", ANTHROPIC_PROVIDER_SCHEMA)
    framework.schema_registry.register("provider.gemini", GEMINI_PROVIDER_SCHEMA)
    framework.schema_registry.register(
        "provider.openai_compatible", OPENAI_COMPATIBLE_PROVIDER_SCHEMA
    )
    framework.schema_registry.register("provider.openai_tts", OPENAI_TTS_SCHEMA)
    framework.schema_registry.register("provider.openai_stt", OPENAI_STT_SCHEMA)
    framework.schema_registry.register("provider.edge_tts", EDGE_TTS_SCHEMA)
    _ = framework.binder.bind_provider_class(OpenAIChatProvider)
    _ = framework.binder.bind_provider_class(AnthropicChatProvider)
    _ = framework.binder.bind_provider_class(GeminiChatProvider)
    _ = framework.binder.bind_provider_class(OpenAICompatibleChatProvider)
    _ = framework.binder.bind_provider_class(OpenAITTSProvider)
    _ = framework.binder.bind_provider_class(OpenAISTTProvider)
    _ = framework.binder.bind_provider_class(EdgeTTSProvider)


def _setup_permissions(
    framework: NekoBotFramework,
    permission_config: dict[str, object],
) -> None:
    """从 permission_config 提取 owner_ids 并构建 PermissionEngine。"""
    raw_ids = permission_config.get("owner_ids", [])
    if isinstance(raw_ids, list):
        framework.owner_ids = frozenset(str(uid) for uid in raw_ids if uid)

    raw_rules = permission_config.get("rules", [])
    has_rules = isinstance(raw_rules, list) and len(raw_rules) > 0

    # 只要配置了 owner_ids 或 rules，就启用权限引擎
    if not framework.owner_ids and not has_rules:
        return

    rules: list[PermissionRule] = []

    # 默认规则：所有已认证用户均可使用 provider（发起 LLM 请求）
    rules.append(
        PermissionRule(
            permissions=("provider.use",),
            roles=(),  # 空 roles = 不检查角色，所有人均可
            allow=True,
            require_all=False,
            description="default: all authenticated users can use providers",
        )
    )

    # 默认规则：owner/admin/群主/群管理 可使用管理命令
    rules.append(
        PermissionRule(
            permissions=("command.invoke",),
            roles=("owner", "super_admin", "admin", "group_owner", "group_admin"),
            allow=True,
            require_all=False,
            description="default: elevated roles can invoke commands",
        )
    )

    # 解析用户自定义 rules（简单格式）
    if isinstance(raw_rules, list):
        for raw in raw_rules:
            if not isinstance(raw, dict):
                continue
            perms_raw = raw.get("permissions", [])
            roles_raw = raw.get("roles", [])
            allow = bool(raw.get("allow", True))
            require_all = bool(raw.get("require_all", False))
            desc = str(raw.get("description", ""))
            if isinstance(perms_raw, list) and isinstance(roles_raw, list):
                rules.append(
                    PermissionRule(
                        permissions=tuple(str(p) for p in perms_raw),
                        roles=tuple(str(r) for r in roles_raw),
                        allow=allow,
                        require_all=require_all,
                        description=desc,
                    )
                )

    framework.permission_engine = PermissionEngine(tuple(rules))
    logger.info(
        "Permission engine initialized: owner_ids={} rules={}",
        len(framework.owner_ids),
        len(rules),
    )


async def bootstrap_runtime(
    app_config: BootstrapConfig | dict[object, object] | None = None,
    *,
    framework: NekoBotFramework | None = None,
    registry: PlatformRegistry | None = None,
    plugin_dir: str = "data/plugins",
    watch_plugins: bool = True,
) -> BootstrappedRuntime:
    framework = framework or create_framework()
    _register_builtin_providers(framework)
    if app_config is None:
        normalized = BootstrapConfig()
    elif isinstance(app_config, BootstrapConfig):
        normalized = app_config
    else:
        normalized = normalize_app_config(app_config)

    _setup_permissions(framework, normalized.permission_config)
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
        "Bootstrapping framework with {} configured platform instance(s)",
        len(normalized.platforms),
    )
    platform_bootstrap = PlatformBootstrap(framework, registry=registry)
    running_platforms = await platform_bootstrap.start_platforms(
        normalized.platforms,
        configuration=configuration,
    )
    if running_platforms:
        logger.info(
            "Started platform instances: {}",
            ", ".join(instance.instance_uuid for instance in running_platforms),
        )
    else:
        logger.info("No enabled platform instances configured")

    # 加载插件目录
    reloader = PluginReloader(framework)
    from pathlib import Path
    if Path(plugin_dir).exists():
        results = await reloader.load_directory(plugin_dir)
        total = sum(len(v) for v in results.values())
        if total:
            logger.info("Loaded {} plugin(s) from {}", total, plugin_dir)
        if watch_plugins:
            await reloader.watch(plugin_dir)
    else:
        logger.debug("Plugin directory not found, skipping: {}", plugin_dir)

    return BootstrappedRuntime(
        framework=framework,
        configuration=configuration,
        platform_bootstrap=platform_bootstrap,
        running_platforms=running_platforms,
        plugin_reloader=reloader,
    )
