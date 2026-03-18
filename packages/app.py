from __future__ import annotations

from types import ModuleType
from typing import Any

from .conversations import (
    ConfigurationContext,
    ConversationContext,
    ConversationResolver,
    InMemoryConversationStore,
)
from .permissions import PermissionDecision, PermissionEngine
from .permissions.constants import PermissionName
from .providers import (
    ChatProvider,
    EmbeddingProvider,
    ProviderRegistry,
    RerankProvider,
    STTProvider,
    TTSProvider,
)
from .providers.types import (
    EmbeddingRequest,
    ProviderContext,
    ProviderRequest,
    RerankRequest,
    STTRequest,
    TTSRequest,
)
from .runtime import FrameworkBinder, RuntimeRegistry
from .runtime import context as runtime_context
from .runtime.context import ExecutionContext, PluginContext
from .schema import ObjectSchema, SchemaRegistry


class NekoBotFramework:
    def __init__(self) -> None:
        self.schema_registry = SchemaRegistry()
        self.runtime_registry = RuntimeRegistry(schema_registry=self.schema_registry)
        self.binder = FrameworkBinder(self.runtime_registry)
        self.conversation_resolver = ConversationResolver()
        self.conversation_store = InMemoryConversationStore()
        self.provider_registry = ProviderRegistry(
            runtime_registry=self.runtime_registry,
            schema_registry=self.schema_registry,
        )

    def register_schema(self, name: str, schema: ObjectSchema) -> None:
        self.runtime_registry.register_schema(name, schema)

    def bind_module(self, module: ModuleType) -> None:
        self.binder.bind_module(module)

    def build_execution_context(self, **kwargs: Any) -> ExecutionContext:
        return ExecutionContext(**kwargs)

    def build_configuration_context(
        self,
        *,
        framework_config: dict[str, Any] | None = None,
        plugin_configs: dict[str, dict[str, Any]] | None = None,
        provider_configs: dict[str, dict[str, Any]] | None = None,
        permission_config: dict[str, Any] | None = None,
        moderation_config: dict[str, Any] | None = None,
        conversation_config: dict[str, Any] | None = None,
        plugin_bindings: dict[str, dict[str, Any]] | None = None,
    ) -> ConfigurationContext:
        return ConfigurationContext(
            framework_config=framework_config or {},
            plugin_configs=plugin_configs or {},
            provider_configs=provider_configs or {},
            permission_config=permission_config or {},
            moderation_config=moderation_config or {},
            conversation_config=conversation_config or {},
            plugin_bindings=plugin_bindings or {},
        )

    def build_conversation_context(
        self,
        execution: ExecutionContext,
        configuration: ConfigurationContext | None = None,
    ) -> ConversationContext:
        resolved = self.conversation_resolver.resolve_conversation_context(
            execution=execution,
            configuration=configuration,
        )
        return self._hydrate_conversation_context(resolved)

    def save_conversation_context(
        self, conversation: ConversationContext
    ) -> ConversationContext:
        return self.conversation_store.save(conversation)

    def build_provider_context(
        self,
        *,
        provider_name: str,
        execution: ExecutionContext,
        conversation: ConversationContext | None = None,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderContext:
        conversation = conversation or self.build_conversation_context(execution)
        return ProviderContext(
            provider_name=provider_name,
            model=model,
            actor_id=execution.actor_id,
            conversation_id=execution.conversation_id,
            platform=execution.platform,
            platform_instance_uuid=execution.platform_instance_uuid,
            scope=execution.scope,
            conversation_key=(
                conversation.conversation_key.value
                if conversation.conversation_key is not None
                else None
            ),
            session_key=(
                conversation.session_key.value
                if conversation.session_key is not None
                else None
            ),
            isolation_mode=conversation.isolation_mode,
            metadata=metadata or execution.metadata.copy(),
        )

    def _hydrate_conversation_context(
        self, resolved: ConversationContext
    ) -> ConversationContext:
        stored: ConversationContext | None = None
        if resolved.conversation_key is not None:
            stored = self.conversation_store.get_conversation(
                resolved.conversation_key.value
            )
        elif resolved.session_key is not None:
            stored = self.conversation_store.get_session(resolved.session_key.value)

        if stored is None:
            return resolved

        return ConversationContext(
            isolation_mode=resolved.isolation_mode,
            conversation_key=resolved.conversation_key,
            session_key=resolved.session_key,
            conversation_id=resolved.conversation_id,
            scope=resolved.scope,
            platform_type=resolved.platform_type,
            platform_instance_uuid=resolved.platform_instance_uuid,
            chat_id=resolved.chat_id,
            actor_id=resolved.actor_id,
            thread_id=resolved.thread_id,
            history=list(stored.history),
            summary=stored.summary,
            memory_refs=list(stored.memory_refs),
            provider_preferences=dict(stored.provider_preferences),
            metadata={**stored.metadata, **resolved.metadata},
        )

    def build_plugin_context(
        self,
        *,
        plugin_name: str,
        execution: ExecutionContext,
        configuration: ConfigurationContext | None = None,
        conversation: ConversationContext | None = None,
        **kwargs: Any,
    ) -> PluginContext:
        configuration = configuration or self.build_configuration_context()
        conversation = conversation or self.build_conversation_context(
            execution=execution,
            configuration=configuration,
        )
        binding = kwargs.pop("binding", None)
        if binding is None:
            binding = self.build_effective_plugin_binding(
                plugin_name=plugin_name,
                configuration=configuration,
            )
        if not binding.enabled:
            raise ValueError(
                f"plugin is disabled for current configuration: {plugin_name}"
            )

        config = kwargs.pop("config", binding.config)
        permission_engine = kwargs.get("permission_engine")
        provider_callable = kwargs.pop("provider_callable", None)
        if provider_callable is None:
            provider_callable = self._build_provider_callable(
                execution=execution,
                configuration=configuration,
                conversation=conversation,
                permission_engine=permission_engine,
            )
        return PluginContext(
            plugin_name=plugin_name,
            config=config,
            execution=execution,
            configuration=configuration,
            conversation=conversation,
            provider_callable=provider_callable,
            **kwargs,
        )

    def build_effective_plugin_binding(
        self,
        *,
        plugin_name: str,
        configuration: ConfigurationContext,
    ) -> runtime_context.EffectivePluginBinding:
        return runtime_context.build_effective_plugin_binding(
            plugin_name, configuration
        )

    def resolve_effective_plugin_bindings(
        self,
        configuration: ConfigurationContext,
        plugin_names: list[str] | tuple[str, ...] | None = None,
    ) -> tuple[runtime_context.EffectivePluginBinding, ...]:
        names = plugin_names or tuple(sorted(self.runtime_registry.plugins.keys()))
        bindings: list[runtime_context.EffectivePluginBinding] = []
        for plugin_name in names:
            binding = self.build_effective_plugin_binding(
                plugin_name=plugin_name,
                configuration=configuration,
            )
            if binding.enabled:
                bindings.append(binding)
        return tuple(bindings)

    def _build_provider_callable(
        self,
        *,
        execution: ExecutionContext,
        configuration: ConfigurationContext,
        conversation: ConversationContext,
        permission_engine: PermissionEngine | None,
    ):
        async def call_provider(provider_name: str, **kwargs: Any) -> Any:
            return await self.invoke_provider(
                provider_name=provider_name,
                execution=execution,
                configuration=configuration,
                conversation=conversation,
                permission_engine=permission_engine,
                **kwargs,
            )

        return call_provider

    async def invoke_provider(
        self,
        *,
        provider_name: str,
        execution: ExecutionContext,
        configuration: ConfigurationContext | None = None,
        conversation: ConversationContext | None = None,
        permission_engine: PermissionEngine | None = None,
        request: Any = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> Any:
        configuration = configuration or self.build_configuration_context()
        conversation = conversation or self.build_conversation_context(
            execution=execution,
            configuration=configuration,
        )

        provider_config = configuration.get_provider_config(provider_name)
        if provider_config:
            self.provider_registry.configure(provider_name, provider_config)

        provider_context = self.build_provider_context(
            provider_name=provider_name,
            execution=execution,
            conversation=conversation,
            model=model,
            metadata=kwargs.pop("metadata", None),
        )

        provider = self.provider_registry.create(provider_name)
        _ = self._enforce_provider_permissions(
            provider_name=provider_name,
            execution=execution,
            permission_engine=permission_engine,
        )

        if request is None:
            request = self._build_provider_request(
                provider_name=provider_name,
                provider_context=provider_context,
                model=model,
                **kwargs,
            )
        else:
            request.context = provider_context

        if isinstance(provider, ChatProvider):
            return await provider.generate(request)
        if isinstance(provider, EmbeddingProvider) and isinstance(
            request, EmbeddingRequest
        ):
            return await provider.embed(request)
        if isinstance(provider, TTSProvider) and isinstance(request, TTSRequest):
            return await provider.synthesize(request)
        if isinstance(provider, STTProvider) and isinstance(request, STTRequest):
            return await provider.transcribe(request)
        if isinstance(provider, RerankProvider) and isinstance(request, RerankRequest):
            return await provider.rerank(request)

        raise TypeError(f"unsupported provider request for provider: {provider_name}")

    def _enforce_provider_permissions(
        self,
        *,
        provider_name: str,
        execution: ExecutionContext,
        permission_engine: PermissionEngine | None,
    ) -> PermissionDecision:
        if permission_engine is None:
            return PermissionDecision(
                allowed=True, reason="no permission engine attached"
            )

        registered = self.runtime_registry.providers.get(provider_name)
        permission_spec = (
            registered.spec.permissions if registered is not None else None
        )
        permissions = (
            permission_spec.permissions
            if permission_spec is not None
            else (PermissionName.PROVIDER_USE,)
        )
        require_all = (
            permission_spec.require_all if permission_spec is not None else True
        )
        decision = permission_engine.evaluate(
            permissions,
            execution.to_authorization_context(
                resource_kind="provider",
                resource_name=provider_name,
            ),
            require_all=require_all,
        )
        if not decision.allowed:
            raise PermissionError(
                f"provider access denied for '{provider_name}': {decision.reason}"
            )
        return decision

    def _build_provider_request(
        self,
        *,
        provider_name: str,
        provider_context: ProviderContext,
        model: str | None = None,
        **kwargs: Any,
    ) -> ProviderRequest:
        return ProviderRequest(
            model=model,
            prompt=kwargs.pop("prompt", None),
            system_prompt=kwargs.pop("system_prompt", None),
            messages=list(kwargs.pop("messages", [])),
            tools=list(kwargs.pop("tools", [])),
            stream=bool(kwargs.pop("stream", False)),
            options={"provider_name": provider_name, **kwargs},
            context=provider_context,
        )


def create_framework() -> NekoBotFramework:
    return NekoBotFramework()
