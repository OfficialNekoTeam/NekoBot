from __future__ import annotations

from typing import cast

from loguru import logger

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
        post_type = self._string(raw_event.get("post_type")) or "unknown"
        scene = self._resolve_scene(raw_event)
        event_name = self._build_event_name(raw_event, scene)
        user_id = self._string(raw_event.get("user_id"))
        group_id = self._string(raw_event.get("group_id"))
        self_id = self._string(raw_event.get("self_id"))
        message_id = self._string(raw_event.get("message_id"))
        segments = self._parse_segments(raw_event.get("message"))
        plain_text = self._resolve_plain_text(raw_event, segments)
        sender = self._parse_sender(raw_event.get("sender"))
        if sender is None and user_id is not None:
            sender = OneBotV11Sender(user_id=user_id)

        event = OneBotV11Event(
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
            sender=sender,
            segments=segments,
            raw_event=dict(raw_event),
            metadata={
                "message_type": self._string(raw_event.get("message_type")),
                "notice_type": self._string(raw_event.get("notice_type")),
                "request_type": self._string(raw_event.get("request_type")),
                "meta_event_type": self._string(raw_event.get("meta_event_type")),
            },
        )
        if post_type == OneBotV11EventType.MESSAGE:
            nickname = sender.nickname or sender.user_id if sender else user_id
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
            meta_event_type = (
                self._string(raw_event.get("meta_event_type")) or "unknown"
            )
            base = f"meta_event.{meta_event_type}"
            return f"{base}.{sub_type}" if sub_type else base
        return post_type

    def _resolve_scene(self, raw_event: ValueMap) -> str:
        message_type = self._string(raw_event.get("message_type"))
        if message_type == OneBotV11Scene.GROUP:
            return OneBotV11Scene.GROUP
        if message_type == OneBotV11Scene.PRIVATE:
            return OneBotV11Scene.PRIVATE
        if self._string(raw_event.get("group_id")) is not None:
            return OneBotV11Scene.GROUP
        if self._string(raw_event.get("user_id")) is not None:
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
        if isinstance(raw_message, str):
            text = raw_message.strip()
            if not text:
                return []
            return [OneBotV11MessageSegment(type="text", data={"text": text})]
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
        # 如果 message 是字符串格式（非 array），直接用 raw_message
        message = raw_event.get("message")
        if isinstance(message, str):
            raw = raw_event.get("raw_message")
            src = raw if isinstance(raw, str) else message
            return src.strip() or None

        # array 格式：只取 text 类型 segment，忽略 CQ 码
        text_parts: list[str] = []
        for segment in segments:
            if segment.type == "text":
                text = segment.data.get("text")
                if isinstance(text, str) and text:
                    text_parts.append(text)
        return "".join(text_parts).strip() or None

    def _describe_segments(self, segments: list[OneBotV11MessageSegment]) -> str:
        _LABELS: dict[str, str] = {
            "image": "[图片]",
            "video": "[视频]",
            "record": "[语音]",
            "file": "[文件]",
            "face": "[表情]",
            "mface": "[商城表情]",
            "at": "[at]",
            "reply": "[回复]",
            "forward": "[合并转发]",
            "json": "[卡片]",
            "xml": "[XML]",
            "poke": "[戳一戳]",
            "location": "[位置]",
            "contact": "[名片]",
            "markdown": "[Markdown]",
            "miniapp": "[小程序]",
        }
        parts: list[str] = []
        for seg in segments:
            if seg.type == "text":
                text = seg.data.get("text", "")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            elif seg.type == "mface":
                summary = seg.data.get("summary", "")
                parts.append(
                    summary if isinstance(summary, str) and summary else "[商城表情]"
                )
            elif seg.type == "at":
                qq = seg.data.get("qq", "")
                parts.append(f"[@{qq}]")
            else:
                parts.append(_LABELS.get(seg.type, f"[{seg.type}]"))
        return " ".join(parts) if parts else "[空消息]"

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
