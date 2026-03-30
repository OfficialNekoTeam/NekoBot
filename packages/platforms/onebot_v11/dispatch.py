from __future__ import annotations

import base64
import json
from collections.abc import Awaitable, Callable
from importlib import import_module
from typing import TYPE_CHECKING, Protocol, TypeAlias, cast

import aiohttp
from loguru import logger

from ...app import NekoBotFramework
from ...conversations.context import ConfigurationContext
from ...plugins.base import BasePlugin
from ...providers.types import STTRequest, TTSRequest
from ...runtime.context import ExecutionContext, PluginContext
from .types import (
    OneBotV11Event,
    OneBotV11MessageSegment,
    OneBotV11OutboundTarget,
    OneBotV11Scene,
)

if TYPE_CHECKING:
    from ...llm.handler import LLMHandler

OutboundSender: TypeAlias = Callable[
    [OneBotV11OutboundTarget, list[dict[str, object]]],
    Awaitable[dict[str, object]],
]
DeleteSender: TypeAlias = Callable[[str], Awaitable[dict[str, object]]]
FetchMessageCallable: TypeAlias = Callable[[str], Awaitable[dict[str, object]]]
FetchForwardCallable: TypeAlias = Callable[[str], Awaitable[dict[str, object]]]


class MessageCodecLike(Protocol):
    def text(self, text: str) -> OneBotV11MessageSegment: ...

    def encode(
        self, segments: list[OneBotV11MessageSegment]
    ) -> list[dict[str, object]]: ...


