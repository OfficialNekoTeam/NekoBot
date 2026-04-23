from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .bootstrap.config import BootstrapConfig

from .conversations import (
    ConfigurationContext,
    ConversationContext,
    ConversationResolver,
    ConversationStore,
    SQLiteConversationStore,
)
from .moderation import ModerationService
from .moderation.types import ModerationDecision, ModerationRequest, ModerationStage
from .permissions import PermissionDecision, PermissionEngine
from .permissions.constants import PermissionName, ScopeName
from .providers import (
    ChatProvider,
    EmbeddingProvider,
    ProviderRegistry,
    RerankProvider,
    STTProvider,
    TTSProvider,
)
from .providers.types import (
    ChatMessage,
    EmbeddingRequest,
    ProviderContext,
    ProviderRequest,
    RerankRequest,
    STTRequest,
    ToolDefinition,
    TTSRequest,
    ValueMap,
)
from .runtime import (
    CommandRegistry,
    EventHandlerRegistry,
    FrameworkBinder,
    RuntimeRegistry,
)
from .runtime import context as runtime_context
from .runtime.context import ExecutionContext, PluginContext
from .schema import ObjectSchema, SchemaRegistry
from .skills.manager import SkillManager
from .tools import ToolRegistry
from .tools.mcp.manager import MCPManager


