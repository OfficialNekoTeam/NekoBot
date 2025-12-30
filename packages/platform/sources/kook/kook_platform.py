"""KOOK (开黑) 平台适配器

参考 AstrBot 和 KOOK 官方文档实现
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
    "kook",
    "KOOK (开黑) 适配器 (基于官方 API)",
    default_config_tmpl={
        "type": "kook",
        "enable": False,
        "id": "kook",
        "name": "NekoBot",
        "token": "",
        "verify_token": "",
        "encrypt_key": "",
    },
    adapter_display_name="KOOK",
    support_streaming_message=True,
)
class KookPlatform(BasePlatform):
    """KOOK (开黑) 平台适配器"""

    def __init__(
        self,
        platform_config: dict,
        platform_settings: dict,
        event_queue: Optional[asyncio.Queue] = None,
    ) -> None:
        super().__init__(platform_config, platform_settings, event_queue)

        self.token = platform_config.get("token", "")
        self.verify_token = platform_config.get("verify_token", "")
        self.encrypt_key = platform_config.get("encrypt_key", "")
        self.api_base = platform_config.get("api_base", "https://www.kookapp.cn/api/v3")

        self._session: Optional[aiohttp.ClientSession] = None
        self._shutdown_event = asyncio.Event()

        # 机器人信息
        self.bot_id = ""
        self.bot_name = self.display_name

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bot {self.token}",
                    "Content-Type": "application/json",
                }
            )
        return self._session

    async def start(self) -> None:
        """启动 KOOK 适配器"""
        if not self.token:
            logger.error("[KOOK] Bot Token 未配置")
            self.status = PlatformStatus.ERROR
            self.record_error("Bot Token 未配置")
            return

        logger.info("[KOOK] 正在启动 KOOK 适配器...")

        try:
            await self._get_session()

            # 获取机器人信息
            await self._fetch_bot_info()

            self.status = PlatformStatus.RUNNING
            logger.info(f"[KOOK] KOOK 适配器已启动 (Bot: {self.bot_name})")

            # 等待关闭信号
            await self._shutdown_event.wait()

        except Exception as e:
            logger.error(f"[KOOK] 启动失败: {e}")
            self.status = PlatformStatus.ERROR
            self.record_error(str(e))

    async def stop(self) -> None:
        """停止 KOOK 适配器"""
        logger.info("[KOOK] 正在停止适配器...")
        self._shutdown_event.set()

        if self._session and not self._session.closed:
            await self._session.close()

        self.status = PlatformStatus.STOPPED
        logger.info("[KOOK] 适配器已停止")

    async def _fetch_bot_info(self) -> None:
        """获取机器人信息"""
        try:
            async with await self._get_session() as session:
                async with session.get(f"{self.api_base}/user/me") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 0:
                            user_data = data.get("data", {})
                            self.bot_id = str(user_data.get("id", ""))
                            self.bot_name = user_data.get("username", self.display_name)
                            logger.info(f"[KOOK] 机器人信息获取成功: {self.bot_name} (ID: {self.bot_id})")
        except Exception as e:
            logger.error(f"[KOOK] 获取机器人信息失败: {e}")

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
                # KOOK 使用 channel_id 发送消息
                # 如果是私聊，需要先获取用户的私聊频道 ID
                url = f"{self.api_base}/message/create"

                payload = {
                    "target_id": target_id,
                    "content": message,
                }

                # 根据 message_type 确定发送类型
                if message_type == "private":
                    # 私聊消息
                    # KOOK 使用 user_id 发送私聊消息
                    payload["type"] = 1  # 1=私聊
                else:
                    # 频道消息
                    payload["type"] = 9  # 9=频道消息

                async with session.post(url, json=payload) as response:
                    result = await response.json()

                    if result.get("code") == 0:
                        return {"status": "success", "message": "消息已发送"}
                    else:
                        logger.error(f"[KOOK] 发送消息失败: {result}")
                        return {"status": "failed", "message": result.get("message", "发送失败")}

        except Exception as e:
            logger.error(f"[KOOK] 发送消息异常: {e}")
            return {"status": "failed", "message": str(e)}

    async def handle_webhook(self, event_data: dict) -> Any:
        """处理 Webhook 事件

        Args:
            event_data: Webhook 事件数据

        Returns:
            Webhook 响应
        """
        try:
            # 验证事件（如果配置了验证token）
            if self.verify_token or self.encrypt_key:
                # 这里可以添加事件验证逻辑
                pass

            event_type = event_data.get("type", "")
            logger.debug(f"[KOOK] 收到事件类型: {event_type}")

            if event_type == 1:  # 文本消息
                await self._handle_text_message(event_data)
            elif event_type == 255:  # 心跳检测
                return {"code": 0}

            return {"code": 0}

        except Exception as e:
            logger.error(f"[KOOK] 处理 Webhook 事件失败: {e}")
            return {"code": 1, "message": str(e)}

    async def _handle_text_message(self, event_data: dict) -> None:
        """处理文本消息"""
        try:
            extra = event_data.get("extra", {})
            author = extra.get("author", {})
            channel_id = event_data.get("target_id", "")

            # 判断是否为频道消息
            is_channel = event_data.get("type") == 9

            # 构建事件数据
            event_data_internal = {
                "platform_id": self.id,
                "type": "message",
                "message_type": "group" if is_channel else "private",
                "sender_id": str(author.get("id", "")),
                "sender_name": author.get("nickname", author.get("username", "Unknown")),
                "group_id": channel_id if is_channel else "",
                "session_id": channel_id if is_channel else str(author.get("id", "")),
                "message_id": event_data.get("msg_id", ""),
                "message": event_data.get("content", ""),
                "timestamp": event_data.get("msg_timestamp", 0) // 1000,
                "raw_message": event_data,
            }

            # 检查是否是机器人自己的消息
            if str(author.get("id", "")) == self.bot_id:
                return

            await self.handle_event(event_data_internal)

        except Exception as e:
            logger.error(f"[KOOK] 处理文本消息失败: {e}")

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
        })
        return stats