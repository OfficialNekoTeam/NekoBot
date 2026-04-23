"""_CommandsMixin: all /cmd_* command handlers for the LLM handler."""

from __future__ import annotations

import aiohttp
from loguru import logger

from ..utils.url_guard import is_safe_url
from ._types import (
    _PREF_BLACKLIST,
    _PREF_ENABLED,
    _PREF_GROUP_ENABLED,
    _PREF_MODEL,
    _PREF_PERSONA,
    _PREF_PROVIDER,
    _PREF_WHITELIST,
    _Ctx,
)


class _CommandsMixin:
    async def _cmd_help(self, ctx: _Ctx) -> None:
        p = self._get_command_prefix(ctx)  # type: ignore[attr-defined]
        is_group = ctx.execution.scope == "group"

        try:
            from importlib.metadata import version as _pkg_version
            _ver = _pkg_version("nekobot")
        except Exception:
            _ver = "dev"

        lines = [
            f"NekoBot v{_ver}",
            "",
            f"{p}help          - 显示此帮助",
            f"{p}sid           - 显示当前会话 ID",
            f"{p}reset         - 清空对话历史",
            f"{p}llm           - 查看 LLM 状态",
            f"{p}llm on|off    - 开启/关闭自动回复",
            f"{p}llm model [ls|<名称>]   - 查看/切换模型",
            f"{p}llm provider <名称>     - 切换 Provider",
            f"{p}llm compress  - 压缩对话历史",
            f"{p}llm reset     - 恢复默认模型和 Provider",
            f"{p}llm persona list|set <名称>|reset|info",
        ]
        if is_group:
            lines += [
                f"{p}llm group on|off - 开启/关闭本群回复",
                f"{p}llm blacklist add|rm|clr|ls <qq>",
                f"{p}llm whitelist add|rm|clr|ls <qq>",
                f"{p}llm persona group set <名称>|reset",
            ]

        # 自动聚合已注册插件的命令
        plugin_lines: list[str] = []
        for registered in self.framework.runtime_registry.plugins.values():  # type: ignore[attr-defined]
            if not registered.commands:
                continue
            plugin_lines.append(f"\n[{registered.spec.name}]")
            for _, cmd_spec in registered.commands:
                aliases = f" ({', '.join(cmd_spec.aliases)})" if cmd_spec.aliases else ""
                desc = f" - {cmd_spec.description}" if cmd_spec.description else ""
                plugin_lines.append(f"{p}{cmd_spec.name}{aliases}{desc}")

        if plugin_lines:
            lines.append("\n--- 插件命令 ---")
            lines.extend(plugin_lines)

        await ctx.reply("\n".join(lines))

    async def _cmd_sid(self, ctx: _Ctx) -> None:
        key = ctx.conversation.conversation_key
        sid = key.value if key is not None else "(无)"
        await ctx.reply(f"[SID] {sid}")

    async def _cmd_reset(self, ctx: _Ctx) -> None:
        from dataclasses import replace
        cleared = replace(ctx.conversation, history=[], summary=None)
        ctx.conversation = await self.framework.save_conversation_context(cleared)  # type: ignore[attr-defined]
        logger.info("llm: conversation reset for key={}", ctx.conversation.conversation_key)
        await ctx.reply("[OK] 对话历史已清空。")

    async def _cmd_llm(self, ctx: _Ctx, parts: list[str]) -> None:
        """parts 是去掉命令名后的参数列表，例如 ["group", "on"]。"""
        _ALIASES: dict[str, str] = {
            "cmp": "compress",
        }
        sub = _ALIASES.get(parts[0].lower(), parts[0].lower()) if parts else "status"

        _ADMIN_SUBS = {
            "on", "off", "model", "provider", "reset", "clearmodel",
            "compress", "summarize", "group", "blacklist", "whitelist",
            "persona",
        }
        if sub in _ADMIN_SUBS and not self._check_permission(ctx.execution, "command.invoke"):  # type: ignore[attr-defined]
            await ctx.reply("[ERR] 权限不足。")
            return

        prefs: dict[str, object] = dict(ctx.conversation.provider_preferences)

        if sub == "off":
            prefs[_PREF_ENABLED] = False
            ctx.conversation = await self._save_prefs(ctx, prefs)  # type: ignore[attr-defined]
            await ctx.reply("[OFF] 已关闭自动回复，发送 /llm on 可重新开启。")

        elif sub == "on":
            prefs[_PREF_ENABLED] = True
            ctx.conversation = await self._save_prefs(ctx, prefs)  # type: ignore[attr-defined]
            await ctx.reply("[ON] 已开启自动回复。")

        elif sub == "model":
            arg = parts[1].lower() if len(parts) > 1 else "ls"
            if arg in ("ls", "list"):
                await self._cmd_model_list(ctx)
            else:
                prefs[_PREF_MODEL] = parts[1]
                ctx.conversation = await self._save_prefs(ctx, prefs)  # type: ignore[attr-defined]
                await ctx.reply(f"[OK] 模型已切换为：{parts[1]}")

        elif sub == "provider" and len(parts) > 1:
            prefs[_PREF_PROVIDER] = parts[1]
            ctx.conversation = await self._save_prefs(ctx, prefs)  # type: ignore[attr-defined]
            await ctx.reply(f"[OK] Provider 已切换为：{parts[1]}")

        elif sub in ("reset", "clearmodel"):
            prefs.pop(_PREF_MODEL, None)
            prefs.pop(_PREF_PROVIDER, None)
            ctx.conversation = await self._save_prefs(ctx, prefs)  # type: ignore[attr-defined]
            await ctx.reply("[OK] 已恢复默认模型和 Provider。")

        elif sub in ("compress", "summarize"):
            await self._do_compress(ctx)  # type: ignore[attr-defined]

        elif sub == "group" and len(parts) > 1:
            await self._cmd_llm_group(ctx, parts[1].lower())

        elif sub == "blacklist":
            await self._cmd_list_manage(ctx, _PREF_BLACKLIST, parts)

        elif sub == "whitelist":
            await self._cmd_list_manage(ctx, _PREF_WHITELIST, parts)

        elif sub == "persona":
            await self._cmd_persona(ctx, parts[1:])

        else:
            await self._cmd_status(ctx, prefs)

    async def _cmd_status(self, ctx: _Ctx, prefs: dict[str, object]) -> None:
        enabled = prefs.get(_PREF_ENABLED, True)
        model = prefs.get(_PREF_MODEL) or "默认"
        provider = (
            prefs.get(_PREF_PROVIDER)
            or ctx.configuration.resolve_provider_name()
            or "未配置"
        )
        turns = len(ctx.conversation.history) // 2
        has_summary = bool(ctx.conversation.summary)
        is_group = ctx.execution.scope == "group"
        group_line = bl_line = wl_line = ""
        if is_group:
            group_enabled = await self._is_group_reply_enabled(ctx)  # type: ignore[attr-defined]
            gs = await self._load_group_settings(ctx)  # type: ignore[attr-defined]
            bl = gs.provider_preferences.get(_PREF_BLACKLIST, [])
            wl = gs.provider_preferences.get(_PREF_WHITELIST, [])
            group_line = f"群回复: {'开启' if group_enabled else '关闭'}\n"
            bl_line = f"黑名单: {', '.join(str(u) for u in bl) or '(空)'}\n"  # type: ignore[union-attr]
            wl_line = f"白名单: {', '.join(str(u) for u in wl) or '(空)'}\n"  # type: ignore[union-attr]
        persona_name = await self._get_active_persona_name(ctx)  # type: ignore[attr-defined]
        persona_line = f"人设: {persona_name}\n" if persona_name else ""
        cmd_prefix = self._get_command_prefix(ctx)  # type: ignore[attr-defined]
        await ctx.reply(
            f"[LLM 状态]\n"
            f"自动回复: {'开启' if enabled else '关闭'}\n"
            f"{group_line}{bl_line}{wl_line}"
            f"Provider: {provider}\n"
            f"模型: {model}\n"
            f"{persona_line}"
            f"历史轮数: {turns}\n"
            f"有摘要: {'是' if has_summary else '否'}\n\n"
            f"{cmd_prefix}llm on|off\n"
            f"{cmd_prefix}llm group on|off\n"
            f"{cmd_prefix}llm blacklist/whitelist add|remove|clear|list <qq>\n"
            f"{cmd_prefix}llm model <名称> | {cmd_prefix}llm provider <名称>\n"
            f"{cmd_prefix}llm persona list|set <名称>|reset\n"
            f"{cmd_prefix}llm compress | {cmd_prefix}reset"
        )

    async def _cmd_persona(self, ctx: _Ctx, args: list[str]) -> None:
        """人设管理命令。子命令：list / set <名称> / reset / info / group set|reset。"""
        personas = await self._get_personas(ctx)  # type: ignore[attr-defined]
        sub = args[0].lower() if args else "info"
        is_group = ctx.execution.scope == "group"

        if sub == "list":
            if not personas:
                await ctx.reply("[人设] 未配置任何人设（在 llm_chat.personas 中添加）。")
                return
            active = await self._get_active_persona_name(ctx)  # type: ignore[attr-defined]
            lines = ["[人设列表]"]
            for name, prompt in personas.items():
                marker = " ✓" if active and active.startswith(name) else ""
                preview = prompt[:40].replace("\n", " ")
                lines.append(f"  {name}{marker}: {preview}{'...' if len(prompt) > 40 else ''}")
            await ctx.reply("\n".join(lines))

        elif sub == "set" and len(args) > 1:
            name = args[1]
            if name not in personas:
                await ctx.reply(f"[ERR] 人设 {name!r} 不存在。可用: {', '.join(personas)}")
                return
            prefs = dict(ctx.conversation.provider_preferences)
            prefs[_PREF_PERSONA] = name
            ctx.conversation = await self._save_prefs(ctx, prefs)  # type: ignore[attr-defined]
            await ctx.reply(f"[OK] 人设已切换为：{name}")

        elif sub == "reset":
            prefs = dict(ctx.conversation.provider_preferences)
            prefs.pop(_PREF_PERSONA, None)
            ctx.conversation = await self._save_prefs(ctx, prefs)  # type: ignore[attr-defined]
            # 若在群聊，也同时清除群默认
            if is_group:
                gs = await self._load_group_settings(ctx)  # type: ignore[attr-defined]
                gp = dict(gs.provider_preferences)
                gp.pop(_PREF_PERSONA, None)
                await self._save_group_settings(ctx, gs, gp)  # type: ignore[attr-defined]
            await ctx.reply("[OK] 已恢复默认人设。")

        elif sub == "info":
            active_name = await self._get_active_persona_name(ctx)  # type: ignore[attr-defined]
            active_text = await self._resolve_persona(ctx)  # type: ignore[attr-defined]
            if not active_name:
                # 可能用的是旧式 system_prompt
                raw = ctx.config.get("system_prompt")
                if isinstance(raw, str) and raw.strip():
                    preview = raw[:120].replace("\n", " ")
                    await ctx.reply(f"[人设] 使用旧式 system_prompt:\n{preview}{'...' if len(raw) > 120 else ''}")
                else:
                    await ctx.reply("[人设] 未配置人设。")
                return
            preview = (active_text or "")[:120].replace("\n", " ")
            await ctx.reply(
                f"[人设] 当前: {active_name}\n"
                f"{preview}{'...' if active_text and len(active_text) > 120 else ''}"
            )

        elif sub == "group" and is_group:
            # /llm persona group set <名称> | group reset
            g_action = args[1].lower() if len(args) > 1 else ""
            if g_action == "set" and len(args) > 2:
                name = args[2]
                if name not in personas:
                    await ctx.reply(f"[ERR] 人设 {name!r} 不存在。可用: {', '.join(personas)}")
                    return
                gs = await self._load_group_settings(ctx)  # type: ignore[attr-defined]
                gp = dict(gs.provider_preferences)
                gp[_PREF_PERSONA] = name
                await self._save_group_settings(ctx, gs, gp)  # type: ignore[attr-defined]
                await ctx.reply(f"[OK] 本群默认人设已设为：{name}")
            elif g_action == "reset":
                gs = await self._load_group_settings(ctx)  # type: ignore[attr-defined]
                gp = dict(gs.provider_preferences)
                gp.pop(_PREF_PERSONA, None)
                await self._save_group_settings(ctx, gs, gp)  # type: ignore[attr-defined]
                await ctx.reply("[OK] 本群默认人设已重置。")
            else:
                await ctx.reply("用法：/llm persona group set <名称> | group reset")

        else:
            p = self._get_command_prefix(ctx)  # type: ignore[attr-defined]
            lines = [
                f"{p}llm persona list          - 列出所有人设",
                f"{p}llm persona set <名称>    - 切换人设（当前会话）",
                f"{p}llm persona reset         - 恢复默认人设",
                f"{p}llm persona info          - 查看当前人设",
            ]
            if is_group:
                lines += [
                    f"{p}llm persona group set <名称>  - 设置本群默认人设",
                    f"{p}llm persona group reset       - 重置本群默认人设",
                ]
            await ctx.reply("\n".join(lines))

    async def _cmd_list_manage(
        self, ctx: _Ctx, pref_key: str, parts: list[str]
    ) -> None:
        label = "黑名单" if pref_key == _PREF_BLACKLIST else "白名单"
        if ctx.execution.group_id is None:
            await ctx.reply("此命令仅在群聊中有效。")
            return
        # parts = ["blacklist"|"whitelist", action?, target?]
        _ACT_ALIASES: dict[str, str] = {"ls": "list", "rm": "remove", "clr": "clear", "del": "remove"}
        raw_action = parts[1].lower() if len(parts) > 1 else "list"
        action = _ACT_ALIASES.get(raw_action, raw_action)
        gs = await self._load_group_settings(ctx)  # type: ignore[attr-defined]
        prefs = dict(gs.provider_preferences)
        current: list[str] = list(prefs.get(pref_key, []))  # type: ignore[arg-type]

        if action == "list":
            await ctx.reply(f"[{label}] {', '.join(current) if current else '(空)'}")
            return
        if action == "clear":
            prefs[pref_key] = []
            await self._save_group_settings(ctx, gs, prefs)  # type: ignore[attr-defined]
            await ctx.reply(f"[OK] 已清空{label}。")
            return
        if len(parts) < 3:
            cmd = "blacklist" if pref_key == _PREF_BLACKLIST else "whitelist"
            await ctx.reply(f"用法：/llm {cmd} add/remove/clear/list <qq>")
            return

        target_id = str(parts[2])
        if action == "add":
            if target_id not in current:
                current.append(target_id)
            prefs[pref_key] = current
            await self._save_group_settings(ctx, gs, prefs)  # type: ignore[attr-defined]
            await ctx.reply(f"[OK] 已将 {target_id} 加入{label}。")
        elif action == "remove":
            if target_id in current:
                current.remove(target_id)
                prefs[pref_key] = current
                await self._save_group_settings(ctx, gs, prefs)  # type: ignore[attr-defined]
                await ctx.reply(f"[OK] 已将 {target_id} 移出{label}。")
            else:
                await ctx.reply(f"[ERR] {target_id} 不在{label}中。")
        else:
            await ctx.reply(f"未知操作：{action}")

    async def _cmd_llm_group(self, ctx: _Ctx, action: str) -> None:
        if ctx.execution.group_id is None:
            await ctx.reply("此命令仅在群聊中有效。")
            return
        gs = await self._load_group_settings(ctx)  # type: ignore[attr-defined]
        prefs = dict(gs.provider_preferences)
        if action == "off":
            prefs[_PREF_GROUP_ENABLED] = False
            await self._save_group_settings(ctx, gs, prefs)  # type: ignore[attr-defined]
            await ctx.reply("[OFF] 已关闭本群自动回复。")
        elif action == "on":
            prefs[_PREF_GROUP_ENABLED] = True
            await self._save_group_settings(ctx, gs, prefs)  # type: ignore[attr-defined]
            await ctx.reply("[ON] 已开启本群自动回复。")
        else:
            await ctx.reply("用法：/llm group on|off")

    async def _cmd_model_list(self, ctx: _Ctx) -> None:
        """列出当前 Provider 支持的模型。"""
        provider_name = self._resolve_provider_name(ctx)  # type: ignore[attr-defined]
        if provider_name is None:
            await ctx.reply("[ERR] 未配置 Provider。")
            return

        # 先尝试从 provider_info 静态列表获取
        try:
            provider = await self.framework.provider_registry.get(provider_name)  # type: ignore[attr-defined]
            info = provider.provider_info()
            if info.models:
                lines = "\n".join(f"  {m.id}" for m in info.models)
                await ctx.reply(f"[模型列表] {provider_name}\n{lines}")
                return
        except Exception as exc:
            logger.warning("llm: failed to get provider info: {}", exc)

        # 静态列表为空，尝试动态查询 /v1/models（OpenAI-compatible）
        provider_cfg = ctx.configuration.get_provider_config(provider_name)
        base_url = provider_cfg.get("base_url")
        api_key = provider_cfg.get("api_key")
        if not isinstance(base_url, str) or not isinstance(api_key, str):
            await ctx.reply(f"[ERR] {provider_name} 未提供模型列表，且无法动态查询。")
            return

        url = base_url.rstrip("/") + "/models"
        if not is_safe_url(url):
            await ctx.reply(f"[ERR] {provider_name} 的 base_url 指向内网地址，已拒绝请求。")
            return
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        await ctx.reply(f"[ERR:api_status_{resp.status}] 获取模型列表失败。")
                        return
                    data = await resp.json()
            models = sorted(
                item.get("id", "") for item in data.get("data", []) if item.get("id")
            )
            if not models:
                await ctx.reply("[ERR] 返回的模型列表为空。")
                return
            lines = "\n".join(f"  {m}" for m in models[:50])
            suffix = f"\n  ...共 {len(models)} 个" if len(models) > 50 else ""
            await ctx.reply(f"[模型列表] {provider_name}\n{lines}{suffix}")
        except Exception as exc:
            logger.error("llm: model list fetch failed: {}", exc)
            await ctx.reply(f"[ERR:{type(exc).__name__}] 查询模型列表失败。")
