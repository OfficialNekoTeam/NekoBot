from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

ValueMap: TypeAlias = dict[str, object]


class OneBotV11EventType:
    MESSAGE: str = "message"
    NOTICE: str = "notice"
    REQUEST: str = "request"
    META_EVENT: str = "meta_event"


class OneBotV11Scene:
    PRIVATE: str = "private"
    GROUP: str = "group"
    CHANNEL: str = "channel"
    SYSTEM: str = "system"


class OneBotV11SegmentType:
    TEXT: str = "text"
    AT: str = "at"
    REPLY: str = "reply"
    IMAGE: str = "image"
    UNKNOWN: str = "unknown"


@dataclass(frozen=True)
class OneBotV11Sender:
    user_id: str | None = None
    nickname: str | None = None
    card: str | None = None
    role: str | None = None
    sex: str | None = None
    age: int | None = None
    metadata: ValueMap = field(default_factory=dict)


@dataclass(frozen=True)
class OneBotV11MessageSegment:
    type: str
    data: ValueMap = field(default_factory=dict)


@dataclass(frozen=True)
class OneBotV11OutboundTarget:
    scene: str
    chat_id: str
    user_id: str | None = None
    group_id: str | None = None
    message_id: str | None = None
    reply_to_message_id: str | None = None
    metadata: ValueMap = field(default_factory=dict)


@dataclass(frozen=True)
class OneBotV11Event:
    event_type: str
    event_name: str
    scene: str
    platform: str = "onebot"
    platform_instance_uuid: str | None = None
    self_id: str | None = None
    message_id: str | None = None
    user_id: str | None = None
    group_id: str | None = None
    chat_id: str | None = None
    sub_type: str | None = None
    post_type: str | None = None
    detail_type: str | None = None
    time: int | None = None
    plain_text: str | None = None
    sender: OneBotV11Sender | None = None
    segments: list[OneBotV11MessageSegment] = field(default_factory=list)
    raw_event: ValueMap = field(default_factory=dict)
    metadata: ValueMap = field(default_factory=dict)
