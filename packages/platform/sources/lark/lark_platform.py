"""飞书平台适配器

参考 AstrBot 的飞书适配器实现
"""

import asyncio
import base64
import json
import re
import time
import uuid
from typing import Any, Optional

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    GetMessageResourceRequest,
)
from lark_oapi.api.im.v1.processor import P2ImMessageReceiveV1Processor

from loguru import logger

from ...base import BasePlatform
from ...register import register_platform_adapter
from ...base import PlatformStatus

try:
    from ..lark_event import LarkPlatformEvent
except ImportError:
    # 如果事件类不存在，创建一个占位符
    class LarkPlatformEvent:
        pass


@register_platform_adapter(
    "lark",
    "飞书机器人适配器 (基于官方 SDK)",
    default_config_tmpl={
        "type": "lark",
        "enable": False,
        "id": "lark",
        "name": "飞书机器人",
        "app_id": "",
        "app_secret": "",
        "domain": "https://open.feishu.cn",
        "connection_mode": "socket",
        "lark_bot_name": "NekoBot",
        "verify_token": "",
        "encrypt_key": "",
    },
    adapter_display_name="飞书",
    support_streaming_message=False,
)
class LarkPlatform(BasePlatform):
    """飞书平台适配器"""

    def __init__(
        self,
        platform_config: dict,
        platform_settings: dict,
        event_queue: Optional[asyncio.Queue] = None,
    ) -> None:
        super().__init__(platform_config, platform_settings, event_queue)

        self.appid = platform_config.get("app_id", "")
        self.appsecret = platform_config.get("app_secret", "")
        self.domain = platform_config.get("domain", "https://open.feishu.cn")
        self.bot_name = platform_config.get("lark_bot_name", "NekoBot")
        self.connection_mode = platform_config.get("connection_mode", "socket")
        self.verify_token = platform_config.get("verify_token", "")
        self.encrypt_key = platform_config.get("encrypt_key", "")

        if not self.bot_name:
            logger.warning("[Lark] 未设置飞书机器人名称，@ 机器人可能得不到回复。")

        # WebSocket 长连接相关配置
        async def on_msg_event_recv(event: lark.im.v1.P2ImMessageReceiveV1):
            await self.convert_msg(event)

        def do_v2_msg_event(event: lark.im.v1.P2ImMessageReceiveV1):
            asyncio.create_task(on_msg_event_recv(event))

        self.event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(do_v2_msg_event)
            .build()
        )

        self.do_v2_msg_event = do_v2_msg_event

        self.ws_client = lark.ws.Client(
            app_id=self.appid,
            app_secret=self.appsecret,
            log_level=lark.LogLevel.ERROR,
            domain=self.domain,
            event_handler=self.event_handler,
        )

        self.lark_api = (
            lark.Client.builder()
            .app_id(self.appid)
            .app_secret(self.appsecret)
            .log_level(lark.LogLevel.ERROR)
            .domain(self.domain)
            .build()
        )

        # 用于去重事件
        self.event_id_timestamps: dict[str, float] = {}

        self._shutdown_event = asyncio.Event()

    def _clean_expired_events(self):
        """清理超过 30 分钟的事件记录"""
        current_time = time.time()
        expired_keys = [
            event_id
            for event_id, timestamp in self.event_id_timestamps.items()
            if current_time - timestamp > 1800
        ]
        for event_id in expired_keys:
            del self.event_id_timestamps[event_id]

    def _is_duplicate_event(self, event_id: str) -> bool:
        """检查事件是否重复"""
        self._clean_expired_events()
        if event_id in self.event_id_timestamps:
            return True
        self.event_id_timestamps[event_id] = time.time()
        return False

    async def start(self) -> None:
        """启动飞书适配器"""
        if not self.appid or not self.appsecret:
            logger.error("[Lark] App ID 或 App Secret 未配置")
            self.status = PlatformStatus.ERROR
            self.record_error("App ID 或 App Secret 未配置")
            return

        logger.info("[Lark] 正在启动飞书适配器...")

        try:
            if self.connection_mode == "socket":
                # 长连接模式
                await self.ws_client._connect()
                self.status = PlatformStatus.RUNNING
                logger.info("[Lark] 飞书适配器已启动 (WebSocket 模式)")

                # 等待关闭信号
                await self._shutdown_event.wait()
            else:
                # Webhook 模式
                logger.info("[Lark] 飞书适配器已配置为 Webhook 模式")
                self.status = PlatformStatus.RUNNING

        except Exception as e:
            logger.error(f"[Lark] 启动失败: {e}")
            self.status = PlatformStatus.ERROR
            self.record_error(str(e))

    async def stop(self) -> None:
        """停止飞书适配器"""
        logger.info("[Lark] 正在停止适配器...")
        self._shutdown_event.set()

        if self.ws_client:
            try:
                await self.ws_client._disconnect()
            except Exception as e:
                logger.warning(f"[Lark] 关闭 WebSocket 时出错: {e}")

        self.status = PlatformStatus.STOPPED
        logger.info("[Lark] 适配器已停止")

    async def send_message(
        self,
        message_type: str,
        target_id: str,
        message: str,
        **kwargs,
    ) -> dict[str, Any]:
        """发送消息

        Args:
            message_type: 消息类型（private/group）
            target_id: 目标ID（user_id/chat_id）
            message: 消息内容
            **kwargs: 其他参数

        Returns:
            发送结果
        """
        try:
            if self.lark_api.im is None:
                logger.error("[Lark] API Client im 模块未初始化，无法发送消息")
                return {"status": "failed", "message": "API Client 未初始化"}

            # 构建飞书消息格式
            res = {
                "zh_cn": {
                    "title": "",
                    "content": [[{"tag": "text", "text": message}]],
                },
            }

            # 确定接收者类型
            if message_type == "private":
                receive_id_type = "open_id"
            else:
                receive_id_type = "chat_id"
                # 如果是群聊 ID 且包含 %，处理特殊格式
                if "%" in target_id:
                    target_id = target_id.split("%")[1]

            request = (
                CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(target_id)
                    .content(json.dumps(res))
                    .msg_type("post")
                    .uuid(str(uuid.uuid4()))
                    .build(),
                )
                .build()
            )

            response = await self.lark_api.im.v1.message.acreate(request)

            if not response.success():
                logger.error(f"[Lark] 发送消息失败({response.code}): {response.msg}")
                return {"status": "failed", "message": f"发送失败: {response.msg}"}

            return {"status": "success", "message": "消息已发送"}

        except Exception as e:
            logger.error(f"[Lark] 发送消息异常: {e}")
            return {"status": "failed", "message": str(e)}

    async def convert_msg(self, event: lark.im.v1.P2ImMessageReceiveV1):
        """转换飞书消息为内部格式"""
        if event.event is None:
            return
        message = event.event.message
        if message is None:
            return

        # 检查是否重复事件
        if hasattr(event, 'header') and event.header:
            event_id = event.header.event_id
            if event_id and self._is_duplicate_event(event_id):
                logger.debug(f"[Lark] 跳过重复事件: {event_id}")
                return

        # 构建事件数据
        event_data = {
            "platform_id": self.id,
            "type": "message",
            "message_type": "group" if message.chat_type == "group" else "private",
            "sender_id": event.event.sender.sender_id.open_id if event.event.sender and event.event.sender.sender_id else "",
            "sender_name": event.event.sender.sender_id.open_id if event.event.sender and event.event.sender.sender_id else "",
            "group_id": message.chat_id if message.chat_type == "group" else "",
            "session_id": message.chat_id if message.chat_type == "group" else (event.event.sender.sender_id.open_id if event.event.sender and event.event.sender.sender_id else ""),
            "message_id": message.message_id,
            "message": self._parse_message_content(message),
            "timestamp": int(message.create_time // 1000) if message.create_time else int(time.time()),
            "raw_message": message,
        }

        await self.handle_event(event_data)

    def _parse_message_content(self, message) -> str:
        """解析消息内容"""
        if not message.content:
            return ""

        try:
            content_json = json.loads(message.content)
        except json.JSONDecodeError:
            logger.error(f"[Lark] 解析消息内容失败: {message.content}")
            return ""

        if message.message_type == "text":
            message_str = content_json.get("text", "")
            # 移除 @ 符号
            return re.sub(r"(@_user_\d+)", "", message_str).strip()
        elif message.message_type == "post":
            content_ls = content_json.get("content", [])
            if isinstance(content_ls, list):
                text_parts = []
                for comp in content_ls:
                    if isinstance(comp, dict) and comp.get("tag") == "text":
                        text_parts.append(comp.get("text", ""))
                return "".join(text_parts)
        elif message.message_type == "image":
            return "[图片]"

        return ""