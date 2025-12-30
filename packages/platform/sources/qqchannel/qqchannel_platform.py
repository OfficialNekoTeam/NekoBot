"""QQ频道平台适配器

参考 QQ 频道官方文档和 AstrBot 实现
"""

import asyncio
import json
from typing import Any, Optional

import aiohttp
from loguru import logger

from ...base import BasePlatform
from ...register import register_platform_adapter
from ...base import PlatformStatus


@register_platform_adapter(
    "qqchannel",
    "QQ频道适配器 (基于官方 API)",
    default_config_tmpl={
        "type": "qqchannel",
        "enable": False,
        "id": "qqchannel",
        "name": "NekoBot",
        "app_id": "",
        "token": "",
        "sandbox": False,
    },
    adapter_display_name="QQ频道",
    support_streaming_message=True,
)
class QQChannelPlatform(BasePlatform):
    """QQ频道平台适配器"""

    def __init__(
        self,
        platform_config: dict,
        platform_settings: dict,
        event_queue: Optional[asyncio.Queue] = None,
    ) -> None:
        super().__init__(platform_config, platform_settings, event_queue)

        self.app_id = platform_config.get("app_id", "")
        self.token = platform_config.get("token", "")
        self.sandbox = platform_config.get("sandbox", False)

        # API 基础 URL
        if self.sandbox:
            self.api_base = "https://sandbox.api.sgroup.qq.com"
            self.ws_base = "wss://sandbox.api.sgroup.qq.com/websocket"
        else:
            self.api_base = "https://api.sgroup.qq.com"
            self.ws_base = "wss://api.sgroup.qq.com/websocket"

        self._session: Optional[aiohttp.ClientSession] = None
        self._shutdown_event = asyncio.Event()

        # 机器人信息
        self.bot_id = ""
        self.bot_name = self.display_name

        # WebSocket 连接
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bot {self.app_id}.{self.token}",
                    "Content-Type": "application/json",
                }
            )
        return self._session

    async def start(self) -> None:
        """启动 QQ 频道适配器"""
        if not self.app_id or not self.token:
            logger.error("[QQChannel] App ID 或 Token 未配置")
            self.status = PlatformStatus.ERROR
            self.record_error("App ID 或 Token 未配置")
            return

        logger.info("[QQChannel] 正在启动 QQ 频道适配器...")

        try:
            await self._get_session()

            # 获取机器人信息
            await self._fetch_bot_info()

            self.status = PlatformStatus.RUNNING
            logger.info(f"[QQChannel] QQ 频道适配器已启动 (Bot: {self.bot_name})")

            # 这里应该启动 WebSocket 连接
            # 由于复杂性，暂时使用等待关闭信号的方式
            await self._shutdown_event.wait()

        except Exception as e:
            logger.error(f"[QQChannel] 启动失败: {e}")
            self.status = PlatformStatus.ERROR
            self.record_error(str(e))

    async def stop(self) -> None:
        """停止 QQ 频道适配器"""
        logger.info("[QQChannel] 正在停止适配器...")
        self._shutdown_event.set()

        # 关闭 WebSocket 连接
        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                logger.warning(f"[QQChannel] 关闭 WebSocket 时出错: {e}")

        if self._session and not self._session.closed:
            await self._session.close()

        self.status = PlatformStatus.STOPPED
        logger.info("[QQChannel] 适配器已停止")

    async def _fetch_bot_info(self) -> None:
        """获取机器人信息"""
        try:
            async with await self._get_session() as session:
                async with session.get(f"{self.api_base}/users/@me") as response:
                    if response.status == 200:
                        data = await response.json()
                        self.bot_id = str(data.get("id", ""))
                        self.bot_name = data.get("nick", self.display_name)
                        logger.info(f"[QQChannel] 机器人信息获取成功: {self.bot_name} (ID: {self.bot_id})")
        except Exception as e:
            logger.error(f"[QQChannel] 获取机器人信息失败: {e}")

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
            target_id: 目标ID（用户ID/频道ID）
            message: 消息内容
            **kwargs: 其他参数

        Returns:
            发送结果
        """
        try:
            async with await self._get_session() as session:
                # QQ 频道使用 message.create 发送消息
                url = f"{self.api_base}/messages"

                payload = {
                    "msg_id": "",  # 用于回复消息
                    "content": message,
                    "msg_type": 0,  # 0=文本消息
                    "timestamp": "",
                }

                # 根据 message_type 确定发送目标
                if message_type == "private":
                    # 私聊消息
                    payload["channel_id"] = target_id
                else:
                    # 频道消息
                    payload["channel_id"] = target_id

                async with session.post(url, json=payload) as response:
                    result = await response.json()

                    # QQ 频道 API 返回 code=0 表示成功
                    if result.get("code") == 0:
                        return {"status": "success", "message": "消息已发送"}
                    else:
                        logger.error(f"[QQChannel] 发送消息失败: {result}")
                        return {"status": "failed", "message": result.get("message", "发送失败")}

        except Exception as e:
            logger.error(f"[QQChannel] 发送消息异常: {e}")
            return {"status": "failed", "message": str(e)}

    async def handle_webhook(self, event_data: dict) -> Any:
        """处理 Webhook 事件

        Args:
            event_data: Webhook 事件数据

        Returns:
            Webhook 响应
        """
        try:
            event_type = event_data.get("type", "")
            logger.debug(f"[QQChannel] 收到事件类型: {event_type}")

            if event_type == "MESSAGE_CREATE":
                await self._handle_message_create(event_data)
            elif event_type == "GUILD_MEMBER_ADD":
                # 新成员加入事件
                pass
            elif event_type == "READY":
                # WebSocket 就绪事件
                logger.info("[QQChannel] WebSocket 连接就绪")

            return {"code": 0}

        except Exception as e:
            logger.error(f"[QQChannel] 处理 Webhook 事件失败: {e}")
            return {"code": 1, "message": str(e)}

    async def _handle_message_create(self, event_data: dict) -> None:
        """处理消息创建事件"""
        try:
            data = event_data.get("d", {})
            author = data.get("author", {})
            channel_id = data.get("channel_id", "")
            guild_id = data.get("guild_id", "")

            # 构建事件数据
            event_data_internal = {
                "platform_id": self.id,
                "type": "message",
                "message_type": "group",  # QQ 频道主要是群聊
                "sender_id": str(author.get("id", "")),
                "sender_name": author.get("nick", author.get("username", "Unknown")),
                "group_id": channel_id,
                "session_id": channel_id,
                "message_id": data.get("id", ""),
                "message": data.get("content", ""),
                "timestamp": data.get("timestamp", 0) // 1000,
                "raw_message": event_data,
            }

            # 检查是否是机器人自己的消息
            if str(author.get("id", "")) == self.bot_id:
                return

            await self.handle_event(event_data_internal)

        except Exception as e:
            logger.error(f"[QQChannel] 处理消息创建事件失败: {e}")

    async def webhook_callback(self, request: Any) -> Any:
        """统一 Webhook 回调入口"""
        # 这里的 request 类型取决于使用的 Web 框架
        # 暂时返回占位符
        return {"status": "ok"}

    def get_stats(self) -> dict:
        """获取平台统计信息"""
        stats = super().get_stats()
        stats.update({
            "bot_id": self.bot_id,
            "bot_name": self.bot_name,
            "sandbox": self.sandbox,
        })
        return stats