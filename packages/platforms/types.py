from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

ValueMap: TypeAlias = dict[str, object]


class EventType:
    MESSAGE = "message"
    NOTICE = "notice"
    REQUEST = "request"
    META_EVENT = "meta_event"


class Scene:
    PRIVATE = "private"
    GROUP = "group"
    CHANNEL = "channel"
    SYSTEM = "system"


class SegmentType:
    TEXT = "text"
    MENTION = "mention"    # @user  (OB11: at)
    REPLY = "reply"        # quote/reply
    IMAGE = "image"
    VOICE = "voice"        # audio  (OB11: record)
    VIDEO = "video"
    FILE = "file"
    STICKER = "sticker"    # emoji / face  (OB11: face, mface)
    FORWARD = "forward"    # forwarded message chain
    CARD = "card"          # rich card  (OB11: json, xml)
    POKE = "poke"
    LOCATION = "location"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PlatformSender:
    """Platform-agnostic sender/actor metadata."""

    user_id: str | None = None
    username: str | None = None    # display name (nickname / card / first_name …)
    role: str | None = None        # group role: owner / admin / member
    metadata: ValueMap = field(default_factory=dict)


@dataclass(frozen=True)
class MessageSegment:
    """Platform-agnostic message segment using unified SegmentType values."""

    type: str
    data: ValueMap = field(default_factory=dict)


@dataclass(frozen=True)
class PlatformEvent:
    """Unified event model shared across all platform adapters.

    Platform-specific details are preserved in *metadata* and *raw_event*
    so adapters can still access them without polluting the common interface.
    """

    event_type: str                       # EventType.*
    event_name: str                       # hierarchical: "message.group.normal"
    scene: str                            # Scene.*
    platform: str                         # "onebot" | "telegram" | …
    platform_instance_uuid: str | None = None
    self_id: str | None = None            # bot's own id on this platform
    user_id: str | None = None            # actor who triggered the event
    group_id: str | None = None
    chat_id: str | None = None
    message_id: str | None = None
    plain_text: str | None = None
    sender: PlatformSender | None = None
    segments: list[MessageSegment] = field(default_factory=list)
    raw_event: ValueMap = field(default_factory=dict)    # original platform payload
    metadata: ValueMap = field(default_factory=dict)     # platform-specific extras
