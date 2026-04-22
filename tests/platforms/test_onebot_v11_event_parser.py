from __future__ import annotations

from typing import cast

from packages.platforms.onebot_v11.event_parser import OneBotV11EventParser
from packages.platforms.types import Scene, SegmentType
from packages.providers.types import ValueMap


def test_parse_group_message_event_normalizes_core_fields() -> None:
    parser = OneBotV11EventParser()
    raw_event = {
        "post_type": "message",
        "message_type": "group",
        "sub_type": "normal",
        "self_id": 10001,
        "user_id": 20002,
        "group_id": 30003,
        "message_id": 40004,
        "time": 1710000000,
        "raw_message": "hello @bot",
        "message": [
            {"type": "text", "data": {"text": "hello "}},
            {"type": "at", "data": {"qq": "10001"}},
        ],
        "sender": {"user_id": 20002, "nickname": "tester", "role": "member"},
    }

    event = parser.parse(cast(ValueMap, raw_event), platform_instance_uuid="instance-1")

    assert event.event_type == "message"
    assert event.event_name == "message.group.normal"
    assert event.scene == Scene.GROUP
    assert event.platform_instance_uuid == "instance-1"
    assert event.user_id == "20002"
    assert event.group_id == "30003"
    assert event.chat_id == "30003"
    assert event.message_id == "40004"
    assert event.plain_text == "hello"
    assert event.sender is not None
    assert event.sender.username == "tester"
    assert event.segments[0].type == SegmentType.TEXT
    assert event.segments[1].type == SegmentType.MENTION


def test_parse_private_message_falls_back_to_text_from_segments() -> None:
    parser = OneBotV11EventParser()
    raw_event = {
        "post_type": "message",
        "message_type": "private",
        "user_id": "u-1",
        "message": [{"type": "text", "data": {"text": "hello world"}}],
    }

    event = parser.parse(cast(ValueMap, raw_event), platform_instance_uuid="instance-1")

    assert event.scene == Scene.PRIVATE
    assert event.chat_id == "u-1"
    assert event.plain_text == "hello world"


def test_parse_private_friend_message_keeps_concrete_event_name() -> None:
    parser = OneBotV11EventParser()
    raw_event = {
        "post_type": "message",
        "message_type": "private",
        "sub_type": "friend",
        "user_id": 20001,
        "message": "hello friend",
    }

    event = parser.parse(cast(ValueMap, raw_event), platform_instance_uuid="instance-1")

    assert event.scene == Scene.PRIVATE
    assert event.event_name == "message.private.friend"
    assert event.chat_id == "20001"
    assert event.plain_text == "hello friend"


def test_parse_group_message_without_message_type_falls_back_from_group_id() -> None:
    parser = OneBotV11EventParser()
    raw_event = {
        "post_type": "message",
        "group_id": 30003,
        "user_id": 20002,
        "message": "hello group",
    }

    event = parser.parse(cast(ValueMap, raw_event), platform_instance_uuid="instance-1")

    assert event.scene == Scene.GROUP
    assert event.event_name == "message.group"
    assert event.chat_id == "30003"
    assert event.plain_text == "hello group"
    assert event.segments[0].type == SegmentType.TEXT
    assert event.segments[0].data == {"text": "hello group"}


def test_parse_notice_request_and_meta_events_have_expected_names() -> None:
    parser = OneBotV11EventParser()

    notice = parser.parse(
        cast(ValueMap, {"post_type": "notice", "notice_type": "group_increase"}),
        platform_instance_uuid="instance-1",
    )
    request = parser.parse(
        cast(ValueMap, {"post_type": "request", "request_type": "friend"}),
        platform_instance_uuid="instance-1",
    )
    meta = parser.parse(
        cast(ValueMap, {"post_type": "meta_event", "meta_event_type": "heartbeat"}),
        platform_instance_uuid="instance-1",
    )

    assert notice.event_name == "notice.group_increase"
    assert request.event_name == "request.friend"
    assert meta.event_name == "meta_event.heartbeat"
    assert meta.scene == Scene.SYSTEM


def test_parse_notice_event_includes_subtype_when_present() -> None:
    parser = OneBotV11EventParser()

    notice = parser.parse(
        cast(
            ValueMap,
            {
                "post_type": "notice",
                "notice_type": "notify",
                "sub_type": "poke",
            },
        ),
        platform_instance_uuid="instance-1",
    )

    assert notice.event_name == "notice.notify.poke"
