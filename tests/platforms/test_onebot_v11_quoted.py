"""Tests for OneBotV11Dispatcher._analyze_quoted_message and
_extract_forward_text — image extraction, reply-to-self detection,
forward message parsing including nested forwards."""
from __future__ import annotations

from packages.app import NekoBotFramework
from packages.platforms.onebot_v11.dispatch import OneBotV11Dispatcher
from packages.platforms.onebot_v11.message_codec import OneBotV11MessageCodec
from packages.platforms.types import MessageSegment, PlatformEvent, Scene, SegmentType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dispatcher(
    *,
    fetch_msg_responses: dict[str, dict[str, object]] | None = None,
    fetch_fwd_responses: dict[str, dict[str, object]] | None = None,
) -> OneBotV11Dispatcher:
    """Build a dispatcher with optional stub API callables."""
    fw = NekoBotFramework()

    async def send_callable(target: object, segments: object) -> dict[str, object]:
        return {"status": "ok", "data": {"message_id": 1}}

    async def fetch_message_callable(msg_id: str) -> dict[str, object]:
        if fetch_msg_responses is None:
            return {"status": "ok", "data": {}}
        return fetch_msg_responses.get(msg_id, {"status": "ok", "data": {}})

    async def fetch_forward_callable(fwd_id: str) -> dict[str, object]:
        if fetch_fwd_responses is None:
            return {"status": "ok", "data": {}}
        return fetch_fwd_responses.get(fwd_id, {"status": "ok", "data": {}})

    return OneBotV11Dispatcher(
        fw,
        send_callable=send_callable,  # type: ignore[arg-type]
        message_codec=OneBotV11MessageCodec(),
        fetch_message_callable=fetch_message_callable,
        fetch_forward_callable=fetch_forward_callable,
    )


def _seg(type_: str, **data: object) -> MessageSegment:
    return MessageSegment(type=type_, data=dict(data))  # type: ignore[arg-type]


def _event(
    segments: list[MessageSegment] | None = None,
    *,
    self_id: str = "bot-99",
    plain_text: str = "",
) -> PlatformEvent:
    return PlatformEvent(
        event_type="message",
        event_name="message.group",
        scene=Scene.GROUP,
        platform="onebot",
        platform_instance_uuid="inst-1",
        self_id=self_id,
        user_id="user-1",
        group_id="group-1",
        chat_id="group-1",
        message_id="msg-1",
        plain_text=plain_text,
        segments=segments or [],
    )


# ===========================================================================
# Direct image segments
# ===========================================================================


async def test_image_url_from_direct_segment() -> None:
    dispatcher = _make_dispatcher()
    event = _event(segments=[
        _seg(SegmentType.IMAGE, url="https://cdn.example.com/img.jpg", file="img.jpg"),
    ])
    result = await dispatcher._analyze_quoted_message(event)
    assert "https://cdn.example.com/img.jpg" in result["image_urls"]


async def test_image_with_no_http_url_ignored() -> None:
    """file:// or local paths should not be added."""
    dispatcher = _make_dispatcher()
    event = _event(segments=[
        _seg(SegmentType.IMAGE, file="somefile.image", url=""),
    ])
    result = await dispatcher._analyze_quoted_message(event)
    assert result["image_urls"] == []


async def test_no_segments_returns_empty() -> None:
    dispatcher = _make_dispatcher()
    result = await dispatcher._analyze_quoted_message(_event())
    assert result["image_urls"] == []
    assert result["is_reply_to_self"] is False
    assert result["quoted_text"] is None


# ===========================================================================
# Reply segment — is_reply_to_self detection
# ===========================================================================


async def test_reply_to_self_detected_via_user_id() -> None:
    """When the original message's top-level user_id matches self_id → is_reply_to_self."""
    dispatcher = _make_dispatcher(
        fetch_msg_responses={
            "msg-42": {
                "status": "ok",
                "data": {
                    "user_id": "bot-99",
                    "message": [{"type": "text", "data": {"text": "I said this"}}],
                },
            }
        }
    )
    event = _event(
        segments=[_seg(SegmentType.REPLY, message_id="msg-42")],
        self_id="bot-99",
    )
    result = await dispatcher._analyze_quoted_message(event)
    assert result["is_reply_to_self"] is True


async def test_reply_to_self_detected_via_sender_user_id() -> None:
    """Fallback: sender.user_id when top-level user_id is missing."""
    dispatcher = _make_dispatcher(
        fetch_msg_responses={
            "msg-10": {
                "status": "ok",
                "data": {
                    "sender": {"user_id": "bot-99", "nickname": "Bot"},
                    "message": [],
                },
            }
        }
    )
    event = _event(segments=[_seg(SegmentType.REPLY, message_id="msg-10")], self_id="bot-99")
    result = await dispatcher._analyze_quoted_message(event)
    assert result["is_reply_to_self"] is True


