from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeAlias, cast

from ..conversations.context import ConfigurationContext, ConversationContext
from ..permissions import (
    AuthorizationContext,
    PermissionDecision,
    PermissionEngine,
    ResourceRef,
    Subject,
)
from ..permissions.constants import ScopeName

ValueMap: TypeAlias = dict[str, object]

ReplyCallable = Callable[[str], Awaitable[str | None]]  # returns message_id or None
RecallCallable = Callable[[str], Awaitable[None]]        # takes message_id
SendVoiceCallable = Callable[[bytes, str], Awaitable[str | None]]  # (audio_bytes, mime) -> message_id
ProviderCallable = Callable[..., Awaitable[object]]
TaskCallable = Callable[[str, ValueMap], Awaitable[object]]
PermissionCallable = Callable[[tuple[str, ...], bool], PermissionDecision]
SaveConversationCallable = Callable[[ConversationContext], Awaitable[ConversationContext]]
LoadConversationCallable = Callable[[str], Awaitable[ConversationContext | None]]


async def _noop_reply(message: str) -> str | None:
    _ = message
    return None


async def _noop_recall(message_id: str) -> None:
    _ = message_id
    return None


async def _noop_send_voice(audio_bytes: bytes, mime_type: str) -> str | None:
    _ = audio_bytes, mime_type
    return None


async def _missing_provider(*args: object, **kwargs: object) -> object:
    _ = args, kwargs
    raise RuntimeError("provider access is not configured for this context")


async def _missing_task(name: str, payload: ValueMap) -> object:
    _ = name, payload
    raise RuntimeError("task scheduling is not configured for this context")


def _allow_all_permissions(
    permissions: tuple[str, ...], require_all: bool
) -> PermissionDecision:
    _ = permissions, require_all
    return PermissionDecision(allowed=True, reason="default allow")


async def _noop_save_conversation(context: ConversationContext) -> ConversationContext:
    return context


async def _noop_load_conversation(key: str) -> ConversationContext | None:
    _ = key
    return None


DEFAULT_REPLY_CALLABLE: ReplyCallable = _noop_reply
DEFAULT_RECALL_CALLABLE: RecallCallable = _noop_recall
DEFAULT_SEND_VOICE_CALLABLE: SendVoiceCallable = _noop_send_voice
DEFAULT_PROVIDER_CALLABLE: ProviderCallable = _missing_provider
DEFAULT_TASK_CALLABLE: TaskCallable = _missing_task
DEFAULT_PERMISSION_CALLABLE: PermissionCallable = _allow_all_permissions
DEFAULT_SAVE_CONVERSATION_CALLABLE: SaveConversationCallable = _noop_save_conversation
DEFAULT_LOAD_CONVERSATION_CALLABLE: LoadConversationCallable = _noop_load_conversation


@dataclass(slots=True)
class ExecutionContext:
    event_name: str = ""
    actor_id: str | None = None
    platform: str | None = None
    platform_instance_uuid: str | None = None
    conversation_id: str | None = None
    chat_id: str | None = None
    group_id: str | None = None
    channel_id: str | None = None
    thread_id: str | None = None
    message_id: str | None = None
    scope: str = ScopeName.GLOBAL
    roles: tuple[str, ...] = ()
    platform_roles: tuple[str, ...] = ()
    group_roles: tuple[str, ...] = ()
    is_authenticated: bool = False
    metadata: ValueMap = field(default_factory=dict)

    def to_authorization_context(
        self, resource_kind: str, resource_name: str
    ) -> AuthorizationContext:
        return AuthorizationContext(
            subject=Subject(
                actor_id=self.actor_id,
                roles=self.roles,
                platform_roles=self.platform_roles,
                group_roles=self.group_roles,
                is_authenticated=self.is_authenticated,
            ),
            resource=ResourceRef(kind=resource_kind, name=resource_name),
            scope=self.scope,
            platform=self.platform,
            conversation_id=self.conversation_id,
            group_id=self.group_id,
            channel_id=self.channel_id,
            metadata=self.metadata.copy(),
        )


