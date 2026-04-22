from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

ValueMap: TypeAlias = dict[str, object]


# ---------------------------------------------------------------------------
# OneBot V11 protocol constants
# ---------------------------------------------------------------------------


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
    """Wire-format segment type names used by the OneBot V11 protocol.

    These reflect the raw JSON segment types sent over the wire.  Inbound
    events are normalised to platform-agnostic SegmentType values
    (packages.platforms.types.SegmentType) by the event parser.
    """

    TEXT: str = "text"
    AT: str = "at"
    REPLY: str = "reply"
    IMAGE: str = "image"
    RECORD: str = "record"
    VIDEO: str = "video"
    FACE: str = "face"
    FORWARD: str = "forward"
    JSON: str = "json"
    XML: str = "xml"
    UNKNOWN: str = "unknown"


# ---------------------------------------------------------------------------
# Outbound (codec / sending) types — OneBot V11 specific
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OneBotV11MessageSegment:
    """Raw OneBot V11 message segment used by the message codec for encoding
    outbound messages.  Inbound events use the platform-agnostic
    MessageSegment from packages.platforms.types instead.
    """

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
