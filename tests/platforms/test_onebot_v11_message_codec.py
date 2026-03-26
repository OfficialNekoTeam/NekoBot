from __future__ import annotations

from packages.platforms.onebot_v11.message_codec import OneBotV11MessageCodec
from packages.platforms.onebot_v11.types import (
    OneBotV11MessageSegment,
    OneBotV11SegmentType,
)


def test_decode_converts_raw_segments_to_normalized_segments() -> None:
    codec = OneBotV11MessageCodec()
    raw_message = [
        {"type": "text", "data": {"text": "hello"}},
        {"type": "reply", "data": {"id": "123"}},
    ]

    segments = codec.decode(raw_message)

    assert segments == [
        OneBotV11MessageSegment(type="text", data={"text": "hello"}),
        OneBotV11MessageSegment(type="reply", data={"id": "123"}),
    ]


def test_encode_emits_supported_onebot_segments() -> None:
    codec = OneBotV11MessageCodec()
    payload = codec.encode(
        [
            codec.text("hello"),
            codec.at("10001"),
            codec.reply("42"),
            codec.image("base64://image"),
        ]
    )

    assert payload[0] == {"type": "text", "data": {"text": "hello"}}
    assert payload[1] == {"type": "at", "data": {"qq": "10001"}}
    assert payload[2] == {"type": "text", "data": {"text": " "}}
    assert payload[3] == {"type": "reply", "data": {"id": "42"}}
    assert payload[4] == {"type": "image", "data": {"file": "base64://image"}}


def test_encode_skips_blank_text_segments() -> None:
    codec = OneBotV11MessageCodec()
    payload = codec.encode(
        [
            OneBotV11MessageSegment(
                type=OneBotV11SegmentType.TEXT, data={"text": "   "}
            ),
            codec.text("ok"),
        ]
    )

    assert payload == [{"type": "text", "data": {"text": "ok"}}]