@dataclass(slots=True)
class PluginContext:
    plugin_name: str
    config: ValueMap = field(default_factory=dict)
    execution: ExecutionContext = field(default_factory=ExecutionContext)
    configuration: ConfigurationContext = field(default_factory=ConfigurationContext)
    conversation: ConversationContext | None = None
    reply_callable: ReplyCallable = DEFAULT_REPLY_CALLABLE
    recall_callable: RecallCallable = DEFAULT_RECALL_CALLABLE
    send_voice_callable: SendVoiceCallable = DEFAULT_SEND_VOICE_CALLABLE
    provider_callable: ProviderCallable = DEFAULT_PROVIDER_CALLABLE
    task_callable: TaskCallable = DEFAULT_TASK_CALLABLE
    permission_callable: PermissionCallable = DEFAULT_PERMISSION_CALLABLE
    save_conversation_callable: SaveConversationCallable = (
        DEFAULT_SAVE_CONVERSATION_CALLABLE
    )
    load_conversation_callable: LoadConversationCallable = (
        DEFAULT_LOAD_CONVERSATION_CALLABLE
    )
    permission_engine: PermissionEngine | None = None
    resource_kind: str = "plugin"

    def __post_init__(self) -> None:
        if not self.config:
            self.config = self.configuration.get_plugin_config(self.plugin_name)

    async def reply(self, message: str) -> str | None:
        return await self.reply_callable(message)

    async def recall(self, message_id: str) -> None:
        await self.recall_callable(message_id)

    async def send_voice(self, audio_bytes: bytes, mime_type: str = "audio/mpeg") -> str | None:
        """发送语音消息，audio_bytes 为音频二进制，返回 message_id 或 None。"""
        return await self.send_voice_callable(audio_bytes, mime_type)

    async def tts(
        self, text: str, *, provider_name: str, voice: str | None = None, model: str | None = None
    ) -> bytes | None:
        """调用 TTS provider 合成语音，返回音频二进制（mp3）。失败返回 None。"""
        from ..providers.types import TTSRequest, TTSResponse
        try:
            result = await self.provider_callable(
                provider_name=provider_name,
                request=TTSRequest(text=text, voice=voice, model=model),
            )
            if isinstance(result, TTSResponse):
                if result.error:
                    return None
                return result.audio_bytes or None
        except Exception:
            return None
        return None

    async def stt(
        self, audio_bytes: bytes, mime_type: str = "audio/mpeg", *, provider_name: str, model: str | None = None
    ) -> str | None:
        """调用 STT provider 转写语音，返回文字。失败返回 None。"""
        from ..providers.types import STTRequest, STTResponse
        try:
            result = await self.provider_callable(
                provider_name=provider_name,
                request=STTRequest(audio_bytes=audio_bytes, mime_type=mime_type, model=model),
            )
            if isinstance(result, STTResponse):
                if result.error:
                    return None
                return result.text or None
        except Exception:
            return None
        return None

    async def save_conversation(self, context: ConversationContext) -> ConversationContext:
        return await self.save_conversation_callable(context)

    async def load_conversation(self, key: str) -> ConversationContext | None:
        return await self.load_conversation_callable(key)

    async def request_provider(self, provider_name: str, **kwargs: object) -> object:
        return await self.provider_callable(provider_name=provider_name, **kwargs)

    async def schedule_task(self, task_name: str, payload: ValueMap) -> object:
        return await self.task_callable(task_name, payload)

    def get_config(self, key: str, default: object = None) -> object:
        return self.config.get(key, default)

    def permission_decision(
        self, *permissions: str, require_all: bool = True
    ) -> PermissionDecision:
        if self.permission_engine is not None:
            auth_context = self.execution.to_authorization_context(
                resource_kind=self.resource_kind,
                resource_name=self.plugin_name,
            )
            return self.permission_engine.evaluate(
                tuple(permissions),
                auth_context,
                require_all=require_all,
            )
        return self.permission_callable(tuple(permissions), require_all)

    def check_permissions(self, *permissions: str, require_all: bool = True) -> bool:
        return self.permission_decision(*permissions, require_all=require_all).allowed


@dataclass(frozen=True)
class EffectivePluginBinding:
    plugin_name: str
    enabled: bool
    config: ValueMap = field(default_factory=dict)
    metadata: ValueMap = field(default_factory=dict)


def build_effective_plugin_binding(
    plugin_name: str,
    configuration: ConfigurationContext,
    execution: ExecutionContext | None = None,
) -> EffectivePluginBinding:
    base_config = configuration.get_plugin_config(plugin_name)
    binding = configuration.get_plugin_binding(plugin_name)
    override_config = binding.get("config", {})
    merged_config = dict(base_config)
    if isinstance(override_config, dict):
        override_map = cast(dict[str, object], override_config)
        merged_config.update(override_map)
    enabled = configuration.is_plugin_enabled(plugin_name, execution=execution)
    binding_map = cast(dict[object, object], binding)
    metadata = {
        str(key): value
        for key, value in binding_map.items()
        if isinstance(key, str) and key not in {"enabled", "config"}
    }
    return EffectivePluginBinding(
        plugin_name=plugin_name,
        enabled=enabled,
        config=merged_config,
        metadata=metadata,
    )
