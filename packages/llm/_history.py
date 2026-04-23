"""_HistoryMixin: conversation history saving and compression."""

from __future__ import annotations

from dataclasses import replace

from loguru import logger

from ..providers.types import ProviderResponse
from ._types import (
    _COMPRESS_KEEP_TURNS,
    _SUMMARIZE_PROMPT,
    _Ctx,
)


class _HistoryMixin:
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
        history_limit = self._get_config_int(ctx, "history_limit", 20)  # type: ignore[attr-defined]
        summary = ctx.conversation.summary
        if len(new_history) > history_limit * 2:
            summary, new_history = await self._compress(
                ctx, new_history, provider_name, model
            )
        updated = replace(ctx.conversation, history=new_history, summary=summary)
        ctx.conversation = await self.framework.save_conversation_context(updated)  # type: ignore[attr-defined]
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
            result = await self.framework.invoke_provider(  # type: ignore[attr-defined]
                provider_name=provider_name,
                execution=ctx.execution,
                configuration=ctx.configuration,
                conversation=ctx.conversation,
                permission_engine=self.framework.permission_engine,  # type: ignore[attr-defined]
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
        provider_name = self._resolve_provider_name(ctx)  # type: ignore[attr-defined]
        if provider_name is None:
            await ctx.reply("未配置 Provider，无法压缩。")
            return
        model = self._resolve_model(ctx)  # type: ignore[attr-defined]
        summary, new_history = await self._compress(
            ctx, ctx.conversation.history, provider_name, model
        )
        updated = replace(ctx.conversation, history=new_history, summary=summary)
        ctx.conversation = await self.framework.save_conversation_context(updated)  # type: ignore[attr-defined]
        if summary:
            await ctx.reply(
                f"[OK] 已压缩历史（保留最近 {_COMPRESS_KEEP_TURNS} 轮）\n"
                f"摘要：{summary[:200]}{'...' if len(summary) > 200 else ''}"
            )
        else:
            await ctx.reply(f"[OK] 已截断历史，保留最近 {_COMPRESS_KEEP_TURNS} 轮。")