async def test_reply_to_other_user_not_self() -> None:
    dispatcher = _make_dispatcher(
        fetch_msg_responses={
            "msg-5": {
                "status": "ok",
                "data": {
                    "user_id": "user-123",
                    "message": [],
                },
            }
        }
    )
    event = _event(segments=[_seg(SegmentType.REPLY, message_id="msg-5")], self_id="bot-99")
    result = await dispatcher._analyze_quoted_message(event)
    assert result["is_reply_to_self"] is False


async def test_reply_extracts_text_from_original_message() -> None:
    dispatcher = _make_dispatcher(
        fetch_msg_responses={
            "msg-7": {
                "status": "ok",
                "data": {
                    "user_id": "user-1",
                    "message": [{"type": "text", "data": {"text": "original text"}}],
                },
            }
        }
    )
    event = _event(segments=[_seg(SegmentType.REPLY, message_id="msg-7")])
    result = await dispatcher._analyze_quoted_message(event)
    assert result["quoted_text"] == "original text"


async def test_reply_extracts_image_from_original_message() -> None:
    dispatcher = _make_dispatcher(
        fetch_msg_responses={
            "msg-8": {
                "status": "ok",
                "data": {
                    "user_id": "user-1",
                    "message": [
                        {"type": "image", "data": {"url": "https://cdn.example.com/x.jpg"}}
                    ],
                },
            }
        }
    )
    event = _event(segments=[_seg(SegmentType.REPLY, message_id="msg-8")])
    result = await dispatcher._analyze_quoted_message(event)
    assert "https://cdn.example.com/x.jpg" in result["image_urls"]


# ===========================================================================
# Forward segment detection
# ===========================================================================


async def test_forward_segment_triggers_get_forward_msg() -> None:
    """When get_msg returns a forward segment, get_forward_msg is called with the forward ID."""
    fetched_forward_ids: list[str] = []

    fw = NekoBotFramework()

    async def send_callable(t: object, s: object) -> dict[str, object]:
        return {"status": "ok", "data": {"message_id": 1}}

    async def fetch_message_callable(msg_id: str) -> dict[str, object]:
        return {
            "status": "ok",
            "data": {
                "user_id": "user-1",
                "message": [{"type": "forward", "data": {"id": "fwd-001"}}],
            },
        }

    async def fetch_forward_callable(fwd_id: str) -> dict[str, object]:
        fetched_forward_ids.append(fwd_id)
        return {
            "status": "ok",
            "data": {
                "messages": [
                    {
                        "sender": {"nickname": "Alice", "user_id": "100"},
                        "message": [{"type": "text", "data": {"text": "forward content"}}],
                    }
                ]
            },
        }

    dispatcher = OneBotV11Dispatcher(
        fw,
        send_callable=send_callable,  # type: ignore[arg-type]
        message_codec=OneBotV11MessageCodec(),
        fetch_message_callable=fetch_message_callable,
        fetch_forward_callable=fetch_forward_callable,
    )
    event = _event(segments=[_seg(SegmentType.REPLY, message_id="msg-fwd")])
    result = await dispatcher._analyze_quoted_message(event)

    assert "fwd-001" in fetched_forward_ids
    assert result["quoted_text"] is not None
    assert "Alice" in result["quoted_text"]
    assert "forward content" in result["quoted_text"]


# ===========================================================================
# _extract_forward_text — node parsing
# ===========================================================================


async def test_extract_forward_text_basic_nodes() -> None:
    dispatcher = _make_dispatcher(
        fetch_fwd_responses={
            "fwd-1": {
                "status": "ok",
                "data": {
                    "messages": [
                        {
                            "sender": {"nickname": "Alice"},
                            "message": [{"type": "text", "data": {"text": "hello"}}],
                        },
                        {
                            "sender": {"nickname": "Bob"},
                            "message": [{"type": "text", "data": {"text": "world"}}],
                        },
                    ]
                },
            }
        }
    )
    text = await dispatcher._extract_forward_text("fwd-1")
    assert text is not None
    assert "Alice" in text
    assert "hello" in text
    assert "Bob" in text
    assert "world" in text


async def test_extract_forward_text_sender_fallback_card() -> None:
    """Sender name falls back: nickname → card → user_id."""
    dispatcher = _make_dispatcher(
        fetch_fwd_responses={
            "fwd-2": {
                "status": "ok",
                "data": {
                    "messages": [
                        {
                            "sender": {"nickname": "", "card": "CardName", "user_id": "999"},
                            "message": [{"type": "text", "data": {"text": "hi"}}],
                        },
                    ]
                },
            }
        }
    )
    text = await dispatcher._extract_forward_text("fwd-2")
    assert text is not None
    assert "CardName" in text


