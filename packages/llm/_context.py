"""_ContextMixin: message building, system prompt, persona resolution."""

from __future__ import annotations

from datetime import datetime

from loguru import logger

from ._types import (
    _PREF_PERSONA,
    _Ctx,
)


class _ContextMixin:
    def _build_messages(
        self,
        ctx: _Ctx,
        user_text: str,
        *,
        sender_info: dict[str, str | None] | None = None,
    ) -> tuple[list[dict[str, object]], str]:
        history_limit = self._get_config_int(ctx, "history_limit", 20)  # type: ignore[attr-defined]
        messages: list[dict[str, object]] = []

        # 不再向 messages 注入 role: system。改为生成 extra_context 字符串。
        extra_parts: list[str] = []

        if ctx.conversation.summary:
            extra_parts.append(f"[对话历史摘要]\n{ctx.conversation.summary}")

        history = ctx.conversation.history
        cutoff = max(0, len(history) - history_limit * 2)
        for entry in history[cutoff:]:
            role = entry.get("role")
            content = entry.get("content")
            if isinstance(role, str) and isinstance(content, str):
                messages.append({"role": role, "content": content})

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ctx_parts = [f"当前时间：{now}"]
        if sender_info:
            uid = sender_info.get("uid")
            name = sender_info.get("name")
            role = sender_info.get("role")
            level = sender_info.get("level")
            title = sender_info.get("title")
            if name:
                ctx_parts.append(f"用户名：{name}")
            if uid:
                ctx_parts.append(f"UID：{uid}")
            if role:
                ctx_parts.append(f"身份：{role}")
            if level:
                ctx_parts.append(f"等级：{level}")
            if title:
                ctx_parts.append(f"头衔：{title}")
        extra_parts.append("[当前环境数据] " + "、".join(ctx_parts))

        # 如果用户引用了一条消息，注入引用内容供 LLM 参考
        quoted_text = ctx.payload.get("quoted_text")
        if isinstance(quoted_text, str) and quoted_text.strip():
            extra_parts.append(f"[引用消息]\n{quoted_text.strip()}")

        # 注入技能发现列表
        skills = self.framework.skill_manager.skill_descriptions  # type: ignore[attr-defined]
        if skills:
            skill_lines = [f"- {s['name']}: {s['description']}" for s in skills]
            suffix = "\n(如需执行上述技能，请先调用 view_skill 工具查看详细指令)"
            extra_parts.append("[可用技能列表]\n" + "\n".join(skill_lines) + suffix)

        messages.append({"role": "user", "content": user_text})
        return messages, "\n\n".join(extra_parts)

    async def _get_system_prompt(self, ctx: _Ctx, extra_context: str = "") -> str:
        persona_text = await self._resolve_persona(ctx)  # type: ignore[attr-defined]
        if not persona_text:
            # 向后兼容：直接配置的 system_prompt
            raw = ctx.config.get("system_prompt")
            persona_text = (
                raw if isinstance(raw, str) and raw.strip()
                else "你是 NekoBot，一个由 Neko 开发的智能机器人。"
            )

        if extra_context:
            return f"{persona_text}\n\n{extra_context}"
        return persona_text  # type: ignore[return-value]

    async def _get_personas(self, ctx: _Ctx) -> dict[str, str]:
        """合并从 config 和 DB 读取的人设，返回 {name: prompt}。"""
        # 1. 从 config 读取 (向后兼容)
        res: dict[str, str] = {}
        raw = ctx.config.get("personas")
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(k, str) and isinstance(v, str):
                    res[k] = v

        # 2. 从 DB 读取 (动态管理)
        try:
            db_personas = await self.framework.conversation_store.list_personas()  # type: ignore[attr-defined]
            res.update(db_personas)
        except Exception as exc:
            logger.warning("llm: failed to fetch personas from DB: {}", exc)

        return res

    async def _resolve_persona(self, ctx: _Ctx) -> str | None:
        """解析当前生效的人设文本。优先级：per-conversation > per-group > default_persona。"""
        personas = await self._get_personas(ctx)
        if not personas:
            return None

        # 1. per-conversation 偏好
        pref = ctx.conversation.provider_preferences.get(_PREF_PERSONA)
        if isinstance(pref, str) and pref in personas:
            return personas[pref]

        # 2. per-group 设置
        if ctx.execution.group_id is not None:
            gs = await self._load_group_settings(ctx)  # type: ignore[attr-defined]
            group_pref = gs.provider_preferences.get(_PREF_PERSONA)
            if isinstance(group_pref, str) and group_pref in personas:
                return personas[group_pref]

        # 3. config default_persona
        default = ctx.config.get("default_persona")
        if isinstance(default, str) and default in personas:
            return personas[default]

        return None

    async def _get_active_persona_name(self, ctx: _Ctx) -> str | None:
        """返回当前生效的人设名称，用于状态显示。"""
        personas = await self._get_personas(ctx)
        if not personas:
            return None

        pref = ctx.conversation.provider_preferences.get(_PREF_PERSONA)
        if isinstance(pref, str) and pref in personas:
            return pref

        if ctx.execution.group_id is not None:
            gs = await self._load_group_settings(ctx)  # type: ignore[attr-defined]
            group_pref = gs.provider_preferences.get(_PREF_PERSONA)
            if isinstance(group_pref, str) and group_pref in personas:
                return f"{group_pref}(群默认)"

        default = ctx.config.get("default_persona")
        if isinstance(default, str) and default in personas:
            return f"{default}(全局默认)"

        return None

    def _extract_sender_info(self, ctx: _Ctx) -> dict[str, str | None]:
        sender = ctx.payload.get("sender")
        if not isinstance(sender, dict):
            return {}

        def _s(key: str) -> str | None:
            v = sender.get(key)
            return str(v) if v is not None and str(v).strip() else None

        name = _s("card") or _s("nickname")
        uid = _s("user_id") or ctx.execution.actor_id

        _ROLE_LABELS = {"owner": "群主", "admin": "管理员", "member": "成员"}
        raw_role = _s("role")
        role = _ROLE_LABELS.get(raw_role, raw_role) if raw_role else None

        return {
            "uid": uid,
            "name": name,
            "role": role,
            "level": _s("level"),
            "title": _s("title"),
        }
