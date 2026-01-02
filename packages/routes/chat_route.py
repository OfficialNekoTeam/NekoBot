"""聊天路由

提供 LLM 聊天功能，支持流式响应和会话管理
"""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from loguru import logger

from quart import g, make_response, request

from .route import Route, Response, RouteContext

# 会话数据存储路径
SESSIONS_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "chat_sessions.json"
)
SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def track_conversation(convs: dict, conv_id: str):
    """跟踪会话上下文

    Args:
        convs: 会话字典
        conv_id: 会话 ID
    """
    convs[conv_id] = True
    try:
        yield
    finally:
        convs.pop(conv_id, None)


class ChatRoute(Route):
    """聊天路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.sessions_path = SESSIONS_PATH
        self.routes = [
            ("/chat/send", "POST", self.chat),
            ("/chat/new_session", "GET", self.new_session),
            ("/chat/sessions", "GET", self.get_sessions),
            ("/chat/get_session", "GET", self.get_session),
            ("/chat/delete_session", "POST", self.delete_session),
        ]
        self.running_convs: dict[str, bool] = {}

    async def chat(self) -> Any:
        """发送聊天消息（支持流式响应）

        Returns:
            流式响应
        """
        username = g.get("username", "guest")

        post_data = await request.json
        if "message" not in post_data:
            return Response().error("Missing key: message").to_dict()

        if "session_id" not in post_data:
            return Response().error("Missing key: session_id").to_dict()

        message = post_data["message"]
        session_id = post_data["session_id"]
        selected_provider = post_data.get("selected_provider")
        selected_model = post_data.get("selected_model")
        enable_streaming = post_data.get("enable_streaming", True)

        # 检查消息是否为空
        if not message:
            return Response().error("Message is empty").to_dict()

        # 保存用户消息到会话历史
        await self._save_user_message(session_id, username, message)

        # 获取 LLM 提供商配置
        from ..core.config import load_config

        config = load_config()
        llm_providers = config.get("llm_providers", {})

        # 查找选中的提供商
        provider_config = None
        if selected_provider:
            for provider_id, provider in llm_providers.items():
                if provider.get("id") == selected_provider and provider.get(
                    "enabled", False
                ):
                    provider_config = provider
                    break

        if not provider_config:
            # 使用第一个启用的提供商
            for provider in llm_providers.values():
                if provider.get("enabled", False):
                    provider_config = provider
                    break

        if not provider_config:
            return Response().error("No enabled LLM provider found").to_dict()

        # 流式响应
        async def stream():
            client_disconnected = False
            accumulated_text = ""

            try:
                async with track_conversation(self.running_convs, session_id):
                    # 调用真实的 LLM API
                    if enable_streaming and hasattr(self, '_stream_llm_response'):
                        # 尝试使用流式响应
                        async for chunk in self._stream_llm_response(
                            message, provider_config, selected_model, session_id
                        ):
                            if not client_disconnected:
                                accumulated_text += chunk
                                yield f"data: {json.dumps({'type': 'plain', 'text': chunk}, ensure_ascii=False)}\n\n"
                    else:
                        # 使用普通响应
                        response_text = await self._call_llm_response(
                            message, provider_config, selected_model, session_id
                        )

                        # 发送流式数据
                        for chunk in self._chunk_text(response_text):
                            if not client_disconnected:
                                accumulated_text += chunk
                                yield f"data: {json.dumps({'type': 'plain', 'text': chunk}, ensure_ascii=False)}\n\n"

                    # 发送结束标记
                    if not client_disconnected:
                        yield f"data: {json.dumps({'type': 'end'}, ensure_ascii=False)}\n\n"

                        # 保存 bot 消息到会话历史
                        await self._save_bot_message(session_id, accumulated_text)

            except asyncio.CancelledError:
                logger.debug(f"[Chat] 用户 {username} 断开聊天连接。")
                client_disconnected = True
            except Exception as e:
                logger.error(f"[Chat] 聊天错误: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = await make_response(
            stream(),
            {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Transfer-Encoding": "chunked",
                "Connection": "keep-alive",
            },
        )
        response.timeout = None
        return response

    async def _call_llm_response(
        self, message: str, provider_config: dict, model: str, session_id: str
    ) -> str:
        """调用真实的 LLM API

        Args:
            message: 用户消息
            provider_config: 提供商配置
            model: 模型名称
            session_id: 会话 ID

        Returns:
            LLM 响应文本
        """
        from ...llm.register import llm_provider_cls_map
        from ...llm.context_manager import LLMContextManager, ContextConfig, ContextCompressionStrategy

        provider_type = provider_config.get("type", "unknown")
        logger.info(
            f"[Chat] 使用提供商 {provider_type} 模型 {model} 处理消息: {message[:100]}"
        )

        # 获取 provider 类
        provider_meta = llm_provider_cls_map.get(provider_type)
        if not provider_meta:
            logger.error(f"未找到 LLM 提供商类型: {provider_type}")
            return f"错误: 未找到 LLM 提供商类型 {provider_type}"

        # 创建 provider 实例
        provider = provider_meta.cls_type(provider_config, {})

        # 如果指定了模型，使用指定的模型
        if model:
            provider.set_model(model)

        # 获取会话历史作为上下文
        sessions = self._load_sessions()
        contexts = None
        if session_id in sessions:
            # 转换会话历史为 LLM 上下文格式
            contexts = []
            for msg in sessions[session_id].get("messages", []):
                contexts.append({
                    "role": msg.get("role"),
                    "content": msg.get("content")
                })
            # 只保留最近的 N 条消息
            max_messages = provider_config.get("max_messages", 20)
            if contexts and len(contexts) > max_messages:
                contexts = contexts[-max_messages:]

        try:
            # 调用 LLM API
            response = await provider.text_chat(
                prompt=message,
                session_id=session_id,
                contexts=contexts,
            )

            response_text = response.completion_text or response.content

            logger.info(f"[Chat] LLM 响应: {response_text[:100]}")
            return response_text

        except Exception as e:
            logger.error(f"[Chat] LLM API 调用失败: {e}", exc_info=True)
            return f"错误: LLM API 调用失败 - {str(e)}"

    async def _stream_llm_response(
        self, message: str, provider_config: dict, model: str, session_id: str
    ):
        """流式 LLM 响应

        Args:
            message: 用户消息
            provider_config: 提供商配置
            model: 模型名称
            session_id: 会话 ID

        Yields:
            响应文本块
        """
        from ...llm.register import llm_provider_cls_map
        from ...llm.context_manager import LLMContextManager, ContextConfig, ContextCompressionStrategy

        provider_type = provider_config.get("type", "unknown")

        # 获取 provider 类
        provider_meta = llm_provider_cls_map.get(provider_type)
        if not provider_meta:
            yield f"错误: 未找到 LLM 提供商类型 {provider_type}"
            return

        # 创建 provider 实例
        provider = provider_meta.cls_type(provider_config, {})

        # 如果指定了模型，使用指定的模型
        if model:
            provider.set_model(model)

        # 检查是否支持流式响应
        if not hasattr(provider, 'text_chat_stream'):
            # 不支持流式，回退到普通响应
            response_text = await self._call_llm_response(message, provider_config, model, session_id)
            for chunk in self._chunk_text(response_text):
                yield chunk
            return

        # 获取会话历史作为上下文
        sessions = self._load_sessions()
        contexts = None
        if session_id in sessions:
            contexts = []
            for msg in sessions[session_id].get("messages", []):
                contexts.append({
                    "role": msg.get("role"),
                    "content": msg.get("content")
                })
            max_messages = provider_config.get("max_messages", 20)
            if contexts and len(contexts) > max_messages:
                contexts = contexts[-max_messages:]

        try:
            # 调用流式 LLM API
            async for chunk in provider.text_chat_stream(
                prompt=message,
                session_id=session_id,
                contexts=contexts,
            ):
                if chunk and chunk.completion_text:
                    yield chunk.completion_text

        except Exception as e:
            logger.error(f"[Chat] LLM 流式 API 调用失败: {e}", exc_info=True)
            yield f"错误: LLM API 调用失败 - {str(e)}"

    def _chunk_text(self, text: str, chunk_size: int = 10) -> list[str]:
        """将文本分块

        Args:
            text: 要分块的文本
            chunk_size: 每块的大小

        Returns:
            文本块列表
        """
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    async def _save_user_message(
        self, session_id: str, username: str, message: str
    ) -> None:
        """保存用户消息到会话历史

        Args:
            session_id: 会话 ID
            username: 用户名
            message: 消息内容
        """
        sessions = self._load_sessions()
        if session_id not in sessions:
            sessions[session_id] = {
                "id": session_id,
                "messages": [],
                "created_at": self._get_current_timestamp(),
            }

        sessions[session_id]["messages"].append(
            {
                "role": "user",
                "content": message,
                "timestamp": self._get_current_timestamp(),
            }
        )
        self._save_sessions(sessions)

    async def _save_bot_message(self, session_id: str, message: str) -> None:
        """保存 bot 消息到会话历史

        Args:
            session_id: 会话 ID
            message: 消息内容
        """
        sessions = self._load_sessions()
        if session_id not in sessions:
            sessions[session_id] = {
                "id": session_id,
                "messages": [],
                "created_at": self._get_current_timestamp(),
            }

        sessions[session_id]["messages"].append(
            {
                "role": "assistant",
                "content": message,
                "timestamp": self._get_current_timestamp(),
            }
        )
        self._save_sessions(sessions)

    async def new_session(self) -> dict[str, Any]:
        """创建新会话

        Returns:
            新会话信息
        """
        username = g.get("username", "guest")
        session_id = str(uuid.uuid4())

        sessions = self._load_sessions()
        sessions[session_id] = {
            "id": session_id,
            "creator": username,
            "messages": [],
            "created_at": self._get_current_timestamp(),
        }
        self._save_sessions(sessions)

        return Response().ok(data={"session_id": session_id}).to_dict()

    async def get_sessions(self) -> dict[str, Any]:
        """获取所有会话

        Returns:
            会话列表
        """
        username = g.get("username", "guest")
        sessions = self._load_sessions()

        # 过滤属于当前用户的会话
        user_sessions = [
            {
                "id": session_id,
                "creator": session.get("creator"),
                "created_at": session.get("created_at"),
                "message_count": len(session.get("messages", [])),
            }
            for session_id, session in sessions.items()
            if session.get("creator") == username
        ]

        return Response().ok(data={"sessions": user_sessions}).to_dict()

    async def get_session(self) -> dict[str, Any]:
        """获取会话信息和历史

        Returns:
            会话信息和历史记录
        """
        session_id = request.args.get("session_id")
        if not session_id:
            return Response().error("Missing key: session_id").to_dict()

        sessions = self._load_sessions()
        if session_id not in sessions:
            return Response().error(f"Session {session_id} not found").to_dict()

        session = sessions[session_id]
        is_running = self.running_convs.get(session_id, False)

        return (
            Response()
            .ok(
                data={
                    "session": {
                        "id": session.get("id"),
                        "creator": session.get("creator"),
                        "created_at": session.get("created_at"),
                    },
                    "messages": session.get("messages", []),
                    "is_running": is_running,
                }
            )
            .to_dict()
        )

    async def delete_session(self) -> dict[str, Any]:
        """删除会话

        Returns:
            删除结果
        """
        post_data = await request.json
        session_id = post_data.get("session_id")
        if not session_id:
            return Response().error("Missing key: session_id").to_dict()

        username = g.get("username", "guest")

        sessions = self._load_sessions()
        if session_id not in sessions:
            return Response().error(f"Session {session_id} not found").to_dict()

        session = sessions[session_id]
        if session.get("creator") != username:
            return Response().error("Permission denied").to_dict()

        del sessions[session_id]
        self._save_sessions(sessions)

        return Response().ok(message="Session deleted successfully").to_dict()

    def _load_sessions(self) -> dict[str, Any]:
        """加载所有会话

        Returns:
            会话字典
        """
        if not self.sessions_path.exists():
            return {}

        try:
            with open(self.sessions_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载会话文件失败: {e}")
            return {}

    def _save_sessions(self, sessions: dict[str, Any]) -> None:
        """保存会话

        Args:
            sessions: 会话字典
        """
        with open(self.sessions_path, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2, ensure_ascii=False)

    def _get_current_timestamp(self) -> str:
        """获取当前时间戳

        Returns:
            ISO 格式的时间戳
        """
        from datetime import datetime

        return datetime.now().isoformat()
