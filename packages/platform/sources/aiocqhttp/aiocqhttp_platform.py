"""aiocqhttp 平台适配器"""

import asyncio
import json
from typing import Dict, Any, Optional
from aiohttp import web, WSMsgType
from loguru import logger

from ...base import BasePlatform
from ...register import register_platform_adapter


@register_platform_adapter(
    "aiocqhttp",
    "aiocqhttp 平台适配器，基于 OneBot V11 协议，支持反向 WebSocket。",
    default_config_tmpl={
        "type": "aiocqhttp",
        "enable": True,
        "id": "aiocqhttp",
        "name": "NekoBot",
        "ws_host": "0.0.0.0",
        "ws_port": 6299,
        "command_prefix": "/",
    },
    adapter_display_name="aiocqhttp",
    support_streaming_message=False,
)
class AiocqhttpPlatform(BasePlatform):
    """aiocqhttp 平台适配器"""

    def __init__(
        self,
        platform_config: Dict[str, Any],
        platform_settings: Dict[str, Any],
        event_queue: Optional[asyncio.Queue] = None,
    ):
        super().__init__(platform_config, platform_settings, event_queue)
        self.ws_host = self.get_config("ws_host", "0.0.0.0")
        self.ws_port = self.get_config("ws_port", 6299)
        self.command_prefix = self.get_config("command_prefix", "/")
        self.clients: list[web.WebSocketResponse] = []
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

    async def start(self) -> None:
        """启动 aiocqhttp 平台适配器"""
        app = web.Application()
        app.add_routes([web.get("/ws", self.handle_aiocqhttp_client)])

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.ws_host, self.ws_port)
        await self.site.start()

        logger.info(
            f"[{self.display_name}] aiocqhttp 平台已启动: ws://{self.ws_host}:{self.ws_port}/ws"
        )

    async def stop(self) -> None:
        """停止 aiocqhttp 平台适配器"""
        if self.clients:
            for ws in list(self.clients):
                try:
                    await ws.close(code=1001, message="Server shutting down")
                except Exception as e:
                    logger.debug(f"[{self.display_name}] 断开客户端失败: {e}")
            self.clients.clear()
        if self.site:
            await self.site.stop()
            self.site = None
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
        logger.info(f"[{self.display_name}] aiocqhttp 平台已停止")

    async def send_message(
        self, message_type: str, target_id: str, message: str, **kwargs
    ) -> Dict[str, Any]:
        """发送消息

        Args:
            message_type: 消息类型（private/group）
            target_id: 目标ID（用户ID/群ID）
            message: 消息内容
            **kwargs: 其他参数

        Returns:
            发送结果
        """
        if not self.clients:
            return {"status": "failed", "message": "没有可用的客户端连接"}

        # 根据消息类型选择正确的参数名
        if message_type == "private":
            params = {"user_id": target_id, "message": message}
        else:  # group
            params = {"group_id": target_id, "message": message}

        response = {"action": f"send_{message_type}_msg", "params": params}

        for client in self.clients:
            try:
                await client.send_json(response)
                return {"status": "success", "message": "消息已发送"}
            except Exception as e:
                logger.error(f"[{self.display_name}] 发送消息失败: {e}")

        return {"status": "failed", "message": "发送消息失败"}

    async def handle_aiocqhttp_client(
        self, request: web.Request
    ) -> web.WebSocketResponse:
        """处理 aiocqhttp 客户端连接"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        client_id = f"{request.remote}:{request.transport.get_extra_info('peername')[1] if request.transport.get_extra_info('peername') else 'unknown'}"
        logger.info(f"[{self.display_name}] aiocqhttp客户端已连接: {client_id}")

        self.clients.append(ws)

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data: Dict[str, Any] = json.loads(msg.data)

                        # 处理API调用请求
                        if "action" in data:
                            action = data.get("action")
                            echo = data.get("echo")
                            params = data.get("params", {})

                            logger.debug(f"[{self.display_name}] 收到API调用: {action}")

                            # 处理API调用
                            response = await self.handle_api_call(action, params)

                            # 添加echo字段
                            if echo is not None:
                                response["echo"] = echo

                            await ws.send_json(response)
                            continue

                        # 处理事件
                        data["platform_id"] = self.id
                        await self.handle_event(data)

                    except json.JSONDecodeError as e:
                        logger.error(
                            f"[{self.display_name}] 解析aiocqhttp消息失败: {e}"
                        )
                elif msg.type == WSMsgType.ERROR:
                    logger.error(
                        f"[{self.display_name}] aiocqhttp客户端连接错误: {ws.exception()}"
                    )
        except Exception as e:
            logger.error(f"[{self.display_name}] 处理aiocqhttp客户端出错: {e}")
        finally:
            self.clients.remove(ws)
            logger.info(f"[{self.display_name}] aiocqhttp客户端已断开: {client_id}")

        return ws

    async def handle_api_call(
        self, action: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理API调用"""
        # 这里可以添加具体的API处理逻辑
        # 目前返回不支持的响应
        return {
            "status": "failed",
            "retcode": 1404,
            "data": None,
            "message": f"不支持的API: {action}",
            "wording": f"不支持的API: {action}",
            "echo": None,
            "stream": "normal-action",
        }
