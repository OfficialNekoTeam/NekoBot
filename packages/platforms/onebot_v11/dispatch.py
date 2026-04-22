from __future__ import annotations

import base64
import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol, TypeAlias

import aiohttp
from loguru import logger

from ...utils.url_guard import is_safe_url

from ...app import NekoBotFramework
from ...conversations.context import ConfigurationContext
from ...platforms.dispatcher import BaseDispatcher
from ...platforms.types import PlatformEvent, SegmentType
from ...providers.types import STTRequest
from ...runtime.context import ExecutionContext
from .message_codec import OneBotV11MessageCodec
from .types import (
    OneBotV11MessageSegment,
    OneBotV11OutboundTarget,
    OneBotV11Scene,
)

if TYPE_CHECKING:
    from ...llm.handler import LLMHandler

OutboundSender: TypeAlias = Callable[
    [OneBotV11OutboundTarget, list[dict[str, object]]],
    Awaitable[dict[str, object]],
]
DeleteSender: TypeAlias = Callable[[str], Awaitable[dict[str, object]]]
FetchMessageCallable: TypeAlias = Callable[[str], Awaitable[dict[str, object]]]
FetchForwardCallable: TypeAlias = Callable[[str], Awaitable[dict[str, object]]]


class MessageCodecLike(Protocol):
    def text(self, text: str) -> OneBotV11MessageSegment: ...

    def record(self, file: str) -> OneBotV11MessageSegment: ...

    def encode(
        self, segments: list[OneBotV11MessageSegment]
    ) -> list[dict[str, object]]: ...


