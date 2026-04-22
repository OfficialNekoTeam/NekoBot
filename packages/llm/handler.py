"""核心 LLM 对话处理器

作为应用功能直接挂载在消息分发链末端，不经过插件系统。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING

import aiohttp
from loguru import logger

from ..conversations.context import ConfigurationContext, ConversationContext
from ..conversations.models import ConversationKey, IsolationMode
from ..providers.types import ProviderResponse
from ..runtime.context import ExecutionContext
from ..utils.url_guard import is_safe_url

if TYPE_CHECKING:
    from ..app import NekoBotFramework

_DEFAULT_HISTORY_LIMIT = 20
_COMPRESS_KEEP_TURNS = 5
_SUMMARIZE_PROMPT = (
    "请将以下对话历史简洁地总结成几句话，保留关键信息和结论，"
    "不要包含无关细节。总结用中文输出。\n\n对话历史：\n{history}"
)

_PREF_ENABLED = "reply_enabled"
_PREF_MODEL = "preferred_model"
_PREF_PROVIDER = "preferred_provider"
_PREF_GROUP_ENABLED = "group_reply_enabled"
_PREF_BLACKLIST = "user_blacklist"
_PREF_WHITELIST = "user_whitelist"
_PREF_PERSONA = "persona"

# config.json 里 plugin_configs 下的节名（保持向后兼容）
_CONFIG_SECTION = "llm_chat"

ReplyCallable = Callable[[str], Awaitable[str | None]]
RecallCallable = Callable[[str], Awaitable[None]]


async def _noop_recall(message_id: str) -> None:
    _ = message_id


@dataclass
class _Ctx:
    """单次消息处理的上下文束，字段可变。"""

    payload: dict[str, object]
    execution: ExecutionContext
    configuration: ConfigurationContext
    conversation: ConversationContext
    reply: ReplyCallable
    recall: RecallCallable
    config: dict[str, object]


class LLMHandler:
    """LLM 对话处理器，作为消息分发链的核心应用功能。"""

    def __init__(self, framework: NekoBotFramework) -> None:
        self.framework = framework

    async def handle(
        self,
        *,
        payload: dict[str, object],
        execution: ExecutionContext,
        configuration: ConfigurationContext,
        conversation: ConversationContext,
        reply: ReplyCallable,
        recall: RecallCallable | None = None,
    ) -> None:
        config = configuration.get_plugin_config(_CONFIG_SECTION)
        ctx = _Ctx(
            payload=payload,
            execution=execution,
            configuration=configuration,
            conversation=conversation,
            reply=reply,
            recall=recall or _noop_recall,
            config=config,
        )
        await self._handle_message(ctx)

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    async def _handle_message(self, ctx: _Ctx) -> None:
        plain_text = ctx.payload.get("plain_text")
        if not isinstance(plain_text, str) or not plain_text.strip():
            return

        text = plain_text.strip()
        is_group = ctx.execution.scope == "group"

        # 命令优先（不需要唤醒）
        cmd_prefix = self._get_command_prefix(ctx)
        if text.startswith(cmd_prefix):
            cmd_body = text[len(cmd_prefix):]
            parts = cmd_body.split()
            cmd_name = parts[0].lower() if parts else ""
            if cmd_name == "reset":
                await self._cmd_reset(ctx)
                return
            if cmd_name == "llm":
                await self._cmd_llm(ctx, parts[1:])
                return
            if cmd_name == "help":
                await self._cmd_help(ctx)
                return
            if cmd_name == "sid":
                await self._cmd_sid(ctx)
                return
            # 未知命令不落入 LLM
            return

        # 群聊：回复总开关 + 黑/白名单
        if is_group:
            if not await self._is_group_reply_enabled(ctx):
                return
            actor_id = ctx.execution.actor_id
            if actor_id and not await self._is_user_allowed(ctx, actor_id):
                return

        # 唤醒检查
        text, should_respond = self._check_wake(ctx, text, is_group)
        if not should_respond:
            return

        # 每用户回复开关
        if not self._is_reply_enabled(ctx):
            return

        provider_name = self._resolve_provider_name(ctx)
        if provider_name is None:
            logger.warning("llm: no provider configured, skipping")
            return

        model = self._resolve_model(ctx)
        system_prompt = await self._get_system_prompt(ctx)
        effective = ctx.payload.get("effective_text")
        llm_text = effective if isinstance(effective, str) and effective else text
        sender_info = self._extract_sender_info(ctx)
        messages, extra_context = self._build_messages(ctx, llm_text, sender_info=sender_info)
        system_prompt = await self._get_system_prompt(ctx, extra_context)
        raw_image_urls = ctx.payload.get("image_urls")
        image_urls: list[str] = (
            [u for u in raw_image_urls if isinstance(u, str)]
            if isinstance(raw_image_urls, list)
            else []
        )

        logger.info(
            "llm: provider={} model={} history_turns={} images={} text={}",
            provider_name,
            model or "default",
            len(messages) // 2,
            len(image_urls),
            text[:80] + "..." if len(text) > 80 else text,
        )

        tools = self.framework.tool_registry.get_tool_definitions()

        invoke_kwargs: dict[str, object] = dict(
            provider_name=provider_name,
            execution=ctx.execution,
            configuration=ctx.configuration,
            conversation=ctx.conversation,
            permission_engine=self.framework.permission_engine,
            messages=messages,
            system_prompt=system_prompt,
            model=model,
            image_urls=image_urls,
            tools=tools,
        )

        try:
            result = await self._run_tool_loop(ctx, invoke_kwargs)
        except PermissionError as exc:
            logger.warning("llm: permission denied: {}", exc)
            await ctx.reply("[ERR:permission_denied] 无权访问该 Provider。")
            return
        except Exception as exc:
            logger.error("llm: provider call failed: {}", exc)
            await ctx.reply(f"[ERR:{type(exc).__name__}] 请求失败，请稍后再试。")
            return

        if not isinstance(result, ProviderResponse):
            logger.warning("llm: unexpected result type: {}", type(result))
            return

        if result.error:
            err = result.error
            logger.error("llm: provider error: code={} msg={}", err.code, err.message)
            if err.retryable:
                err_msg_id = await ctx.reply(
                    f"[ERR:{err.code}] {err.message[:120]} (重试中...)"
                )
                logger.info("llm: retrying after retryable error code={}", err.code)
                try:
                    retry_result = await self._run_tool_loop(ctx, invoke_kwargs)
                except Exception as exc2:
                    logger.error("llm: retry failed: {}", exc2)
                    return
                if (
                    isinstance(retry_result, ProviderResponse)
                    and not retry_result.error
                    and retry_result.content
                ):
                    if err_msg_id is not None:
                        await ctx.recall(err_msg_id)
                    await self._save_history(
                        ctx, llm_text, retry_result.content, provider_name, model
                    )
                    await ctx.reply(retry_result.content)
                else:
                    logger.warning("llm: retry did not produce a valid response")
            else:
                await ctx.reply(f"[ERR:{err.code}] {err.message[:120]}")
            return

        if not result.content:
            logger.warning("llm: empty response from provider")
            return

        await self._save_history(ctx, llm_text, result.content, provider_name, model)
        await ctx.reply(result.content)

    # ------------------------------------------------------------------
    # 命令处理
    # ------------------------------------------------------------------

    async def _cmd_help(self, ctx: _Ctx) -> None:
        p = self._get_command_prefix(ctx)
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
        for registered in self.framework.runtime_registry.plugins.values():
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

    async def _run_tool_loop(
        self,
        ctx: _Ctx,
        invoke_kwargs: dict[str, object],
    ) -> ProviderResponse:
        """执行 provider 调用，支持多轮 tool call 循环。

        当 LLM 返回 tool_calls 时，执行工具并将结果追加到消息后继续调用，
        直到 LLM 返回正常文本回复或达到最大轮数。
        """
        import json as _json

        max_iterations = self._get_config_int(ctx, "tool_max_iterations", 5)
        messages: list[dict[str, object]] = list(
            invoke_kwargs.get("messages", [])  # type: ignore[arg-type]
        )

        for iteration in range(max_iterations):
            current_kwargs = dict(invoke_kwargs)
            current_kwargs["messages"] = messages

            result = await self.framework.invoke_provider(**current_kwargs)  # type: ignore[arg-type]

            if not isinstance(result, ProviderResponse):
                return result  # type: ignore[return-value]

            # 无工具调用或有错误，直接返回
            if not result.tool_calls or result.error:
                return result

            logger.info(
                "llm: tool loop iteration={} tool_calls={}",
                iteration + 1,
                [tc.name for tc in result.tool_calls],
            )

            # 追加 assistant 消息（带 tool_calls 标记）
            tool_calls_serialized = [
                {
                    "id": tc.id or tc.name,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": _json.dumps(tc.arguments)},
                }
                for tc in result.tool_calls
            ]
            messages.append({
                "role": "assistant",
                "content": result.content or "",
                "tool_calls": tool_calls_serialized,
            })

            # 执行所有工具调用，追加结果
            for tool_call in result.tool_calls:
                tool_result = await self.framework.tool_registry.dispatch(tool_call)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id or tool_call.name,
                    "content": str(tool_result),
                })
                logger.debug("llm: tool {!r} result: {}", tool_call.name, str(tool_result)[:200])

        # 超出最大轮数，做最后一次不带工具的调用
        logger.warning("llm: tool loop reached max iterations ({}), forcing final call", max_iterations)
        final_kwargs = dict(invoke_kwargs)
        final_kwargs["messages"] = messages
        final_kwargs["tools"] = []
        return await self.framework.invoke_provider(**final_kwargs)  # type: ignore[return-value]

    async def _cmd_reset(self, ctx: _Ctx) -> None:
        cleared = replace(ctx.conversation, history=[], summary=None)
        ctx.conversation = await self.framework.save_conversation_context(cleared)
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
        if sub in _ADMIN_SUBS and not self._check_permission(ctx.execution, "command.invoke"):
            await ctx.reply("[ERR] 权限不足。")
            return

        prefs: dict[str, object] = dict(ctx.conversation.provider_preferences)

        if sub == "off":
            prefs[_PREF_ENABLED] = False
            ctx.conversation = await self._save_prefs(ctx, prefs)
            await ctx.reply("[OFF] 已关闭自动回复，发送 /llm on 可重新开启。")

        elif sub == "on":
            prefs[_PREF_ENABLED] = True
            ctx.conversation = await self._save_prefs(ctx, prefs)
            await ctx.reply("[ON] 已开启自动回复。")

        elif sub == "model":
            arg = parts[1].lower() if len(parts) > 1 else "ls"
            if arg in ("ls", "list"):
                await self._cmd_model_list(ctx)
            else:
                prefs[_PREF_MODEL] = parts[1]
                ctx.conversation = await self._save_prefs(ctx, prefs)
                await ctx.reply(f"[OK] 模型已切换为：{parts[1]}")

        elif sub == "provider" and len(parts) > 1:
            prefs[_PREF_PROVIDER] = parts[1]
            ctx.conversation = await self._save_prefs(ctx, prefs)
            await ctx.reply(f"[OK] Provider 已切换为：{parts[1]}")

        elif sub in ("reset", "clearmodel"):
            prefs.pop(_PREF_MODEL, None)
            prefs.pop(_PREF_PROVIDER, None)
            ctx.conversation = await self._save_prefs(ctx, prefs)
            await ctx.reply("[OK] 已恢复默认模型和 Provider。")

        elif sub in ("compress", "summarize"):
            await self._do_compress(ctx)

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
            group_enabled = await self._is_group_reply_enabled(ctx)
            gs = await self._load_group_settings(ctx)
            bl = gs.provider_preferences.get(_PREF_BLACKLIST, [])
            wl = gs.provider_preferences.get(_PREF_WHITELIST, [])
            group_line = f"群回复: {'开启' if group_enabled else '关闭'}\n"
            bl_line = f"黑名单: {', '.join(str(u) for u in bl) or '(空)'}\n"  # type: ignore[union-attr]
            wl_line = f"白名单: {', '.join(str(u) for u in wl) or '(空)'}\n"  # type: ignore[union-attr]
        persona_name = await self._get_active_persona_name(ctx)
        persona_line = f"人设: {persona_name}\n" if persona_name else ""
        cmd_prefix = self._get_command_prefix(ctx)
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
        personas = await self._get_personas(ctx)
        sub = args[0].lower() if args else "info"
        is_group = ctx.execution.scope == "group"

        if sub == "list":
            if not personas:
                await ctx.reply("[人设] 未配置任何人设（在 llm_chat.personas 中添加）。")
                return
            active = await self._get_active_persona_name(ctx)
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
            ctx.conversation = await self._save_prefs(ctx, prefs)
            await ctx.reply(f"[OK] 人设已切换为：{name}")

        elif sub == "reset":
            prefs = dict(ctx.conversation.provider_preferences)
            prefs.pop(_PREF_PERSONA, None)
            ctx.conversation = await self._save_prefs(ctx, prefs)
            # 若在群聊，也同时清除群默认
            if is_group:
                gs = await self._load_group_settings(ctx)
                gp = dict(gs.provider_preferences)
                gp.pop(_PREF_PERSONA, None)
                await self._save_group_settings(ctx, gs, gp)
            await ctx.reply("[OK] 已恢复默认人设。")

        elif sub == "info":
            active_name = await self._get_active_persona_name(ctx)
            active_text = await self._resolve_persona(ctx)
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
                gs = await self._load_group_settings(ctx)
                gp = dict(gs.provider_preferences)
                gp[_PREF_PERSONA] = name
                await self._save_group_settings(ctx, gs, gp)
                await ctx.reply(f"[OK] 本群默认人设已设为：{name}")
            elif g_action == "reset":
                gs = await self._load_group_settings(ctx)
                gp = dict(gs.provider_preferences)
                gp.pop(_PREF_PERSONA, None)
                await self._save_group_settings(ctx, gs, gp)
                await ctx.reply("[OK] 本群默认人设已重置。")
            else:
                await ctx.reply("用法：/llm persona group set <名称> | group reset")

        else:
            p = self._get_command_prefix(ctx)
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
        gs = await self._load_group_settings(ctx)
        prefs = dict(gs.provider_preferences)
        current: list[str] = list(prefs.get(pref_key, []))  # type: ignore[arg-type]

        if action == "list":
            await ctx.reply(f"[{label}] {', '.join(current) if current else '(空)'}")
            return
        if action == "clear":
            prefs[pref_key] = []
            await self._save_group_settings(ctx, gs, prefs)
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
            await self._save_group_settings(ctx, gs, prefs)
            await ctx.reply(f"[OK] 已将 {target_id} 加入{label}。")
        elif action == "remove":
            if target_id in current:
                current.remove(target_id)
                prefs[pref_key] = current
                await self._save_group_settings(ctx, gs, prefs)
                await ctx.reply(f"[OK] 已将 {target_id} 移出{label}。")
            else:
                await ctx.reply(f"[ERR] {target_id} 不在{label}中。")
        else:
            await ctx.reply(f"未知操作：{action}")

    async def _cmd_llm_group(self, ctx: _Ctx, action: str) -> None:
        if ctx.execution.group_id is None:
            await ctx.reply("此命令仅在群聊中有效。")
            return
        gs = await self._load_group_settings(ctx)
        prefs = dict(gs.provider_preferences)
        if action == "off":
            prefs[_PREF_GROUP_ENABLED] = False
            await self._save_group_settings(ctx, gs, prefs)
            await ctx.reply("[OFF] 已关闭本群自动回复。")
        elif action == "on":
            prefs[_PREF_GROUP_ENABLED] = True
            await self._save_group_settings(ctx, gs, prefs)
            await ctx.reply("[ON] 已开启本群自动回复。")
        else:
            await ctx.reply("用法：/llm group on|off")

    # ------------------------------------------------------------------
    # 群设置（独立 conversation key 存储）
    # ------------------------------------------------------------------

    def _group_settings_key(self, ctx: _Ctx) -> str:
        group_id = ctx.execution.group_id or "global"
        instance = ctx.execution.platform_instance_uuid or "default"
        return f"group_settings:{instance}:{group_id}"

    async def _load_group_settings(self, ctx: _Ctx) -> ConversationContext:
        group_id = ctx.execution.group_id or "global"
        key = self._group_settings_key(ctx)
        stored = await self.framework.conversation_store.get_conversation(key)
        if stored is not None:
            return stored
        return ConversationContext(
            isolation_mode=IsolationMode.SHARED_GROUP,
            conversation_key=ConversationKey(key),
            scope="group",
            chat_id=group_id,
        )

    async def _save_group_settings(
        self,
        ctx: _Ctx,
        existing: ConversationContext,
        prefs: dict[str, object],
    ) -> None:
        await self.framework.save_conversation_context(
            replace(existing, provider_preferences=prefs)
        )

    async def _is_group_reply_enabled(self, ctx: _Ctx) -> bool:
        if ctx.execution.group_id is None:
            return True
        gs = await self._load_group_settings(ctx)
        return bool(gs.provider_preferences.get(_PREF_GROUP_ENABLED, True))

    async def _is_user_allowed(self, ctx: _Ctx, user_id: str) -> bool:
        gs = await self._load_group_settings(ctx)
        prefs = gs.provider_preferences
        blacklist: list[object] = prefs.get(_PREF_BLACKLIST, [])  # type: ignore[assignment]
        if isinstance(blacklist, list) and user_id in blacklist:
            logger.debug("llm: user {} is blacklisted", user_id)
            return False
        whitelist: list[object] = prefs.get(_PREF_WHITELIST, [])  # type: ignore[assignment]
        if isinstance(whitelist, list) and whitelist and user_id not in whitelist:
            logger.debug("llm: user {} not in whitelist", user_id)
            return False
        return True

    # ------------------------------------------------------------------
    # 唤醒逻辑
    # ------------------------------------------------------------------

    def _check_wake(
        self, ctx: _Ctx, text: str, is_group: bool
    ) -> tuple[str, bool]:
        if not is_group:
            return text, True

        # 引用 bot 自己发的消息（由平台适配器预先解析）
        if ctx.payload.get("is_reply_to_self"):
            logger.debug("llm: woken by reply to own message")
            return text, True

        self_id = self._get_self_id(ctx)
        if self_id and self._is_at_me(ctx, self_id):
            stripped = self._strip_at_prefix(text, self_id)
            logger.debug("llm: woken by @mention, self_id={}", self_id)
            return stripped, True

        chat_prefix = self._get_config_str(ctx, "chat_prefix", "/chat")
        if text.startswith(chat_prefix):
            stripped = text[len(chat_prefix):].lstrip()
            if not stripped:
                return text, False
            logger.debug("llm: woken by prefix {!r}", chat_prefix)
            return stripped, True

        keywords_raw = ctx.config.get("wake_keywords")
        if isinstance(keywords_raw, list):
            for kw in keywords_raw:
                if isinstance(kw, str) and kw and kw in text:
                    logger.debug("llm: woken by keyword {!r}", kw)
                    return text, True

        return text, False

    def _get_self_id(self, ctx: _Ctx) -> str | None:
        raw = ctx.payload.get("raw_event")
        if isinstance(raw, dict):
            self_id = raw.get("self_id")
            if isinstance(self_id, (str, int)):
                return str(self_id)
        meta = ctx.payload.get("metadata")
        if isinstance(meta, dict):
            self_id = meta.get("onebot_self_id")
            if isinstance(self_id, str):
                return self_id
        return None

    def _is_at_me(self, ctx: _Ctx, self_id: str) -> bool:
        segments = ctx.payload.get("segments")
        if not isinstance(segments, list):
            return False
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            if seg.get("type") == "at":
                data = seg.get("data", {})
                if isinstance(data, dict) and str(data.get("qq", "")) == self_id:
                    return True
        return False

    def _strip_at_prefix(self, text: str, self_id: str) -> str:
        stripped = text.strip()
        prefix = f"@{self_id}"
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix):].lstrip()
        return stripped or text


    # ------------------------------------------------------------------
    # 历史记录 & 摘要
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        ctx: _Ctx,
        user_text: str,
        *,
        sender_info: dict[str, str | None] | None = None,
    ) -> tuple[list[dict[str, object]], str]:
        history_limit = self._get_config_int(ctx, "history_limit", _DEFAULT_HISTORY_LIMIT)
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
        skills = self.framework.skill_manager.skill_descriptions
        if skills:
            skill_lines = [f"- {s['name']}: {s['description']}" for s in skills]
            extra_parts.append("[可用技能列表]\n" + "\n".join(skill_lines) + "\n(如需执行上述技能，请先调用 view_skill 工具查看详细指令)")

        messages.append({"role": "user", "content": user_text})
        return messages, "\n\n".join(extra_parts)

    async def _save_history(
        self,
        ctx: _Ctx,
        user_text: str,
        assistant_text: str,
        provider_name: str,
        model: str | None,
    ) -> None:
        new_history = list(ctx.conversation.history) + [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text},
        ]
        history_limit = self._get_config_int(ctx, "history_limit", _DEFAULT_HISTORY_LIMIT)
        summary = ctx.conversation.summary
        if len(new_history) > history_limit * 2:
            summary, new_history = await self._compress(
                ctx, new_history, provider_name, model
            )
        updated = replace(ctx.conversation, history=new_history, summary=summary)
        ctx.conversation = await self.framework.save_conversation_context(updated)
        logger.debug(
            "llm: saved history turns={} has_summary={}",
            len(new_history) // 2,
            bool(summary),
        )

    async def _compress(
        self,
        ctx: _Ctx,
        history: list[dict[str, object]],
        provider_name: str,
        model: str | None,
    ) -> tuple[str | None, list[dict[str, object]]]:
        keep = _COMPRESS_KEEP_TURNS * 2
        to_summarize = history[:-keep] if len(history) > keep else history
        recent = history[-keep:] if len(history) > keep else []
        history_text = "\n".join(
            f"{e.get('role', '?')}: {e.get('content', '')}"
            for e in to_summarize
            if isinstance(e.get("role"), str) and isinstance(e.get("content"), str)
        )
        prompt = _SUMMARIZE_PROMPT.format(history=history_text)
        try:
            result = await self.framework.invoke_provider(
                provider_name=provider_name,
                execution=ctx.execution,
                configuration=ctx.configuration,
                conversation=ctx.conversation,
                permission_engine=self.framework.permission_engine,
                messages=[{"role": "user", "content": prompt}],
                model=model,
            )
            if isinstance(result, ProviderResponse) and result.content:
                logger.info(
                    "llm: compressed {} turns into summary", len(to_summarize) // 2
                )
                return result.content, recent
        except Exception as exc:
            logger.warning("llm: compression failed, keeping full history: {}", exc)
        return None, history[-keep:]

    async def _do_compress(self, ctx: _Ctx) -> None:
        if not ctx.conversation.history:
            await ctx.reply("当前没有历史记录可以压缩。")
            return
        provider_name = self._resolve_provider_name(ctx)
        if provider_name is None:
            await ctx.reply("未配置 Provider，无法压缩。")
            return
        model = self._resolve_model(ctx)
        summary, new_history = await self._compress(
            ctx, ctx.conversation.history, provider_name, model
        )
        updated = replace(ctx.conversation, history=new_history, summary=summary)
        ctx.conversation = await self.framework.save_conversation_context(updated)
        if summary:
            await ctx.reply(
                f"[OK] 已压缩历史（保留最近 {_COMPRESS_KEEP_TURNS} 轮）\n"
                f"摘要：{summary[:200]}{'...' if len(summary) > 200 else ''}"
            )
        else:
            await ctx.reply(f"[OK] 已截断历史，保留最近 {_COMPRESS_KEEP_TURNS} 轮。")

    async def _cmd_model_list(self, ctx: _Ctx) -> None:
        """列出当前 Provider 支持的模型。"""
        provider_name = self._resolve_provider_name(ctx)
        if provider_name is None:
            await ctx.reply("[ERR] 未配置 Provider。")
            return

        # 先尝试从 provider_info 静态列表获取
        try:
            provider = await self.framework.provider_registry.get(provider_name)
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

    # ------------------------------------------------------------------
    # 配置 & 偏好 helpers
    # ------------------------------------------------------------------

    def _check_permission(self, execution: ExecutionContext, *permissions: str) -> bool:
        engine = self.framework.permission_engine
        if engine is None:
            return True
        decision = engine.evaluate(
            permissions,
            execution.to_authorization_context(
                resource_kind="command",
                resource_name=permissions[0] if permissions else "",
            ),
            require_all=False,
        )
        return decision.allowed

    def _is_reply_enabled(self, ctx: _Ctx) -> bool:
        return bool(ctx.conversation.provider_preferences.get(_PREF_ENABLED, True))

    def _resolve_provider_name(self, ctx: _Ctx) -> str | None:
        pref = ctx.conversation.provider_preferences.get(_PREF_PROVIDER)
        if isinstance(pref, str) and pref:
            return pref
        return ctx.configuration.resolve_provider_name()

    def _resolve_model(self, ctx: _Ctx) -> str | None:
        pref = ctx.conversation.provider_preferences.get(_PREF_MODEL)
        return pref if isinstance(pref, str) and pref else None

    async def _get_system_prompt(self, ctx: _Ctx, extra_context: str = "") -> str:
        persona_text = await self._resolve_persona(ctx)
        if not persona_text:
            # 向后兼容：直接配置的 system_prompt
            raw = ctx.config.get("system_prompt")
            persona_text = raw if isinstance(raw, str) and raw.strip() else "你是 NekoBot，一个由 Neko 开发的智能机器人。"

        if extra_context:
            return f"{persona_text}\n\n{extra_context}"
        return persona_text

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
            db_personas = await self.framework.conversation_store.list_personas()
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
            gs = await self._load_group_settings(ctx)
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
            gs = await self._load_group_settings(ctx)
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

    async def _save_prefs(self, ctx: _Ctx, prefs: dict[str, object]) -> ConversationContext:
        updated = replace(ctx.conversation, provider_preferences=prefs)
        return await self.framework.save_conversation_context(updated)

    def _get_command_prefix(self, ctx: _Ctx) -> str:
        val = ctx.configuration.framework_config.get("command_prefix")
        return val if isinstance(val, str) and val else "/"

    def _get_config_str(self, ctx: _Ctx, key: str, default: str) -> str:
        val = ctx.config.get(key)
        return val if isinstance(val, str) else default

    def _get_config_int(self, ctx: _Ctx, key: str, default: int) -> int:
        val = ctx.config.get(key)
        return val if isinstance(val, int) else default

    def _get_config_bool(self, ctx: _Ctx, key: str, default: bool) -> bool:
        val = ctx.config.get(key)
        return val if isinstance(val, bool) else default
