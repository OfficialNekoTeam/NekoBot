from __future__ import annotations

from typing import cast

from loguru import logger

from ...platforms.types import (
    MessageSegment,
    PlatformEvent,
    PlatformSender,
    Scene,
    SegmentType,
)
from .types import (
    OneBotV11EventType,
    OneBotV11Scene,
    OneBotV11SegmentType,
    ValueMap,
)


class OneBotV11EventParser:
    """Parse raw OneBot V11 JSON payloads into platform-agnostic PlatformEvent."""

    def parse(
        self,
        raw_event: ValueMap,
        *,
        platform_instance_uuid: str,
    ) -> PlatformEvent:
        post_type = self._string(raw_event.get("post_type")) or "unknown"
        scene = self._resolve_scene(raw_event)
        event_name = self._build_event_name(raw_event, scene)
        user_id = self._string(raw_event.get("user_id"))
        group_id = self._string(raw_event.get("group_id"))
        self_id = self._string(raw_event.get("self_id"))
        message_id = self._string(raw_event.get("message_id"))
        segments = self._parse_segments(raw_event.get("message"))
        plain_text = self._resolve_plain_text(raw_event, segments)
        sender = self._parse_sender(raw_event.get("sender"), user_id)

        event = PlatformEvent(
            event_type=post_type,
            event_name=event_name,
            scene=scene,
            platform="onebot",
            platform_instance_uuid=platform_instance_uuid,
            self_id=self_id,
            user_id=user_id,
            group_id=group_id,
            chat_id=self._resolve_chat_id(scene, user_id, group_id),
            message_id=message_id,
            plain_text=plain_text,
            sender=sender,
            segments=segments,
            raw_event=dict(raw_event),
            metadata={
                "message_type": self._string(raw_event.get("message_type")),
                "notice_type": self._string(raw_event.get("notice_type")),
                "request_type": self._string(raw_event.get("request_type")),
                "meta_event_type": self._string(raw_event.get("meta_event_type")),
                "sub_type": self._string(raw_event.get("sub_type")),
                "post_type": post_type,
                "detail_type": self._resolve_detail_type(raw_event),
                "time": self._integer(raw_event.get("time")),
                "onebot_self_id": self_id,
            },
        )

        if post_type == OneBotV11EventType.MESSAGE:
            nickname = sender.username or sender.user_id if sender else user_id
            content = plain_text or self._describe_segments(segments)
            if event.scene == OneBotV11Scene.GROUP:
                logger.info(
                    "[OneBot] 收到群消息 | 群: {} | 用户: {}({}) | 内容: {}",
                    group_id,
                    nickname,
                    user_id,
                    content,
                )
            else:
                logger.info(
                    "[OneBot] 收到私聊消息 | 用户: {}({}) | 内容: {}",
                    nickname,
                    user_id,
                    content,
                )
        else:
            logger.debug(
                "[OneBot] 收到事件: {} | scene={} chat_id={}",
                event.event_name,
                event.scene,
                event.chat_id,
            )
        return event

    # ------------------------------------------------------------------
    # Event name / scene resolution
    # ------------------------------------------------------------------

    def _build_event_name(self, raw_event: ValueMap, scene: str) -> str:
        post_type = self._string(raw_event.get("post_type")) or "unknown"
        sub_type = self._string(raw_event.get("sub_type"))
        if post_type == OneBotV11EventType.MESSAGE:
            message_type = self._string(raw_event.get("message_type")) or scene
            base = f"message.{message_type}"
            return f"{base}.{sub_type}" if sub_type else base
        if post_type == OneBotV11EventType.NOTICE:
            notice_type = self._string(raw_event.get("notice_type")) or "unknown"
            base = f"notice.{notice_type}"
            return f"{base}.{sub_type}" if sub_type else base
        if post_type == OneBotV11EventType.REQUEST:
            request_type = self._string(raw_event.get("request_type")) or "unknown"
            base = f"request.{request_type}"
            return f"{base}.{sub_type}" if sub_type else base
        if post_type == OneBotV11EventType.META_EVENT:
            meta_event_type = self._string(raw_event.get("meta_event_type")) or "unknown"
            base = f"meta_event.{meta_event_type}"
            return f"{base}.{sub_type}" if sub_type else base
        return post_type

    def _resolve_scene(self, raw_event: ValueMap) -> str:
        message_type = self._string(raw_event.get("message_type"))
        if message_type == OneBotV11Scene.GROUP:
            return Scene.GROUP
        if message_type == OneBotV11Scene.PRIVATE:
            return Scene.PRIVATE
        if self._string(raw_event.get("group_id")) is not None:
            return Scene.GROUP
        if self._string(raw_event.get("user_id")) is not None:
            return Scene.PRIVATE
        post_type = self._string(raw_event.get("post_type"))
        if post_type == OneBotV11EventType.META_EVENT:
            return Scene.SYSTEM
        return Scene.SYSTEM

    def _resolve_detail_type(self, raw_event: ValueMap) -> str | None:
        return (
            self._string(raw_event.get("message_type"))
            or self._string(raw_event.get("notice_type"))
            or self._string(raw_event.get("request_type"))
            or self._string(raw_event.get("meta_event_type"))
        )

    def _resolve_chat_id(
        self,
        scene: str,
        user_id: str | None,
        group_id: str | None,
    ) -> str | None:
        if scene == Scene.GROUP:
            return group_id
        if scene == Scene.PRIVATE:
            return user_id
        return group_id or user_id

    # ------------------------------------------------------------------
    # Sender
    # ------------------------------------------------------------------

    def _parse_sender(self, sender: object, fallback_user_id: str | None) -> PlatformSender | None:
        if not isinstance(sender, dict):
            if fallback_user_id is not None:
                return PlatformSender(user_id=fallback_user_id)
            return None
        raw = cast(dict[object, object], sender)
        user_id = self._string(raw.get("user_id"))
        nickname = self._string(raw.get("nickname"))
        card = self._string(raw.get("card"))
        # Prefer card (group display name) over nickname
        username = card or nickname
        role = self._string(raw.get("role"))
        # Preserve all OB11-specific fields in metadata
        metadata: ValueMap = {
            str(key): value
            for key, value in raw.items()
            if isinstance(key, str)
        }
        return PlatformSender(
            user_id=user_id,
            username=username,
            role=role,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Segment normalisation: OB11 wire format → platform-agnostic
    # ------------------------------------------------------------------

    def _parse_segments(self, raw_message: object) -> list[MessageSegment]:
        if isinstance(raw_message, str):
            text = raw_message.strip()
            if not text:
                return []
            return [MessageSegment(type=SegmentType.TEXT, data={"text": text})]
        if not isinstance(raw_message, list):
            return []

        segments: list[MessageSegment] = []
        for item in cast(list[object], raw_message):
            if not isinstance(item, dict):
                continue
            raw = cast(dict[object, object], item)
            ob11_type = self._string(raw.get("type")) or "unknown"
            data = self._value_map(raw.get("data"))
            segments.append(self._normalize_segment(ob11_type, data))
        return segments

    def _normalize_segment(self, ob11_type: str, data: ValueMap) -> MessageSegment:
        """Map an OB11 wire-format segment to a platform-agnostic MessageSegment."""
        if ob11_type == OneBotV11SegmentType.TEXT:
            return MessageSegment(type=SegmentType.TEXT, data=data)

        if ob11_type == OneBotV11SegmentType.AT:
            # OB11 uses "qq" for user_id; normalise to "user_id"
            qq = self._string(data.get("qq")) or ""
            return MessageSegment(type=SegmentType.MENTION, data={"user_id": qq})

        if ob11_type == OneBotV11SegmentType.REPLY:
            # OB11 uses "id" for the referenced message; normalise to "message_id"
            msg_id = self._string(data.get("id")) or ""
            return MessageSegment(type=SegmentType.REPLY, data={"message_id": msg_id})

        if ob11_type == OneBotV11SegmentType.IMAGE:
            return MessageSegment(type=SegmentType.IMAGE, data=data)

        if ob11_type == OneBotV11SegmentType.RECORD:
            return MessageSegment(type=SegmentType.VOICE, data=data)

        if ob11_type == OneBotV11SegmentType.VIDEO:
            return MessageSegment(type=SegmentType.VIDEO, data=data)

        if ob11_type == OneBotV11SegmentType.FACE:
            return MessageSegment(type=SegmentType.STICKER, data=data)

        if ob11_type == "mface":
            return MessageSegment(type=SegmentType.STICKER, data=data)

        if ob11_type == OneBotV11SegmentType.FORWARD:
            return MessageSegment(type=SegmentType.FORWARD, data=data)

        if ob11_type in (OneBotV11SegmentType.JSON, OneBotV11SegmentType.XML):
            return MessageSegment(type=SegmentType.CARD, data={**data, "card_type": ob11_type})

        if ob11_type == "poke":
            return MessageSegment(type=SegmentType.POKE, data=data)

        if ob11_type == "location":
            return MessageSegment(type=SegmentType.LOCATION, data=data)

        # Unknown / unhandled — preserve original type for platform-specific use
        return MessageSegment(type=SegmentType.UNKNOWN, data={**data, "original_type": ob11_type})

    # ------------------------------------------------------------------
    # Plain text extraction
    # ------------------------------------------------------------------

    def _resolve_plain_text(
        self,
        raw_event: ValueMap,
        segments: list[MessageSegment],
    ) -> str | None:
        message = raw_event.get("message")
        if isinstance(message, str):
            raw = raw_event.get("raw_message")
            src = raw if isinstance(raw, str) else message
            return src.strip() or None

        # Array format: only text segments
        text_parts: list[str] = []
        for segment in segments:
            if segment.type == SegmentType.TEXT:
                text = segment.data.get("text")
                if isinstance(text, str) and text:
                    text_parts.append(text)
        return "".join(text_parts).strip() or None

    def _describe_segments(self, segments: list[MessageSegment]) -> str:
        _LABELS: dict[str, str] = {
            SegmentType.IMAGE: "[图片]",
            SegmentType.VIDEO: "[视频]",
            SegmentType.VOICE: "[语音]",
            SegmentType.FILE: "[文件]",
            SegmentType.STICKER: "[表情]",
            SegmentType.FORWARD: "[合并转发]",
            SegmentType.CARD: "[卡片]",
            SegmentType.POKE: "[戳一戳]",
            SegmentType.LOCATION: "[位置]",
        }
        parts: list[str] = []
        for seg in segments:
            if seg.type == SegmentType.TEXT:
                text = seg.data.get("text", "")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            elif seg.type == SegmentType.STICKER:
                summary = seg.data.get("summary", "")
                parts.append(summary if isinstance(summary, str) and summary else "[表情]")
            elif seg.type == SegmentType.MENTION:
                uid = seg.data.get("user_id", "")
                parts.append(f"[@{uid}]")
            else:
                parts.append(_LABELS.get(seg.type, f"[{seg.type}]"))
        return " ".join(parts) if parts else "[空消息]"

    # ------------------------------------------------------------------
    # Type coercions
    # ------------------------------------------------------------------

    def _string(self, value: object) -> str | None:
        if isinstance(value, str):
            return value
        if isinstance(value, int):
            return str(value)
        return None

    def _integer(self, value: object) -> int | None:
        return value if isinstance(value, int) else None

    def _value_map(self, value: object) -> ValueMap:
        if not isinstance(value, dict):
            return {}
        raw = cast(dict[object, object], value)
        return {str(key): item for key, item in raw.items() if isinstance(key, str)}