class OneBotV11Dispatcher(BaseDispatcher):
    """OneBot V11 platform dispatcher.

    Extends BaseDispatcher with platform-specific callables:
        - reply  : encode text → OB11 message segments, send to group/private
        - recall : delete a message by message_id
        - send_voice : base64-encode audio, send as record segment
        - _get_llm_extra_payload : image URLs, quoted text, STT transcription
    """

    def __init__(
        self,
        framework: NekoBotFramework,
        *,
        send_callable: OutboundSender,
        delete_callable: DeleteSender | None = None,
        fetch_message_callable: FetchMessageCallable | None = None,
        fetch_forward_callable: FetchForwardCallable | None = None,
        message_codec: MessageCodecLike | None = None,
        llm_handler: LLMHandler | None = None,
    ) -> None:
        super().__init__(framework, llm_handler=llm_handler)
        self.send_callable: OutboundSender = send_callable
        self.delete_callable: DeleteSender | None = delete_callable
        self.fetch_message_callable: FetchMessageCallable | None = fetch_message_callable
        self.fetch_forward_callable: FetchForwardCallable | None = fetch_forward_callable
        self.message_codec: MessageCodecLike = (
            message_codec if message_codec is not None else OneBotV11MessageCodec()
        )

    # ------------------------------------------------------------------
    # BaseDispatcher abstract interface
    # ------------------------------------------------------------------

    def _make_reply_callable(
        self, event: PlatformEvent
    ) -> Callable[[str], Awaitable[str | None]]:
        async def reply(message: str) -> str | None:
            target = self.build_reply_target(event)
            if target is None:
                logger.warning(
                    "Cannot reply to event with no reply target: {}", event.event_name
                )
                return None
            outbound: list[OneBotV11MessageSegment] = [self.message_codec.text(message)]
            segments = self.message_codec.encode(outbound)
            logger.info(
                "[OneBot] 发送回复 | scene={} chat_id={} | 内容: {}",
                target.scene,
                target.chat_id,
                message[:100] + "..." if len(message) > 100 else message,
            )
            resp = await self.send_callable(target, segments)
            data = resp.get("data")
            if isinstance(data, dict):
                msg_id = data.get("message_id")
                if msg_id is not None:
                    return str(msg_id)
            return None

        return reply

    def _make_recall_callable(
        self, event: PlatformEvent
    ) -> Callable[[str], Awaitable[None]]:
        async def recall(message_id: str) -> None:
            if self.delete_callable is None:
                logger.warning("[OneBot] delete_callable 未配置，无法撤回消息")
                return
            try:
                await self.delete_callable(message_id)
                logger.info("[OneBot] 已撤回消息 message_id={}", message_id)
            except Exception as exc:
                logger.warning("[OneBot] 撤回消息失败 message_id={}: {}", message_id, exc)

        return recall

    def _make_send_voice_callable(
        self, event: PlatformEvent
    ) -> Callable[[bytes, str], Awaitable[str | None]]:
        async def send_voice(audio_bytes: bytes, mime_type: str = "audio/mpeg") -> str | None:
            target = self.build_reply_target(event)
            if target is None:
                return None
            b64 = base64.b64encode(audio_bytes).decode()
            seg = self.message_codec.record(f"base64://{b64}")
            segments = self.message_codec.encode([seg])
            resp = await self.send_callable(target, segments)
            data = resp.get("data")
            if isinstance(data, dict):
                msg_id = data.get("message_id")
                if msg_id is not None:
                    return str(msg_id)
            return None

        return send_voice

    async def _get_llm_extra_payload(
        self,
        event: PlatformEvent,
        execution: ExecutionContext,
        configuration: ConfigurationContext,
    ) -> dict[str, object]:
        extra: dict[str, object] = {}

        quoted = await self._analyze_quoted_message(event)
        if quoted["image_urls"]:
            extra["image_urls"] = quoted["image_urls"]
        if quoted["is_reply_to_self"]:
            extra["is_reply_to_self"] = True
        if quoted["quoted_text"]:
            extra["quoted_text"] = quoted["quoted_text"]

        stt_text = await self._transcribe_voice(event, configuration, execution)
        if stt_text:
            extra["plain_text"] = stt_text
            extra["stt_transcribed"] = True
            logger.info("[STT] 语音转文字: {}", stt_text[:80])

        return extra

    # ------------------------------------------------------------------
    # OneBot V11-specific helpers
    # ------------------------------------------------------------------

    def build_reply_target(self, event: PlatformEvent) -> OneBotV11OutboundTarget | None:
        if event.scene == OneBotV11Scene.GROUP and event.group_id is not None:
            return OneBotV11OutboundTarget(
                scene=OneBotV11Scene.GROUP,
                chat_id=event.group_id,
                group_id=event.group_id,
                user_id=event.user_id,
                message_id=event.message_id,
                reply_to_message_id=event.message_id,
            )

        chat_id = event.chat_id or event.user_id
        if chat_id is None:
            return None

        return OneBotV11OutboundTarget(
            scene=OneBotV11Scene.PRIVATE,
            chat_id=chat_id,
            user_id=event.user_id or chat_id,
            message_id=event.message_id,
            reply_to_message_id=event.message_id,
        )

    async def _transcribe_voice(
        self,
        event: PlatformEvent,
        configuration: ConfigurationContext,
        execution: ExecutionContext,
    ) -> str | None:
        """If the event contains a voice segment and stt_provider is configured,
        download the audio and transcribe it."""
        stt_provider = configuration.framework_config.get("stt_provider")
        if not isinstance(stt_provider, str) or not stt_provider:
            return None

        audio_url: str | None = None
        audio_mime = "audio/mpeg"
        for seg in event.segments:
            if seg.type == SegmentType.VOICE:
                url = seg.data.get("url") or seg.data.get("file", "")
                if isinstance(url, str) and is_safe_url(url):
                    audio_url = url
                    break

        if audio_url is None:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(audio_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        logger.warning("[STT] 下载音频失败 status={}", resp.status)
                        return None
                    audio_bytes = await resp.read()
                    ct = resp.headers.get("Content-Type", "")
                    if ct:
                        audio_mime = ct.split(";")[0].strip()
        except Exception as exc:
            logger.warning("[STT] 下载音频出错: {}", exc)
            return None

        try:
            result = await self.framework.invoke_provider(
                provider_name=stt_provider,
                execution=execution,
                configuration=configuration,
                request=STTRequest(audio_bytes=audio_bytes, mime_type=audio_mime),
            )
            from ...providers.types import STTResponse  # noqa: PLC0415
            if isinstance(result, STTResponse):
                if result.error:
                    logger.warning("[STT] 转写失败: {}", result.error.message)
                    return None
                return result.text or None
        except Exception as exc:
            logger.warning("[STT] 调用 STT provider 出错: {}", exc)

        return None

    async def _analyze_quoted_message(
        self, event: PlatformEvent
    ) -> dict[str, object]:
        """Analyse image URLs and quoted-message context for LLM payload.

        Returns:
            image_urls       : list of image URLs from current + quoted messages
            is_reply_to_self : whether the quoted message was sent by this bot
            quoted_text      : text content of the quoted message
        """
        image_urls: list[str] = []
        is_reply_to_self = False
        quoted_text: str | None = None

        # 1. Images in the current message
        for seg in event.segments:
            if seg.type == SegmentType.IMAGE:
                url = seg.data.get("url") or seg.data.get("file", "")
                if isinstance(url, str) and is_safe_url(url):
                    image_urls.append(url)

        # 2. Reply segment — fetch referenced message once
        if self.fetch_message_callable is not None:
            for seg in event.segments:
                if seg.type != SegmentType.REPLY:
                    continue
                # After normalisation, reply data uses "message_id"
                msg_id = seg.data.get("message_id")
                if not msg_id:
                    continue
                try:
                    resp = await self.fetch_message_callable(str(msg_id))
                    data = resp.get("data") if isinstance(resp, dict) else None
                    if not isinstance(data, dict):
                        continue

                    self_id = event.self_id or ""
                    sender_id = str(data.get("user_id") or "")
                    if not sender_id:
                        sender = data.get("sender")
                        if isinstance(sender, dict):
                            sender_id = str(sender.get("user_id") or "")
                    if sender_id and self_id and sender_id == self_id:
                        is_reply_to_self = True

                    # Raw API response is always OB11 format
                    raw_msg = data.get("message", [])
                    raw_segs: list[object] = raw_msg if isinstance(raw_msg, list) else []  # type: ignore[assignment]
                    forward_id: str | None = None
                    for raw_seg in raw_segs:
                        if isinstance(raw_seg, dict) and raw_seg.get("type") == "forward":
                            seg_data_f = raw_seg.get("data", {})
                            if isinstance(seg_data_f, dict):
                                fid = seg_data_f.get("id")
                                if isinstance(fid, (str, int)) and fid:
                                    forward_id = str(fid)
                            break

                    if forward_id is not None:
                        qt = await self._extract_forward_text(forward_id)
                        if qt:
                            quoted_text = qt
                    else:
                        text_parts: list[str] = []
                        for raw_seg in raw_segs:
                            if not isinstance(raw_seg, dict):
                                continue
                            seg_type = raw_seg.get("type")
                            seg_data = raw_seg.get("data", {})
                            if not isinstance(seg_data, dict):
                                continue
                            if seg_type == "image":
                                url = seg_data.get("url") or seg_data.get("file", "")
                                if isinstance(url, str) and url.startswith("http"):
                                    image_urls.append(url)
                            elif seg_type == "text":
                                t = seg_data.get("text", "")
                                if isinstance(t, str) and t.strip():
                                    text_parts.append(t.strip())
                        if text_parts:
                            quoted_text = " ".join(text_parts)

                except Exception as exc:
                    logger.warning(
                        "[OneBot] 获取引用消息失败 msg_id={}: {}", msg_id, exc
                    )
                break  # only process the first reply segment

        return {
            "image_urls": image_urls,
            "is_reply_to_self": is_reply_to_self,
            "quoted_text": quoted_text,
        }

    async def _extract_forward_text(
        self,
        forward_id: str,
        *,
        _seen: set[str] | None = None,
        _depth: int = 0,
    ) -> str | None:
        """Fetch a forwarded message chain and return its text content.

        Supports nested forwards (BFS, max 3 levels / 30 nodes / 2000 chars).
        """
        _MAX_DEPTH = 3
        _MAX_NODES = 30
        _MAX_CHARS = 2000

        if self.fetch_forward_callable is None:
            return None
        if _seen is None:
            _seen = set()
        if forward_id in _seen or _depth >= _MAX_DEPTH:
            return None
        _seen.add(forward_id)

        try:
            resp = await self.fetch_forward_callable(forward_id)
            data = resp.get("data") if isinstance(resp, dict) else None
            if not isinstance(data, dict):
                return None

            raw_nodes = (
                data.get("messages")
                or data.get("message")
                or data.get("nodes")
                or data.get("nodeList")
                or []
            )
            nodes: list[object] = raw_nodes if isinstance(raw_nodes, list) else []

            lines: list[str] = []
            indent = "  " * _depth

            for node in nodes[:_MAX_NODES]:
                if not isinstance(node, dict):
                    continue

                sender_raw = node.get("sender") or {}
                sender_name = ""
                if isinstance(sender_raw, dict):
                    sender_name = (
                        str(sender_raw.get("nickname") or "")
                        or str(sender_raw.get("card") or "")
                        or str(sender_raw.get("user_id") or "")
                    )

                raw_content = node.get("message") or node.get("content") or []
                if isinstance(raw_content, str):
                    try:
                        raw_content = json.loads(raw_content)
                    except Exception:
                        if raw_content.strip():
                            prefix = f"{indent}{sender_name}: " if sender_name else indent
                            lines.append(prefix + raw_content.strip())
                        continue

                segs: list[object] = raw_content if isinstance(raw_content, list) else []
                text_parts: list[str] = []

                for seg in segs:
                    if not isinstance(seg, dict):
                        continue
                    seg_type = seg.get("type", "")
                    seg_data = seg.get("data") or {}
                    if not isinstance(seg_data, dict):
                        continue

                    if seg_type in ("text", "plain"):
                        t = seg_data.get("text", "")
                        if isinstance(t, str) and t.strip():
                            text_parts.append(t.strip())
                    elif seg_type == "image":
                        text_parts.append("[图片]")
                    elif seg_type == "video":
                        text_parts.append("[视频]")
                    elif seg_type == "file":
                        fname = seg_data.get("name") or ""
                        text_parts.append(f"[文件:{fname}]" if fname else "[文件]")
                    elif seg_type in ("forward", "forward_msg"):
                        nested_id = str(seg_data.get("id") or seg_data.get("message_id") or "")
                        if nested_id and nested_id not in _seen:
                            nested = await self._extract_forward_text(
                                nested_id, _seen=_seen, _depth=_depth + 1
                            )
                            if nested:
                                text_parts.append(f"\n{nested}")

                if text_parts:
                    prefix = f"{indent}{sender_name}: " if sender_name else indent
                    lines.append(prefix + "".join(text_parts))

            if not lines:
                return None
            return "\n".join(lines)[:_MAX_CHARS]

        except Exception as exc:
            logger.warning("[OneBot] 获取合并转发内容失败 id={}: {}", forward_id, exc)
            return None
