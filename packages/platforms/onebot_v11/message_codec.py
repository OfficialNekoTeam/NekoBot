from __future__ import annotations

from typing import cast

from .types import OneBotV11MessageSegment, OneBotV11SegmentType, ValueMap


class OneBotV11MessageCodec:
    def decode(self, raw_message: object) -> list[OneBotV11MessageSegment]:
        if not isinstance(raw_message, list):
            return []

        segments: list[OneBotV11MessageSegment] = []
        for item in cast(list[object], raw_message):
            if not isinstance(item, dict):
                continue
            raw = cast(dict[object, object], item)
            segment_type = raw.get("type")
            data = raw.get("data")
            segments.append(
                OneBotV11MessageSegment(
                    type=segment_type
                    if isinstance(segment_type, str)
                    else OneBotV11SegmentType.UNKNOWN,
                    data=self._value_map(data),
                )
            )
        return segments

    def encode(
        self, segments: list[OneBotV11MessageSegment]
    ) -> list[dict[str, object]]:
        payloads: list[dict[str, object]] = []
        for segment in segments:
            encoded = self._encode_segment(segment)
            if encoded is None:
                continue
            payloads.append(encoded)
            if segment.type == OneBotV11SegmentType.AT:
                payloads.append({"type": "text", "data": {"text": " "}})
        return payloads

    def text(self, text: str) -> OneBotV11MessageSegment:
        return OneBotV11MessageSegment(
            type=OneBotV11SegmentType.TEXT,
            data={"text": text},
        )

    def at(self, user_id: str) -> OneBotV11MessageSegment:
        return OneBotV11MessageSegment(
            type=OneBotV11SegmentType.AT,
            data={"qq": user_id},
        )

    def reply(self, message_id: str) -> OneBotV11MessageSegment:
        return OneBotV11MessageSegment(
            type=OneBotV11SegmentType.REPLY,
            data={"id": message_id},
        )

    def image(self, file: str) -> OneBotV11MessageSegment:
        return OneBotV11MessageSegment(
            type=OneBotV11SegmentType.IMAGE,
            data={"file": file},
        )

    def record(self, file: str) -> OneBotV11MessageSegment:
        """语音消息 segment。file 可为 URL、本地路径或 base64://... 格式。"""
        return OneBotV11MessageSegment(
            type="record",
            data={"file": file},
        )

    def _encode_segment(
        self, segment: OneBotV11MessageSegment
    ) -> dict[str, object] | None:
        if segment.type == OneBotV11SegmentType.TEXT:
            text = segment.data.get("text")
            if isinstance(text, str) and text.strip():
                return {"type": "text", "data": {"text": text}}
            return None

        if segment.type == OneBotV11SegmentType.AT:
            qq = segment.data.get("qq") or segment.data.get("user_id")
            if isinstance(qq, str):
                return {"type": "at", "data": {"qq": qq}}
            return None

        if segment.type == OneBotV11SegmentType.REPLY:
            message_id = segment.data.get("id") or segment.data.get("message_id")
            if isinstance(message_id, str):
                return {"type": "reply", "data": {"id": message_id}}
            return None

        if segment.type == OneBotV11SegmentType.IMAGE:
            file = segment.data.get("file")
            if isinstance(file, str) and file:
                return {"type": "image", "data": {"file": file}}
            return None

        if segment.type and segment.type != OneBotV11SegmentType.UNKNOWN:
            return {"type": segment.type, "data": dict(segment.data)}

        return None

    def _value_map(self, value: object) -> ValueMap:
        if not isinstance(value, dict):
            return {}
        raw = cast(dict[object, object], value)
        return {str(key): item for key, item in raw.items() if isinstance(key, str)}
