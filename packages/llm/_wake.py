"""_WakeMixin: wake/activation logic for group messages."""

from __future__ import annotations

from loguru import logger

from ._types import _Ctx


class _WakeMixin:
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
        if self_id and self._is_at_me(ctx, self_id):  # type: ignore[attr-defined]
            stripped = self._strip_at_prefix(text, self_id)
            logger.debug("llm: woken by @mention, self_id={}", self_id)
            return stripped, True

        chat_prefix = self._get_config_str(ctx, "chat_prefix", "/chat")  # type: ignore[attr-defined]
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
            seg_type = seg.get("type")
            data = seg.get("data", {})
            if not isinstance(data, dict):
                continue
            # Normalised platform format: type="mention", data.user_id
            if seg_type == "mention" and str(data.get("user_id", "")) == self_id:
                return True
            # Raw OB11 format (fallback): type="at", data.qq
            if seg_type == "at" and str(data.get("qq", "")) == self_id:
                return True
        return False

    def _strip_at_prefix(self, text: str, self_id: str) -> str:
        stripped = text.strip()
        prefix = f"@{self_id}"
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix):].lstrip()
        return stripped or text