async def test_extract_forward_text_sender_fallback_user_id() -> None:
    dispatcher = _make_dispatcher(
        fetch_fwd_responses={
            "fwd-3": {
                "status": "ok",
                "data": {
                    "messages": [
                        {
                            "sender": {"user_id": "12345"},
                            "message": [{"type": "text", "data": {"text": "hey"}}],
                        },
                    ]
                },
            }
        }
    )
    text = await dispatcher._extract_forward_text("fwd-3")
    assert text is not None
    assert "12345" in text


async def test_extract_forward_text_content_field_alias() -> None:
    """Nodes may use 'content' instead of 'message'."""
    dispatcher = _make_dispatcher(
        fetch_fwd_responses={
            "fwd-4": {
                "status": "ok",
                "data": {
                    "messages": [
                        {
                            "sender": {"nickname": "Carol"},
                            "content": [{"type": "text", "data": {"text": "using content field"}}],
                        },
                    ]
                },
            }
        }
    )
    text = await dispatcher._extract_forward_text("fwd-4")
    assert text is not None
    assert "using content field" in text


async def test_extract_forward_text_nodes_field_alias() -> None:
    """Top-level data may use 'nodes' instead of 'messages'."""
    dispatcher = _make_dispatcher(
        fetch_fwd_responses={
            "fwd-5": {
                "status": "ok",
                "data": {
                    "nodes": [
                        {
                            "sender": {"nickname": "Dave"},
                            "message": [{"type": "text", "data": {"text": "via nodes field"}}],
                        },
                    ]
                },
            }
        }
    )
    text = await dispatcher._extract_forward_text("fwd-5")
    assert text is not None
    assert "via nodes field" in text


async def test_extract_forward_text_image_segment_placeholder() -> None:
    dispatcher = _make_dispatcher(
        fetch_fwd_responses={
            "fwd-6": {
                "status": "ok",
                "data": {
                    "messages": [
                        {
                            "sender": {"nickname": "Eve"},
                            "message": [{"type": "image", "data": {"url": "https://img"}}],
                        },
                    ]
                },
            }
        }
    )
    text = await dispatcher._extract_forward_text("fwd-6")
    assert text is not None
    assert "[图片]" in text


async def test_extract_forward_text_nested_forward_recursion() -> None:
    """Nested forward segment with id triggers recursive fetch."""
    dispatcher = _make_dispatcher(
        fetch_fwd_responses={
            "fwd-outer": {
                "status": "ok",
                "data": {
                    "messages": [
                        {
                            "sender": {"nickname": "Outer"},
                            "message": [{"type": "forward", "data": {"id": "fwd-inner"}}],
                        },
                    ]
                },
            },
            "fwd-inner": {
                "status": "ok",
                "data": {
                    "messages": [
                        {
                            "sender": {"nickname": "Inner"},
                            "message": [{"type": "text", "data": {"text": "nested text"}}],
                        },
                    ]
                },
            },
        }
    )
    text = await dispatcher._extract_forward_text("fwd-outer")
    assert text is not None
    assert "nested text" in text


async def test_extract_forward_text_cycle_prevention() -> None:
    """Circular forward references must not cause infinite recursion."""
    dispatcher = _make_dispatcher(
        fetch_fwd_responses={
            "fwd-a": {
                "status": "ok",
                "data": {
                    "messages": [
                        {
                            "sender": {"nickname": "A"},
                            "message": [{"type": "forward", "data": {"id": "fwd-b"}}],
                        }
                    ]
                },
            },
            "fwd-b": {
                "status": "ok",
                "data": {
                    "messages": [
                        {
                            "sender": {"nickname": "B"},
                            "message": [{"type": "forward", "data": {"id": "fwd-a"}}],
                        }
                    ]
                },
            },
        }
    )
    # Must not raise / hang
    await dispatcher._extract_forward_text("fwd-a")
    # Result may be None or truncated — just must complete


async def test_extract_forward_text_empty_data_returns_none() -> None:
    dispatcher = _make_dispatcher(
        fetch_fwd_responses={"fwd-empty": {"status": "ok", "data": {"messages": []}}}
    )
    text = await dispatcher._extract_forward_text("fwd-empty")
    assert text is None


async def test_extract_forward_text_truncated_at_2000_chars() -> None:
    long_text = "x" * 3000
    dispatcher = _make_dispatcher(
        fetch_fwd_responses={
            "fwd-long": {
                "status": "ok",
                "data": {
                    "messages": [
                        {
                            "sender": {"nickname": "Verbose"},
                            "message": [{"type": "text", "data": {"text": long_text}}],
                        }
                    ]
                },
            }
        }
    )
    text = await dispatcher._extract_forward_text("fwd-long")
    assert text is not None
    assert len(text) <= 2000