class OneBotV11Dispatcher:
    def __init__(
        self,
        framework: NekoBotFramework,
        *,
        send_callable: OutboundSender,
        delete_callable: DeleteSender | None = None,
        fetch_message_callable: FetchMessageCallable | None = None,
        fetch_forward_callable: FetchForwardCallable | None = None,
        message_codec: MessageCodecLike | None = None,
        llm_handler: LLMHandler | None = None,
    ) -> None:
        self.framework: NekoBotFramework = framework
        self.send_callable: OutboundSender = send_callable
        self.delete_callable: DeleteSender | None = delete_callable
        self.fetch_message_callable: FetchMessageCallable | None = fetch_message_callable
        self.fetch_forward_callable: FetchForwardCallable | None = fetch_forward_callable
        self.llm_handler: LLMHandler | None = llm_handler
        self.message_codec: MessageCodecLike
        if message_codec is None:
            module = import_module("packages.platforms.onebot_v11.message_codec")
            codec_class = cast(
                Callable[[], object], getattr(module, "OneBotV11MessageCodec")
            )
            self.message_codec = cast(MessageCodecLike, codec_class())
        else:
            self.message_codec = message_codec

    def build_execution_context(self, event: OneBotV11Event) -> ExecutionContext:
        roles, group_roles = self._resolve_roles(event)
        return self.framework.build_execution_context(
            event_name=event.event_name,
            actor_id=event.user_id,
            platform=event.platform,
            platform_instance_uuid=event.platform_instance_uuid,
            conversation_id=None,
            chat_id=event.chat_id,
            group_id=event.group_id,
            thread_id=None,
            message_id=event.message_id,
            scope=self._resolve_scope(event),
            roles=roles,
            group_roles=group_roles,
            is_authenticated=bool(event.user_id),
            metadata={
                **event.metadata,
                "onebot_event_type": event.event_type,
                "onebot_scene": event.scene,
                "onebot_self_id": event.self_id,
                "onebot_segments": [
                    {"type": seg.type, "data": dict(seg.data)}
                    for seg in event.segments
                ],
                "onebot_raw_event": event.raw_event,
            },
        )

    def _resolve_roles(
        self, event: OneBotV11Event
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Returns (roles, group_roles) for the event actor."""
        roles: list[str] = []
        group_roles: list[str] = []

        if event.user_id and event.user_id in self.framework.owner_ids:
            roles.append("owner")

        if event.sender is not None:
            sender_role = event.sender.role
            if sender_role == "owner":
                group_roles.append("group_owner")
            elif sender_role == "admin":
                group_roles.append("group_admin")
            elif sender_role == "member":
                group_roles.append("member")

        return tuple(roles), tuple(group_roles)

    def build_reply_target(
        self, event: OneBotV11Event
    ) -> OneBotV11OutboundTarget | None:
        if event.scene == OneBotV11Scene.GROUP and event.group_id is not None:
            return OneBotV11OutboundTarget(
                scene=OneBotV11Scene.GROUP,
                chat_id=event.group_id,
                group_id=event.group_id,
                user_id=event.user_id,
                message_id=event.message_id,
                reply_to_message_id=event.message_id,
            )

        chat_id = event.chat_id or event.user_id
        if chat_id is None:
            return None

        return OneBotV11OutboundTarget(
            scene=OneBotV11Scene.PRIVATE,
            chat_id=chat_id,
            user_id=event.user_id or chat_id,
            message_id=event.message_id,
            reply_to_message_id=event.message_id,
        )

    async def dispatch_event(
        self,
        event: OneBotV11Event,
        configuration: ConfigurationContext | None = None,
    ) -> list[PluginContext]:
        execution = self.build_execution_context(event)
        configuration = configuration or self.framework.build_configuration_context()
        conversation = self.framework.build_conversation_context(
            execution, configuration
        )
        bindings = self.framework.resolve_effective_plugin_bindings(
            configuration,
            execution=execution,
        )
        logger.debug(
            "Dispatching OneBot event: event_name={} scope={} bindings={}",
            event.event_name,
            execution.scope,
            len(bindings),
        )
        contexts: list[PluginContext] = []
        for binding in bindings:
            logger.debug("Dispatch matched plugin: {}", binding.plugin_name)
            plugin_context = self.framework.build_plugin_context(
                plugin_name=binding.plugin_name,
                execution=execution,
                configuration=configuration,
                conversation=conversation,
                binding=binding,
                reply_callable=self._build_reply_callable(event),
                send_voice_callable=self._build_send_voice_callable(event),
            )
            contexts.append(plugin_context)
            await self._dispatch_to_plugin(binding.plugin_name, event, plugin_context)

        # LLM 处理：仅限消息事件，在所有插件命令之后作为兜底响应
        if self.llm_handler is not None and (event.post_type or event.event_type) == "message":
            quoted = await self._analyze_quoted_message(event)
            llm_payload = self._build_payload(event)
            if quoted["image_urls"]:
                llm_payload["image_urls"] = quoted["image_urls"]
            if quoted["is_reply_to_self"]:
                llm_payload["is_reply_to_self"] = True
            if quoted["quoted_text"]:
                llm_payload["quoted_text"] = quoted["quoted_text"]

            # STT：语音消息转文字
            stt_text = await self._transcribe_voice(event, configuration, execution)
            if stt_text:
                llm_payload["plain_text"] = stt_text
                llm_payload["stt_transcribed"] = True
                logger.info("[STT] 语音转文字: {}", stt_text[:80])

            await self.llm_handler.handle(
                payload=llm_payload,
                execution=execution,
                configuration=configuration,
                conversation=conversation,
                reply=self._build_reply_callable(event),
                recall=self._build_recall_callable(event),
            )

        return contexts

    async def _dispatch_to_plugin(
        self,
        plugin_name: str,
        event: OneBotV11Event,
        plugin_context: PluginContext,
    ) -> None:
        registered = self.framework.runtime_registry.plugins.get(plugin_name)
        if registered is None:
            return

        plugin_class = cast(type[BasePlugin], registered.plugin_class)
        plugin = plugin_class(
            plugin_context, schema_registry=self.framework.schema_registry
        )

        # --- 命令路由：O(1) 通过 CommandRegistry 查找 ---
        plain_text = (event.plain_text or "").strip()
        cmd_prefix = self._resolve_command_prefix(plugin_context)
        if plain_text.startswith(cmd_prefix):
            cmd_body = plain_text[len(cmd_prefix):]
            parts = cmd_body.split()
            cmd_name = parts[0].lower() if parts else ""
            cmd_args = parts[1:]
            entry = self.framework.command_registry.resolve(cmd_name)
            if entry is not None and entry.plugin_name == plugin_name:
                handler = getattr(plugin, entry.handler_name, None)
                if callable(handler):
                    logger.info(
                        "[OneBot] 命令分发: {} -> {} (cmd={})",
                        plugin_name,
                        entry.handler_name,
                        cmd_name,
                    )
                    payload = self._build_payload(event)
                    payload["command_name"] = cmd_name
                    payload["command_args"] = cmd_args
                    await cast(
                        Callable[[dict[str, object]], Awaitable[None]], handler
                    )(payload)
                return  # 命令已匹配，不再分发给 event_handlers

        # --- 事件路由 ---
        payload = self._build_payload(event)
        for handler_name, handler_spec in registered.event_handlers:
            if not self._matches_event(handler_spec.event, event.event_name):
                continue
            handler = getattr(plugin, handler_name, None)
            if callable(handler):
                logger.info(
                    "[OneBot] 分发至插件: {} -> {} (event={})",
                    plugin_name,
                    handler_name,
                    event.event_name,
                )
                await cast(Callable[[dict[str, object]], Awaitable[None]], handler)(
                    payload
                )

        await plugin.on_event(event.event_name, payload)

    def _resolve_command_prefix(self, plugin_context: PluginContext) -> str:
        raw = plugin_context.configuration.framework_config.get("command_prefix")
        if isinstance(raw, str) and raw:
            return raw
        return "/"

    def _matches_event(self, registered_event: str, actual_event: str) -> bool:
        if registered_event == actual_event:
            return True
        return actual_event.startswith(f"{registered_event}.")

    def _build_payload(self, event: OneBotV11Event) -> dict[str, object]:
        sender = (
            {
                "user_id": event.sender.user_id,
                "nickname": event.sender.nickname,
                "card": event.sender.card,
                "role": event.sender.role,
                "level": event.sender.metadata.get("level"),
                "title": event.sender.metadata.get("title"),
            }
            if event.sender is not None
            else None
        )
        return {
            "event_type": event.event_type,
            "event_name": event.event_name,
            "scene": event.scene,
            "user_id": event.user_id,
            "group_id": event.group_id,
            "chat_id": event.chat_id,
            "message_id": event.message_id,
            "plain_text": event.plain_text,
            "effective_text": self._build_effective_text(event),
            "segments": [
                {"type": seg.type, "data": dict(seg.data)}
                for seg in event.segments
            ],
            "sender": sender,
            "metadata": event.metadata,
            "raw_event": event.raw_event,
        }

    def _build_effective_text(self, event: OneBotV11Event) -> str:
        """将消息 segments 展开为可读文本。

        - 艾特机器人自身跳过（唤醒信号）
        - 艾特其他用户转为 [@QQ号]
        - 非文本媒体标注类型标签
        """
        self_id = event.self_id
        parts: list[str] = []
        for seg in event.segments:
            if seg.type == "text":
                t = seg.data.get("text", "")
                if isinstance(t, str):
                    parts.append(t)
            elif seg.type == "at":
                qq = str(seg.data.get("qq", ""))
                if qq == "all":
                    parts.append("[@全体成员]")
                elif self_id and qq == self_id:
                    pass  # 艾特机器人本身，跳过
                elif qq:
                    parts.append(f"[@{qq}]")
            elif seg.type == "image":
                parts.append("[图片]")
            elif seg.type == "record":
                parts.append("[语音]")
            elif seg.type == "video":
                parts.append("[视频]")
        return "".join(parts).strip()

    def _build_reply_callable(
        self,
        event: OneBotV11Event,
    ) -> Callable[[str], Awaitable[str | None]]:
        async def reply(message: str) -> str | None:
            target = self.build_reply_target(event)
            if target is None:
                logger.warning(
                    "Cannot reply to event with no reply target: {}", event.event_name
                )
                return None
            outbound_segments: list[OneBotV11MessageSegment] = [
                self.message_codec.text(message)
            ]
            segments = self.message_codec.encode(outbound_segments)
            logger.info(
                "[OneBot] 发送回复 | scene={} chat_id={} | 内容: {}",
                target.scene,
                target.chat_id,
                message[:100] + "..." if len(message) > 100 else message,
            )
            resp = await self.send_callable(target, segments)
            data = resp.get("data")
            if isinstance(data, dict):
                msg_id = data.get("message_id")
                if msg_id is not None:
                    return str(msg_id)
            return None

        return reply

    def _build_send_voice_callable(
        self,
        event: OneBotV11Event,
    ) -> Callable[[bytes, str], Awaitable[str | None]]:
        """构建发送语音 callable，供 PluginContext 的 send_voice 使用。"""
        async def send_voice(audio_bytes: bytes, mime_type: str = "audio/mpeg") -> str | None:
            target = self.build_reply_target(event)
            if target is None:
                return None
            b64 = base64.b64encode(audio_bytes).decode()
            seg = self.message_codec.record(f"base64://{b64}")
            segments = self.message_codec.encode([seg])
            resp = await self.send_callable(target, segments)
            data = resp.get("data")
            if isinstance(data, dict):
                msg_id = data.get("message_id")
                if msg_id is not None:
                    return str(msg_id)
            return None

        return send_voice

    async def _transcribe_voice(
        self,
        event: OneBotV11Event,
        configuration: ConfigurationContext,
        execution: ExecutionContext,
    ) -> str | None:
        """如果事件包含语音 segment 且配置了 stt_provider，下载音频并转文字。"""
        stt_provider = configuration.framework_config.get("stt_provider")
        if not isinstance(stt_provider, str) or not stt_provider:
            return None

        audio_url: str | None = None
        audio_mime = "audio/mpeg"
        for seg in event.segments:
            if seg.type == "record":
                url = seg.data.get("url") or seg.data.get("file", "")
                if isinstance(url, str) and url.startswith("http"):
                    audio_url = url
                    break

        if audio_url is None:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(audio_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        logger.warning("[STT] 下载音频失败 status={}", resp.status)
                        return None
                    audio_bytes = await resp.read()
                    ct = resp.headers.get("Content-Type", "")
                    if ct:
                        audio_mime = ct.split(";")[0].strip()
        except Exception as exc:
            logger.warning("[STT] 下载音频出错: {}", exc)
            return None

        try:
            from ...providers.types import STTRequest as _STTRequest
            result = await self.framework.invoke_provider(
                provider_name=stt_provider,
                execution=execution,
                configuration=configuration,
                request=STTRequest(audio_bytes=audio_bytes, mime_type=audio_mime),
            )
            from ...providers.types import STTResponse
            if isinstance(result, STTResponse):
                if result.error:
                    logger.warning("[STT] 转写失败: {}", result.error.message)
                    return None
                return result.text or None
        except Exception as exc:
            logger.warning("[STT] 调用 STT provider 出错: {}", exc)

        return None


    def _build_recall_callable(
        self,
        event: OneBotV11Event,
    ) -> Callable[[str], Awaitable[None]]:
        async def recall(message_id: str) -> None:
            if self.delete_callable is None:
                logger.warning("[OneBot] delete_callable 未配置，无法撤回消息")
                return
            try:
                await self.delete_callable(message_id)
                logger.info("[OneBot] 已撤回消息 message_id={}", message_id)
            except Exception as exc:
                logger.warning("[OneBot] 撤回消息失败 message_id={}: {}", message_id, exc)

        return recall

    async def _analyze_quoted_message(
        self, event: OneBotV11Event
    ) -> dict[str, object]:
        """分析消息中的图片和引用信息，单次 get_msg 调用拿全所有数据。

        返回:
            image_urls: 当前消息 + 引用消息中的图片 URL 列表
            is_reply_to_self: 是否引用了 bot 自己发的消息
            quoted_text: 引用消息的文本内容（供 LLM 上下文注入）
        """
        image_urls: list[str] = []
        is_reply_to_self = False
        quoted_text: str | None = None

        # 1. 当前消息中的图片 segment
        for seg in event.segments:
            if seg.type == "image":
                url = seg.data.get("url") or seg.data.get("file", "")
                if isinstance(url, str) and url.startswith("http"):
                    image_urls.append(url)

        # 2. 引用 segment — 一次 get_msg 取回所有信息
        if self.fetch_message_callable is not None:
            for seg in event.segments:
                if seg.type != "reply":
                    continue
                msg_id = seg.data.get("id")
                if not msg_id:
                    continue
                try:
                    resp = await self.fetch_message_callable(str(msg_id))
                    data = resp.get("data") if isinstance(resp, dict) else None
                    if not isinstance(data, dict):
                        continue

                    # 检查原始消息发送者是否为 bot 自身
                    # data.user_id 和 data.sender.user_id 都有，优先取顶层 user_id
                    self_id = event.self_id or ""
                    sender_id = str(data.get("user_id") or "")
                    if not sender_id:
                        sender = data.get("sender")
                        if isinstance(sender, dict):
                            sender_id = str(sender.get("user_id") or "")
                    if sender_id and self_id and sender_id == self_id:
                        is_reply_to_self = True

                    # 检查是否是合并转发消息（forward segment）
                    # message 字段实际为 array，但 schema 定义为 object，加类型保护
                    raw_msg = data.get("message", [])
                    raw_segs: list[object] = raw_msg if isinstance(raw_msg, list) else []  # type: ignore[assignment]
                    forward_id: str | None = None
                    for raw_seg in raw_segs:
                        if isinstance(raw_seg, dict) and raw_seg.get("type") == "forward":
                            seg_data_f = raw_seg.get("data", {})
                            if isinstance(seg_data_f, dict):
                                fid = seg_data_f.get("id")
                                if isinstance(fid, (str, int)) and fid:
                                    forward_id = str(fid)
                            break

                    if forward_id is not None:
                        # 合并转发：调 get_forward_msg 取全部节点
                        qt = await self._extract_forward_text(forward_id)
                        if qt:
                            quoted_text = qt
                    else:
                        # 普通消息：提取图片 URL 和文本
                        text_parts: list[str] = []
                        for raw_seg in raw_segs:
                            if not isinstance(raw_seg, dict):
                                continue
                            seg_type = raw_seg.get("type")
                            seg_data = raw_seg.get("data", {})
                            if not isinstance(seg_data, dict):
                                continue
                            if seg_type == "image":
                                url = seg_data.get("url") or seg_data.get("file", "")
                                if isinstance(url, str) and url.startswith("http"):
                                    image_urls.append(url)
                            elif seg_type == "text":
                                t = seg_data.get("text", "")
                                if isinstance(t, str) and t.strip():
                                    text_parts.append(t.strip())
                        if text_parts:
                            quoted_text = " ".join(text_parts)

                except Exception as exc:
                    logger.warning(
                        "[OneBot] 获取引用消息失败 msg_id={}: {}", msg_id, exc
                    )
                break  # 只处理第一个 reply segment

        return {
            "image_urls": image_urls,
            "is_reply_to_self": is_reply_to_self,
            "quoted_text": quoted_text,
        }

    async def _extract_forward_text(
        self,
        forward_id: str,
        *,
        _seen: set[str] | None = None,
        _depth: int = 0,
    ) -> str | None:
        """调用 get_forward_msg 提取合并转发文本，支持嵌套转发（BFS，最多 3 层 / 32 次）。"""
        _MAX_DEPTH = 3
        _MAX_NODES = 30
        _MAX_CHARS = 2000

        if self.fetch_forward_callable is None:
            return None
        if _seen is None:
            _seen = set()
        if forward_id in _seen or _depth >= _MAX_DEPTH:
            return None
        _seen.add(forward_id)

        try:
            resp = await self.fetch_forward_callable(forward_id)
            data = resp.get("data") if isinstance(resp, dict) else None
            if not isinstance(data, dict):
                return None

            # 兼容 NapCat / Go-CQHTTP / Lagrange 等实现的字段名差异
            raw_nodes = (
                data.get("messages")
                or data.get("message")
                or data.get("nodes")
                or data.get("nodeList")
                or []
            )
            nodes: list[object] = raw_nodes if isinstance(raw_nodes, list) else []

            lines: list[str] = []
            indent = "  " * _depth

            for node in nodes[:_MAX_NODES]:
                if not isinstance(node, dict):
                    continue

                # sender 三级降级：nickname → card → user_id
                sender_raw = node.get("sender") or {}
                sender_name = ""
                if isinstance(sender_raw, dict):
                    sender_name = (
                        str(sender_raw.get("nickname") or "")
                        or str(sender_raw.get("card") or "")
                        or str(sender_raw.get("user_id") or "")
                    )

                # 节点消息内容：message 或 content，兼容字符串形式
                raw_content = node.get("message") or node.get("content") or []
                if isinstance(raw_content, str):
                    # 尝试作为 JSON 解析，否则直接当文本
                    try:
                        raw_content = json.loads(raw_content)
                    except Exception:
                        if raw_content.strip():
                            prefix = f"{indent}{sender_name}: " if sender_name else indent
                            lines.append(prefix + raw_content.strip())
                        continue

                segs: list[object] = raw_content if isinstance(raw_content, list) else []
                text_parts: list[str] = []

                for seg in segs:
                    if not isinstance(seg, dict):
                        continue
                    seg_type = seg.get("type", "")
                    seg_data = seg.get("data") or {}
                    if not isinstance(seg_data, dict):
                        continue

                    if seg_type in ("text", "plain"):
                        t = seg_data.get("text", "")
                        if isinstance(t, str) and t.strip():
                            text_parts.append(t.strip())
                    elif seg_type == "image":
                        text_parts.append("[图片]")
                    elif seg_type in ("video",):
                        text_parts.append("[视频]")
                    elif seg_type == "file":
                        fname = seg_data.get("name") or ""
                        text_parts.append(f"[文件:{fname}]" if fname else "[文件]")
                    elif seg_type in ("forward", "forward_msg"):
                        # 嵌套转发：如果有 id 则递归 fetch，否则跳过
                        nested_id = str(seg_data.get("id") or seg_data.get("message_id") or "")
                        if nested_id and nested_id not in _seen:
                            nested = await self._extract_forward_text(
                                nested_id, _seen=_seen, _depth=_depth + 1
                            )
                            if nested:
                                text_parts.append(f"\n{nested}")

                if text_parts:
                    prefix = f"{indent}{sender_name}: " if sender_name else indent
                    lines.append(prefix + "".join(text_parts))

            if not lines:
                return None
            return "\n".join(lines)[:_MAX_CHARS]

        except Exception as exc:
            logger.warning("[OneBot] 获取合并转发内容失败 id={}: {}", forward_id, exc)
            return None

    def _resolve_scope(self, event: OneBotV11Event) -> str:
        if event.scene == OneBotV11Scene.GROUP:
            return "group"
        if event.scene == OneBotV11Scene.PRIVATE:
            return "private"
        return "platform"