class NekoBotFramework:
    def __init__(self, conversation_store: ConversationStore | None = None) -> None:
        self.schema_registry: SchemaRegistry = SchemaRegistry()
        # 命令 / 事件分发注册表（由 RuntimeRegistry 负责填充）
        self.command_registry: CommandRegistry = CommandRegistry()
        self.event_handler_registry: EventHandlerRegistry = EventHandlerRegistry()
        self.runtime_registry: RuntimeRegistry = RuntimeRegistry(
            schema_registry=self.schema_registry,
            command_registry=self.command_registry,
            event_handler_registry=self.event_handler_registry,
        )
        self.binder: FrameworkBinder = FrameworkBinder(self.runtime_registry)
        self.conversation_resolver: ConversationResolver = ConversationResolver()
        self.conversation_store: ConversationStore = (
            conversation_store
            or SQLiteConversationStore(Path("data/conversations.sqlite3"))
        )
        self.moderation_service: ModerationService = ModerationService()
        self.provider_registry: ProviderRegistry = ProviderRegistry(
            runtime_registry=self.runtime_registry,
            schema_registry=self.schema_registry,
        )
        # 权限引擎和 owner ID 集合，由 bootstrap 注入
        self.permission_engine: PermissionEngine | None = None
        self.owner_ids: frozenset[str] = frozenset()
        # Agent 工具注册表
        self.tool_registry: ToolRegistry = ToolRegistry()
        self.binder._tool_registry = self.tool_registry
        # MCP 管理器
        self.mcp_manager: MCPManager = MCPManager(self.tool_registry)
        # Skill 管理器 (指令化扩展)
        self.skill_manager: SkillManager = SkillManager(self)
        self._register_builtin_tools()
        self._config_observers: list[Callable[[BootstrapConfig], Awaitable[None]]] = []

    def add_config_observer(self, observer: Callable[[BootstrapConfig], Awaitable[None]]) -> None:
        self._config_observers.append(observer)

    async def update_framework_config(self, new_config: BootstrapConfig) -> None:
        """原子更新全局配置并触发观察者。"""
        from .bootstrap.config import save_app_config  # lazy: avoids app ↔ bootstrap circular import
        save_app_config(new_config)
        for observer in self._config_observers:
            await observer(new_config)

    async def reload_mcp(self) -> None:
        """重新从 mcp_server.json 加载 MCP 服务器。"""
        # 这里直接调用 bootstrap 中的逻辑
        from .bootstrap.runtime import _bootstrap_mcp
        await self.mcp_manager.stop_all()
        await _bootstrap_mcp(self)

    def _register_builtin_tools(self) -> None:
        """注册框架内建工具。"""
        self.tool_registry.register_tool(
            plugin_name="builtin",
            tool_name="view_skill",
            description="查看指定技能的详细指令和要求。在执行具体技能前必须先调用此工具了解详情。",
            parameters_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "技能名称"
                    }
                },
                "required": ["name"]
            },
            handler=self._view_skill_handler
        )

    async def _view_skill_handler(self, name: str) -> str:
        skill = self.skill_manager.get_skill(name)
        if not skill:
            return f"错误：未找到名为 {name!r} 的技能。"
        return skill.content or "该技能没有详细内容。"

    def register_schema(self, name: str, schema: ObjectSchema) -> None:
        self.runtime_registry.register_schema(name, schema)

    def bind_module(self, module: ModuleType) -> None:
        self.binder.bind_module(module)

    def build_execution_context(
        self,
        *,
        event_name: str = "",
        actor_id: str | None = None,
        platform: str | None = None,
        platform_instance_uuid: str | None = None,
        conversation_id: str | None = None,
        chat_id: str | None = None,
        group_id: str | None = None,
        channel_id: str | None = None,
        thread_id: str | None = None,
        message_id: str | None = None,
        scope: str = ScopeName.GLOBAL,
        roles: tuple[str, ...] = (),
        platform_roles: tuple[str, ...] = (),
        group_roles: tuple[str, ...] = (),
        is_authenticated: bool = False,
        metadata: dict[str, object] | None = None,
    ) -> ExecutionContext:
        return ExecutionContext(
            event_name=event_name,
            actor_id=actor_id,
            platform=platform,
            platform_instance_uuid=platform_instance_uuid,
            conversation_id=conversation_id,
            chat_id=chat_id,
            group_id=group_id,
            channel_id=channel_id,
            thread_id=thread_id,
            message_id=message_id,
            scope=scope,
            roles=roles,
            platform_roles=platform_roles,
            group_roles=group_roles,
            is_authenticated=is_authenticated,
            metadata=metadata or {},
        )

    def build_configuration_context(
        self,
        *,
        framework_config: dict[str, object] | None = None,
        plugin_configs: dict[str, dict[str, object]] | None = None,
        provider_configs: dict[str, dict[str, object]] | None = None,
        permission_config: dict[str, object] | None = None,
        moderation_config: dict[str, object] | None = None,
        conversation_config: dict[str, object] | None = None,
        plugin_bindings: dict[str, dict[str, object]] | None = None,
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

    async def build_conversation_context(
        self,
        execution: ExecutionContext,
        configuration: ConfigurationContext | None = None,
    ) -> ConversationContext:
        resolved = self.conversation_resolver.resolve_conversation_context(
            execution=execution,
            configuration=configuration,
        )
        return await self._hydrate_conversation_context(resolved)

    async def save_conversation_context(
        self, conversation: ConversationContext
    ) -> ConversationContext:
        return await self.conversation_store.save(conversation)

    async def review_input(
        self,
        *,
        text: str,
        execution: ExecutionContext,
        configuration: ConfigurationContext | None = None,
    ) -> ModerationDecision:
        return await self._review_text(
            stage=ModerationStage.INPUT,
            text=text,
            execution=execution,
            configuration=configuration,
        )

    async def review_output(
        self,
        *,
        text: str,
        execution: ExecutionContext,
        configuration: ConfigurationContext | None = None,
        conversation: ConversationContext | None = None,
    ) -> ModerationDecision:
        return await self._review_text(
            stage=ModerationStage.OUTPUT,
            text=text,
            execution=execution,
            configuration=configuration,
            conversation=conversation,
        )

    async def review_final_send(
        self,
        *,
        text: str,
        execution: ExecutionContext,
        configuration: ConfigurationContext | None = None,
        conversation: ConversationContext | None = None,
    ) -> ModerationDecision:
        return await self._review_text(
            stage=ModerationStage.FINAL_SEND,
            text=text,
            execution=execution,
            configuration=configuration,
            conversation=conversation,
        )

    async def build_provider_context(
        self,
        *,
        provider_name: str,
        execution: ExecutionContext,
        conversation: ConversationContext | None = None,
        model: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ProviderContext:
        conversation = conversation or await self.build_conversation_context(execution)
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

    async def _hydrate_conversation_context(
        self, resolved: ConversationContext
    ) -> ConversationContext:
        stored: ConversationContext | None = None
        if resolved.conversation_key is not None:
            stored = await self.conversation_store.get_conversation(
                resolved.conversation_key.value
            )
        elif resolved.session_key is not None:
            stored = await self.conversation_store.get_session(resolved.session_key.value)

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

    async def _review_text(
        self,
        *,
        stage: str,
        text: str,
        execution: ExecutionContext,
        configuration: ConfigurationContext | None = None,
        conversation: ConversationContext | None = None,
    ) -> ModerationDecision:
        configuration = configuration or self.build_configuration_context()
        conversation = conversation or await self.build_conversation_context(
            execution=execution,
            configuration=configuration,
        )
        preferred_backend = configuration.resolve_moderation_strategy()
        request = ModerationRequest(
            stage=stage,
            text=text,
            actor_id=execution.actor_id,
            platform=execution.platform,
            conversation_key=(
                conversation.conversation_key.value
                if conversation.conversation_key is not None
                else None
            ),
            metadata=execution.metadata.copy(),
        )
        return await self.moderation_service.review(
            request,
            preferred_backend=preferred_backend,
        )

    async def build_plugin_context(
        self,
        *,
        plugin_name: str,
        execution: ExecutionContext,
        configuration: ConfigurationContext | None = None,
        conversation: ConversationContext | None = None,
        **kwargs: object,
    ) -> PluginContext:
        configuration = configuration or self.build_configuration_context()
        conversation = conversation or await self.build_conversation_context(
            execution=execution,
            configuration=configuration,
        )
        binding_value = kwargs.pop("binding", None)
        if isinstance(binding_value, runtime_context.EffectivePluginBinding):
            binding = binding_value
        else:
            binding = self.build_effective_plugin_binding(
                plugin_name=plugin_name,
                configuration=configuration,
                execution=execution,
            )
        if not binding.enabled:
            raise ValueError(
                f"plugin is disabled for current configuration: {plugin_name}"
            )

        config_value = kwargs.pop("config", binding.config)
        config = (
            cast(runtime_context.ValueMap, config_value)
            if isinstance(config_value, dict)
            else binding.config
        )
        permission_engine_value = kwargs.get("permission_engine")
        permission_engine = (
            permission_engine_value
            if isinstance(permission_engine_value, PermissionEngine)
            else self.permission_engine  # 使用 framework 级别的默认引擎
        )
        reply_callable_value = kwargs.get("reply_callable")
        reply_callable = (
            cast(runtime_context.ReplyCallable, reply_callable_value)
            if callable(reply_callable_value)
            else None
        )
        send_voice_callable_value = kwargs.get("send_voice_callable")
        send_voice_callable = (
            cast(runtime_context.SendVoiceCallable, send_voice_callable_value)
            if callable(send_voice_callable_value)
            else None
        )
        task_callable_value = kwargs.get("task_callable")
        task_callable = (
            cast(runtime_context.TaskCallable, task_callable_value)
            if callable(task_callable_value)
            else None
        )
        permission_callable_value = kwargs.get("permission_callable")
        permission_callable = (
            cast(runtime_context.PermissionCallable, permission_callable_value)
            if callable(permission_callable_value)
            else None
        )
        resource_kind_value = kwargs.get("resource_kind")
        resource_kind = (
            resource_kind_value if isinstance(resource_kind_value, str) else "plugin"
        )
        provider_callable_value = kwargs.pop("provider_callable", None)
        provider_callable = (
            cast(runtime_context.ProviderCallable, provider_callable_value)
            if callable(provider_callable_value)
            else None
        )
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
            reply_callable=reply_callable or runtime_context.DEFAULT_REPLY_CALLABLE,
            send_voice_callable=send_voice_callable or runtime_context.DEFAULT_SEND_VOICE_CALLABLE,
            provider_callable=provider_callable,
            task_callable=task_callable or runtime_context.DEFAULT_TASK_CALLABLE,
            permission_callable=(
                permission_callable or runtime_context.DEFAULT_PERMISSION_CALLABLE
            ),
            save_conversation_callable=self.save_conversation_context,
            load_conversation_callable=self.conversation_store.get_conversation,
            permission_engine=permission_engine,
            resource_kind=resource_kind,
        )

    def build_effective_plugin_binding(
        self,
        *,
        plugin_name: str,
        configuration: ConfigurationContext,
        execution: ExecutionContext | None = None,
    ) -> runtime_context.EffectivePluginBinding:
        return runtime_context.build_effective_plugin_binding(
            plugin_name,
            configuration,
            execution,
        )

    def resolve_effective_plugin_bindings(
        self,
        configuration: ConfigurationContext,
        execution: ExecutionContext | None = None,
        plugin_names: list[str] | tuple[str, ...] | None = None,
    ) -> tuple[runtime_context.EffectivePluginBinding, ...]:
        names = plugin_names or tuple(sorted(self.runtime_registry.plugins.keys()))
        bindings: list[runtime_context.EffectivePluginBinding] = []
        for plugin_name in names:
            binding = self.build_effective_plugin_binding(
                plugin_name=plugin_name,
                configuration=configuration,
                execution=execution,
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
    ) -> runtime_context.ProviderCallable:
        async def call_provider(
            provider_name: str,
            request: ProviderRequest
            | EmbeddingRequest
            | TTSRequest
            | STTRequest
            | RerankRequest
            | None = None,
            model: str | None = None,
            **kwargs: object,
        ) -> object:
            return await self.invoke_provider(
                provider_name=provider_name,
                execution=execution,
                configuration=configuration,
                conversation=conversation,
                permission_engine=permission_engine,
                request=request,
                model=model,
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
        request: ProviderRequest
        | EmbeddingRequest
        | TTSRequest
        | STTRequest
        | RerankRequest
        | None = None,
        model: str | None = None,
        **kwargs: object,
    ) -> object:
        configuration = configuration or self.build_configuration_context()
        conversation = conversation or await self.build_conversation_context(
            execution=execution,
            configuration=configuration,
        )

        provider_config = configuration.get_provider_config(provider_name)
        if provider_config:
            await self.provider_registry.configure(provider_name, provider_config)

        metadata_value = kwargs.pop("metadata", None)
        provider_context = await self.build_provider_context(
            provider_name=provider_name,
            execution=execution,
            conversation=conversation,
            model=model,
            metadata=cast(dict[str, object] | None, metadata_value),
        )

        provider = await self.provider_registry.get(provider_name)
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

        if isinstance(provider, ChatProvider) and isinstance(request, ProviderRequest):
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
        **kwargs: object,
    ) -> ProviderRequest:
        prompt = kwargs.pop("prompt", None)
        system_prompt = kwargs.pop("system_prompt", None)
        messages_value = kwargs.pop("messages", [])
        tools_value = kwargs.pop("tools", [])
        image_urls_value = kwargs.pop("image_urls", [])
        stream_value = kwargs.pop("stream", False)
        messages = self._coerce_chat_messages(messages_value)
        tools = self._coerce_tool_definitions(tools_value)
        image_urls = [u for u in image_urls_value if isinstance(u, str)] if isinstance(image_urls_value, list) else []

        return ProviderRequest(
            model=model,
            prompt=prompt if isinstance(prompt, str) or prompt is None else None,
            system_prompt=(
                system_prompt
                if isinstance(system_prompt, str) or system_prompt is None
                else None
            ),
            messages=messages,
            image_urls=image_urls,
            tools=tools,
            stream=bool(stream_value),
            options={"provider_name": provider_name, **kwargs},
            context=provider_context,
        )

    def _coerce_chat_messages(self, value: object) -> list[ChatMessage]:
        if not isinstance(value, list):
            return []

        messages: list[ChatMessage] = []
        items = cast(list[object], value)
        for item in items:
            coerced = self._coerce_chat_message(item)
            if coerced is not None:
                messages.append(coerced)
        return messages

    def _coerce_chat_message(self, value: object) -> ChatMessage | None:
        if isinstance(value, ChatMessage):
            return value
        if not isinstance(value, dict):
            return None

        raw = cast(dict[object, object], value)
        role = raw.get("role")
        content = raw.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            return None

        name = raw.get("name")
        metadata = self._coerce_value_map(raw.get("metadata"))
        return ChatMessage(
            role=role,
            content=content,
            name=name if isinstance(name, str) else None,
            metadata=metadata,
        )

    def _coerce_tool_definitions(self, value: object) -> list[ToolDefinition]:
        if not isinstance(value, list):
            return []

        tools: list[ToolDefinition] = []
        items = cast(list[object], value)
        for item in items:
            coerced = self._coerce_tool_definition(item)
            if coerced is not None:
                tools.append(coerced)
        return tools

    def _coerce_tool_definition(self, value: object) -> ToolDefinition | None:
        if isinstance(value, ToolDefinition):
            return value
        if not isinstance(value, dict):
            return None

        raw = cast(dict[object, object], value)
        name = raw.get("name")
        if not isinstance(name, str):
            return None

        description = raw.get("description")
        parameters = self._coerce_value_map(raw.get("parameters"))
        metadata = self._coerce_value_map(raw.get("metadata"))
        return ToolDefinition(
            name=name,
            description=description if isinstance(description, str) else "",
            parameters=parameters,
            metadata=metadata,
        )

    def _coerce_value_map(self, value: object) -> ValueMap:
        if not isinstance(value, dict):
            return {}
        return {
            str(key): item
            for key, item in cast(dict[object, object], value).items()
            if isinstance(key, str)
        }


def create_framework(
    conversation_store: ConversationStore | None = None,
) -> NekoBotFramework:
    return NekoBotFramework(conversation_store=conversation_store)
