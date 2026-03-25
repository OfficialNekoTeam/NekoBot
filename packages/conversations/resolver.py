from __future__ import annotations

from typing import TYPE_CHECKING

from ..permissions.constants import ScopeName
from .context import ConfigurationContext, ConversationContext
from .models import ConversationKey, IsolationMode, ScopeRoute, SessionKey

if TYPE_CHECKING:
    from ..runtime.context import ExecutionContext


class ConversationResolver:
    def _base_segments(self, route: ScopeRoute) -> list[str]:
        segments = [route.platform_type, route.platform_instance_uuid, route.scope]
        if route.thread_id:
            segments.extend(("thread", route.thread_id))
        return segments

    def _chat_identity(
        self, route: ScopeRoute, execution: ExecutionContext
    ) -> str | None:
        return route.chat_id or execution.group_id or execution.channel_id

    def resolve_route(self, execution: ExecutionContext) -> ScopeRoute:
        platform_type = execution.platform or "unknown"
        instance_uuid = execution.platform_instance_uuid or "default"
        return ScopeRoute(
            platform_type=platform_type,
            platform_instance_uuid=instance_uuid,
            scope=execution.scope,
            chat_id=execution.chat_id,
            actor_id=execution.actor_id,
            thread_id=execution.thread_id,
            metadata=execution.metadata.copy(),
        )

    def resolve_conversation_context(
        self,
        execution: ExecutionContext,
        configuration: ConfigurationContext | None = None,
    ) -> ConversationContext:
        configuration = configuration or ConfigurationContext()
        route = self.resolve_route(execution)
        isolation_mode = configuration.isolation_mode
        conversation_key = self._resolve_conversation_key(
            route, execution, isolation_mode
        )
        session_key = self._resolve_session_key(route, execution, isolation_mode)
        return ConversationContext(
            isolation_mode=isolation_mode,
            conversation_key=conversation_key,
            session_key=session_key,
            conversation_id=execution.conversation_id,
            scope=execution.scope,
            platform_type=route.platform_type,
            platform_instance_uuid=route.platform_instance_uuid,
            chat_id=route.chat_id,
            actor_id=route.actor_id,
            thread_id=route.thread_id,
            metadata=execution.metadata.copy(),
        )

    def _resolve_conversation_key(
        self,
        route: ScopeRoute,
        execution: ExecutionContext,
        isolation_mode: str,
    ) -> ConversationKey | None:
        if execution.conversation_id:
            return ConversationKey(
                ":".join(
                    (
                        route.platform_type,
                        route.platform_instance_uuid,
                        "conversation",
                        execution.conversation_id,
                    )
                )
            )

        base = self._base_segments(route)

        if route.scope == ScopeName.PRIVATE:
            identity = route.actor_id or route.chat_id
            if identity is None:
                return None
            return ConversationKey(":".join((*base, identity)))

        if route.scope in (ScopeName.GROUP, ScopeName.CONVERSATION):
            chat_id = self._chat_identity(route, execution)
            if chat_id is None:
                return None

            if isolation_mode == IsolationMode.PER_USER:
                actor_id = route.actor_id
                if actor_id is None:
                    return ConversationKey(":".join((*base, chat_id)))
                return ConversationKey(":".join((*base, chat_id, "user", actor_id)))

            if isolation_mode == IsolationMode.SHARED_GROUP:
                return ConversationKey(":".join((*base, chat_id)))

            if isolation_mode == IsolationMode.HYBRID:
                share_group = bool(execution.metadata.get("shared_conversation"))
                if share_group:
                    return ConversationKey(":".join((*base, chat_id)))
                actor_id = route.actor_id
                if actor_id is None:
                    return ConversationKey(":".join((*base, chat_id)))
                return ConversationKey(":".join((*base, chat_id, "user", actor_id)))

            actor_id = route.actor_id
            if actor_id is None:
                return ConversationKey(":".join((*base, chat_id)))
            return ConversationKey(":".join((*base, chat_id, "user", actor_id)))

        if route.scope == ScopeName.PLATFORM:
            return ConversationKey(":".join(base))

        identity = route.chat_id or route.actor_id
        if identity is None:
            return ConversationKey(":".join(base))
        return ConversationKey(":".join((*base, identity)))

    def _resolve_session_key(
        self,
        route: ScopeRoute,
        execution: ExecutionContext,
        isolation_mode: str,
    ) -> SessionKey | None:
        conversation_key = self._resolve_conversation_key(
            route, execution, isolation_mode
        )
        if conversation_key is None:
            return None
        return SessionKey(conversation_key.value)
