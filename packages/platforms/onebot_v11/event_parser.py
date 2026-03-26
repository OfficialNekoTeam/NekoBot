from __future__ import annotations

from typing import cast

from .types import (
    OneBotV11Event,
    OneBotV11EventType,
    OneBotV11MessageSegment,
    OneBotV11Scene,
    OneBotV11Sender,
    ValueMap,
)


class OneBotV11EventParser:
    def parse(
        self,
        raw_event: ValueMap,
        *,
        platform_instance_uuid: str,
    ) -> OneBotV11Event:
        post_type = (
            self._string(raw_event.get("post_type")) or OneBotV11EventType.MESSAGE
        )
        event_name = self._build_event_name(raw_event)
        scene = self._resolve_scene(raw_event)
        user_id = self._string(raw_event.get("user_id"))
        group_id = self._string(raw_event.get("group_id"))
        self_id = self._string(raw_event.get("self_id"))
        message_id = self._string(raw_event.get("message_id"))
        segments = self._parse_segments(raw_event.get("message"))
        plain_text = self._resolve_plain_text(raw_event, segments)

        return OneBotV11Event(
            event_type=post_type,
            event_name=event_name,
            scene=scene,
            platform_instance_uuid=platform_instance_uuid,
            self_id=self_id,
            message_id=message_id,
            user_id=user_id,
            group_id=group_id,
            chat_id=self._resolve_chat_id(scene, user_id, group_id),
            sub_type=self._string(raw_event.get("sub_type")),
            post_type=post_type,
            detail_type=self._resolve_detail_type(raw_event),
            time=self._integer(raw_event.get("time")),
            plain_text=plain_text,
            sender=self._parse_sender(raw_event.get("sender")),
            segments=segments,
            raw_event=dict(raw_event),
            metadata={
                "message_type": self._string(raw_event.get("message_type")),
                "notice_type": self._string(raw_event.get("notice_type")),
                "request_type": self._string(raw_event.get("request_type")),
                "meta_event_type": self._string(raw_event.get("meta_event_type")),
            },
        )

    def _build_event_name(self, raw_event: ValueMap) -> str:
        post_type = self._string(raw_event.get("post_type")) or "message"
        if post_type == OneBotV11EventType.MESSAGE:
            message_type = (
                self._string(raw_event.get("message_type")) or OneBotV11Scene.PRIVATE
            )
            return f"message.{message_type}"
        if post_type == OneBotV11EventType.NOTICE:
            notice_type = self._string(raw_event.get("notice_type")) or "unknown"
            return f"notice.{notice_type}"
        if post_type == OneBotV11EventType.REQUEST:
            request_type = self._string(raw_event.get("request_type")) or "unknown"
            return f"request.{request_type}"
        if post_type == OneBotV11EventType.META_EVENT:
            meta_event_type = (
                self._string(raw_event.get("meta_event_type")) or "unknown"
            )
            return f"meta_event.{meta_event_type}"
        return post_type

    def _resolve_scene(self, raw_event: ValueMap) -> str:
        message_type = self._string(raw_event.get("message_type"))
        if message_type == OneBotV11Scene.GROUP:
            return OneBotV11Scene.GROUP
        if message_type == OneBotV11Scene.PRIVATE:
            return OneBotV11Scene.PRIVATE
        post_type = self._string(raw_event.get("post_type"))
        if post_type == OneBotV11EventType.META_EVENT:
            return OneBotV11Scene.SYSTEM
        return OneBotV11Scene.SYSTEM

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
        if scene == OneBotV11Scene.GROUP:
            return group_id
        if scene == OneBotV11Scene.PRIVATE:
            return user_id
        return group_id or user_id

    def _parse_sender(self, sender: object) -> OneBotV11Sender | None:
        if not isinstance(sender, dict):
            return None
        raw = cast(dict[object, object], sender)
        age = raw.get("age")
        return OneBotV11Sender(
            user_id=self._string(raw.get("user_id")),
            nickname=self._string(raw.get("nickname")),
            card=self._string(raw.get("card")),
            role=self._string(raw.get("role")),
            sex=self._string(raw.get("sex")),
            age=age if isinstance(age, int) else None,
            metadata={
                str(key): value for key, value in raw.items() if isinstance(key, str)
            },
        )

    def _parse_segments(self, raw_message: object) -> list[OneBotV11MessageSegment]:
        if not isinstance(raw_message, list):
            return []

        segments: list[OneBotV11MessageSegment] = []
        for item in cast(list[object], raw_message):
            if not isinstance(item, dict):
                continue
            raw = cast(dict[object, object], item)
            segment_type = self._string(raw.get("type")) or "unknown"
            data = raw.get("data")
            segments.append(
                OneBotV11MessageSegment(
                    type=segment_type,
                    data=self._value_map(data),
                )
            )
        return segments

    def _resolve_plain_text(
        self,
        raw_event: ValueMap,
        segments: list[OneBotV11MessageSegment],
    ) -> str | None:
        raw_message = raw_event.get("raw_message")
        if isinstance(raw_message, str):
            stripped = raw_message.strip()
            return stripped or None

        text_parts: list[str] = []
        for segment in segments:
            if segment.type == "text":
                text = segment.data.get("text")
                if isinstance(text, str) and text:
                    text_parts.append(text)
        if not text_parts:
            return None
        return "".join(text_parts).strip() or None

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
