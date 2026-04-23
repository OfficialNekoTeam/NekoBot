"""核心 LLM 对话处理器

作为应用功能直接挂载在消息分发链末端，不经过插件系统。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from ..providers.types import ProviderResponse
from ._commands import _CommandsMixin
from ._context import _ContextMixin
from ._group import _GroupMixin
from ._helpers import _HelpersMixin
from ._history import _HistoryMixin
from ._types import (
    _CONFIG_SECTION,
    RecallCallable,
    ReplyCallable,
    _Ctx,
    _noop_recall,
)
from ._wake import _WakeMixin

if TYPE_CHECKING:
    from ..app import NekoBotFramework
    from ..conversations.context import ConfigurationContext, ConversationContext
    from ..runtime.context import ExecutionContext

__all__ = ["LLMHandler", "_noop_recall"]


class LLMHandler(
    _CommandsMixin,
    _GroupMixin,
    _WakeMixin,
    _ContextMixin,
    _HistoryMixin,
    _HelpersMixin,
):
    """LLM 对话处理器，作为消息分发链的核心应用功能。"""

    def __init__(self, framework: NekoBotFramework) -> None:
        self.framework = framework
        # Per-conversation serialization: same key → sequential, different keys → parallel.
        # Locks are created lazily and retained for the lifetime of the handler.
        self._conv_locks: dict[str, asyncio.Lock] = {}

    def _get_conv_lock(self, key: str) -> asyncio.Lock:
        if key not in self._conv_locks:
            self._conv_locks[key] = asyncio.Lock()
        return self._conv_locks[key]

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
        conv_key = str(conversation.conversation_key) if conversation.conversation_key else ""
        lock = self._get_conv_lock(conv_key)
        async with lock:
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
    # 工具循环
    # ------------------------------------------------------------------

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
