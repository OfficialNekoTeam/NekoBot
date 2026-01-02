"""对话管理路由

提供对话历史、上下文管理、模板管理和统计功能
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger
from quart import request

from .route import Route, Response, RouteContext
from ..conversation import (
    Conversation,
    Session,
    ConversationManager,
    SessionDeletedCallback,
)


class ConversationRoute(Route):
    """对话管理路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.routes = [
            ("/api/conversations", "GET", self.list_conversations),
            ("/api/conversations", "POST", self.create_conversation),
            ("/api/conversations/<id>", "GET", self.get_conversation),
            ("/api/conversations/<id>", "PUT", self.update_conversation),
            ("/api/conversations/<id>", "DELETE", self.delete_conversation),
            ("/api/conversations/<id>/messages", "GET", self.get_messages),
            ("/api/conversations/<id>/messages", "POST", self.add_message),
            ("/api/conversations/<id>/context", "GET", self.get_context),
            ("/api/conversations/templates", "GET", self.list_templates),
            ("/api/conversations/templates", "POST", self.create_template),
            ("/api/conversations/stats", "GET", self.get_stats),
            ("/api/conversations/search", "POST", self.search_conversations),
            ("/api/sessions", "GET", self.list_sessions),
            ("/api/sessions/<session_id>", "GET", self.get_session),
            ("/api/sessions/<session_id>", "DELETE", self.delete_session),
            ("/api/sessions/<session_id>/switch", "POST", self.switch_conversation),
        ]
        # 设置唯一的 endpoint 名称
        for path, method, handler in self.routes:
            handler.__func__.endpoint_name = f"conv_{handler.__name__}"

        # 获取对话管理器
        self.conv_manager: Optional[ConversationManager] = context.app.plugins.get("conversation_manager")

    async def list_conversations(self) -> Dict[str, Any]:
        """列出所有对话

        查询参数:
            session_id: 会话 ID（可选，筛选特定会话的对话）
            page: 页码（默认1）
            page_size: 每页数量（默认10）

        返回:
            对话列表
        """
        try:
            session_id = request.args.get("session_id")
            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 10))

            if not self.conv_manager:
                return Response().ok(data={"conversations": [], "total": 0}, message="对话管理器未初始化").to_dict()

            # 获取对话列表
            conversations = []
            if session_id:
                # 获取特定会话的对话
                session = self.conv_manager.get_session(session_id)
                if session:
                    for conv_id in session.conversation_ids:
                        conv = self.conv_manager.get_conversation(conv_id)
                        if conv:
                            conversations.append(conv)
            else:
                # 获取所有对话
                conversations = list(self.conv_manager._conversations.values())

            total = len(conversations)

            # 分页
            start = (page - 1) * page_size
            end = start + page_size
            paged_conversations = conversations[start:end]

            # 格式化输出
            conv_list = []
            for conv in paged_conversations:
                conv_list.append({
                    "conversation_id": conv.conversation_id,
                    "session_id": conv.session_id,
                    "title": conv.title,
                    "message_count": len(conv.messages),
                    "persona_id": conv.persona_id,
                    "kb_ids": conv.kb_ids,
                    "created_at": conv.created_at,
                    "updated_at": conv.updated_at,
                })

            return Response().ok(
                data={
                    "conversations": conv_list,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                },
                message="获取对话列表成功"
            ).to_dict()

        except Exception as e:
            logger.error(f"获取对话列表失败: {e}", exc_info=True)
            return Response().error(f"获取对话列表失败: {str(e)}").to_dict()

    async def create_conversation(self) -> Dict[str, Any]:
        """创建新对话

        请求体:
            session_id: 会话 ID
            title: 对话标题
            persona_id: 人格 ID（可选）
            kb_ids: 关联的知识库 ID 列表（可选）

        返回:
            创建结果
        """
        try:
            data = await request.get_json()
            session_id = data.get("session_id")
            title = data.get("title", "新对话")
            persona_id = data.get("persona_id")
            kb_ids = data.get("kb_ids", [])

            if not session_id:
                return Response().error("缺少 session_id 参数").to_dict()

            if not self.conv_manager:
                return Response().error("对话管理器未初始化").to_dict()

            # 创建对话
            conversation = self.conv_manager.create_conversation(
                session_id=session_id,
                title=title,
                persona_id=persona_id,
                kb_ids=kb_ids,
            )

            logger.info(f"创建对话: {conversation.conversation_id}")

            return Response().ok(
                data={"conversation_id": conversation.conversation_id},
                message="创建对话成功"
            ).to_dict()

        except Exception as e:
            logger.error(f"创建对话失败: {e}", exc_info=True)
            return Response().error(f"创建对话失败: {str(e)}").to_dict()

    async def get_conversation(self, id: str) -> Dict[str, Any]:
        """获取单个对话详情

        路径参数:
            id: 对话 ID

        返回:
            对话详细信息
        """
        try:
            if not self.conv_manager:
                return Response().error("对话管理器未初始化").to_dict()

            conversation = self.conv_manager.get_conversation(id)
            if not conversation:
                return Response().error(f"对话不存在: {id}").to_dict()

            info = {
                "conversation_id": conversation.conversation_id,
                "session_id": conversation.session_id,
                "title": conversation.title,
                "messages": conversation.messages,
                "persona_id": conversation.persona_id,
                "kb_ids": conversation.kb_ids,
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
            }

            return Response().ok(data=info, message="获取对话成功").to_dict()

        except Exception as e:
            logger.error(f"获取对话失败: {e}", exc_info=True)
            return Response().error(f"获取对话失败: {str(e)}").to_dict()

    async def update_conversation(self, id: str) -> Dict[str, Any]:
        """更新对话

        路径参数:
            id: 对话 ID

        请求体:
            title: 新标题（可选）
            persona_id: 新人格 ID（可选）
            kb_ids: 新知识库 ID 列表（可选）

        返回:
            更新结果
        """
        try:
            data = await request.get_json()
            title = data.get("title")
            persona_id = data.get("persona_id")
            kb_ids = data.get("kb_ids")

            if not self.conv_manager:
                return Response().error("对话管理器未初始化").to_dict()

            conversation = self.conv_manager.get_conversation(id)
            if not conversation:
                return Response().error(f"对话不存在: {id}").to_dict()

            # 更新对话
            if title is not None:
                conversation.title = title
            if persona_id is not None:
                conversation.persona_id = persona_id
            if kb_ids is not None:
                conversation.kb_ids = kb_ids

            # 保存更新
            self.conv_manager.update_conversation(id, title=title, persona_id=persona_id, kb_ids=kb_ids)

            logger.info(f"更新对话: {id}")

            return Response().ok(message="更新对话成功").to_dict()

        except Exception as e:
            logger.error(f"更新对话失败: {e}", exc_info=True)
            return Response().error(f"更新对话失败: {str(e)}").to_dict()

    async def delete_conversation(self, id: str) -> Dict[str, Any]:
        """删除对话

        路径参数:
            id: 对话 ID

        返回:
            删除结果
        """
        try:
            if not self.conv_manager:
                return Response().error("对话管理器未初始化").to_dict()

            self.conv_manager.delete_conversation(id)

            logger.info(f"删除对话: {id}")

            return Response().ok(message="删除对话成功").to_dict()

        except Exception as e:
            logger.error(f"删除对话失败: {e}", exc_info=True)
            return Response().error(f"删除对话失败: {str(e)}").to_dict()

    async def get_messages(self, id: str) -> Dict[str, Any]:
        """获取对话消息列表

        路径参数:
            id: 对话 ID

        查询参数:
            limit: 返回数量限制（默认 100）
            offset: 偏移量（默认 0）

        返回:
            消息列表
        """
        try:
            limit = int(request.args.get("limit", 100))
            offset = int(request.args.get("offset", 0))

            if not self.conv_manager:
                return Response().error("对话管理器未初始化").to_dict()

            conversation = self.conv_manager.get_conversation(id)
            if not conversation:
                return Response().error(f"对话不存在: {id}").to_dict()

            messages = conversation.messages[offset:offset + limit]

            return Response().ok(
                data={
                    "messages": messages,
                    "total": len(conversation.messages),
                    "limit": limit,
                    "offset": offset,
                },
                message="获取消息成功"
            ).to_dict()

        except Exception as e:
            logger.error(f"获取消息失败: {e}", exc_info=True)
            return Response().error(f"获取消息失败: {str(e)}").to_dict()

    async def add_message(self, id: str) -> Dict[str, Any]:
        """添加消息到对话

        路径参数:
            id: 对话 ID

        请求体:
            role: 角色 (user/assistant/system)
            content: 消息内容

        返回:
            添加结果
        """
        try:
            data = await request.get_json()
            role = data.get("role")
            content = data.get("content")

            if not role or not content:
                return Response().error("缺少必要参数").to_dict()

            if not self.conv_manager:
                return Response().error("对话管理器未初始化").to_dict()

            conversation = self.conv_manager.get_conversation(id)
            if not conversation:
                return Response().error(f"对话不存在: {id}").to_dict()

            # 添加消息
            message = {"role": role, "content": content}
            conversation.messages.append(message)

            # 保存更新
            self.conv_manager.add_message(id, role, content)

            logger.info(f"添加消息到对话 {id}: {role}")

            return Response().ok(message="添加消息成功").to_dict()

        except Exception as e:
            logger.error(f"添加消息失败: {e}", exc_info=True)
            return Response().error(f"添加消息失败: {str(e)}").to_dict()

    async def get_context(self, id: str) -> Dict[str, Any]:
        """获取对话上下文

        路径参数:
            id: 对话 ID

        返回:
            对话上下文
        """
        try:
            if not self.conv_manager:
                return Response().error("对话管理器未初始化").to_dict()

            conversation = self.conv_manager.get_conversation(id)
            if not conversation:
                return Response().error(f"对话不存在: {id}").to_dict()

            # 获取会话
            session = self.conv_manager.get_session(conversation.session_id)
            if not session:
                return Response().error(f"会话不存在: {conversation.session_id}").to_dict()

            context = {
                "conversation_id": id,
                "session_id": conversation.session_id,
                "platform_id": session.platform_id,
                "user_id": session.user_id,
                "channel_id": session.channel_id,
                "persona_id": conversation.persona_id,
                "kb_ids": conversation.kb_ids,
                "message_count": len(conversation.messages),
            }

            return Response().ok(data=context, message="获取上下文成功").to_dict()

        except Exception as e:
            logger.error(f"获取上下文失败: {e}", exc_info=True)
            return Response().error(f"获取上下文失败: {str(e)}").to_dict()

    async def list_templates(self) -> Dict[str, Any]:
        """列出对话模板

        返回:
            模板列表
        """
        try:
            # 从配置或数据库获取模板
            templates = []

            return Response().ok(data={"templates": templates}, message="获取模板成功").to_dict()

        except Exception as e:
            logger.error(f"获取模板失败: {e}", exc_info=True)
            return Response().error(f"获取模板失败: {str(e)}").to_dict()

    async def create_template(self) -> Dict[str, Any]:
        """创建对话模板

        请求体:
            name: 模板名称
            title: 默认标题
            persona_id: 默认人格 ID
            kb_ids: 默认知识库 ID 列表
            system_prompt: 系统提示词

        返回:
            创建结果
        """
        try:
            data = await request.get_json()
            name = data.get("name")
            title = data.get("title", "新对话")
            persona_id = data.get("persona_id")
            kb_ids = data.get("kb_ids", [])
            system_prompt = data.get("system_prompt")

            if not name:
                return Response().error("缺少 name 参数").to_dict()

            logger.info(f"创建对话模板: {name}")

            return Response().ok(message="创建模板成功").to_dict()

        except Exception as e:
            logger.error(f"创建模板失败: {e}", exc_info=True)
            return Response().error(f"创建模板失败: {str(e)}").to_dict()

    async def get_stats(self) -> Dict[str, Any]:
        """获取对话统计信息

        查询参数:
            session_id: 会话 ID（可选）

        返回:
            统计信息
        """
        try:
            session_id = request.args.get("session_id")

            if not self.conv_manager:
                return Response().error("对话管理器未初始化").to_dict()

            # 获取统计
            conversations = list(self.conv_manager._conversations.values())
            sessions = list(self.conv_manager._sessions.values())

            if session_id:
                conversations = [c for c in conversations if c.session_id == session_id]

            stats = {
                "total_conversations": len(conversations),
                "total_sessions": len(sessions),
                "total_messages": sum(len(c.messages) for c in conversations),
                "avg_messages_per_conversation": sum(len(c.messages) for c in conversations) / len(conversations) if conversations else 0,
            }

            return Response().ok(data=stats, message="获取统计成功").to_dict()

        except Exception as e:
            logger.error(f"获取统计失败: {e}", exc_info=True)
            return Response().error(f"获取统计失败: {str(e)}").to_dict()

    async def search_conversations(self) -> Dict[str, Any]:
        """搜索对话

        请求体:
            query: 搜索关键词
            session_id: 会话 ID（可选）
            limit: 返回数量限制（默认 10）

        返回:
            搜索结果
        """
        try:
            data = await request.get_json()
            query = data.get("query", "")
            session_id = data.get("session_id")
            limit = data.get("limit", 10)

            if not self.conv_manager:
                return Response().error("对话管理器未初始化").to_dict()

            # 搜索对话
            results = []
            for conv in self.conv_manager._conversations.values():
                if session_id and conv.session_id != session_id:
                    continue

                # 搜索标题和消息内容
                if query.lower() in conv.title.lower():
                    results.append(conv)
                    continue

                for msg in conv.messages:
                    if query.lower() in msg.get("content", "").lower():
                        results.append(conv)
                        break

                if len(results) >= limit:
                    break

            return Response().ok(
                data={"results": len(results), "conversations": [c.conversation_id for c in results]},
                message="搜索完成"
            ).to_dict()

        except Exception as e:
            logger.error(f"搜索对话失败: {e}", exc_info=True)
            return Response().error(f"搜索对话失败: {str(e)}").to_dict()

    async def list_sessions(self) -> Dict[str, Any]:
        """列出所有会话

        查询参数:
            page: 页码（默认1）
            page_size: 每页数量（默认10）

        返回:
            会话列表
        """
        try:
            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 10))

            if not self.conv_manager:
                return Response().ok(data={"sessions": [], "total": 0}, message="对话管理器未初始化").to_dict()

            sessions = list(self.conv_manager._sessions.values())
            total = len(sessions)

            # 分页
            start = (page - 1) * page_size
            end = start + page_size
            paged_sessions = sessions[start:end]

            # 格式化输出
            session_list = []
            for session in paged_sessions:
                session_list.append({
                    "session_id": session.session_id,
                    "platform_id": session.platform_id,
                    "user_id": session.user_id,
                    "channel_id": session.channel_id,
                    "current_conversation_id": session.current_conversation_id,
                    "conversation_count": len(session.conversation_ids),
                })

            return Response().ok(
                data={
                    "sessions": session_list,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                },
                message="获取会话列表成功"
            ).to_dict()

        except Exception as e:
            logger.error(f"获取会话列表失败: {e}", exc_info=True)
            return Response().error(f"获取会话列表失败: {str(e)}").to_dict()

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """获取单个会话详情

        路径参数:
            session_id: 会话 ID

        返回:
            会话详细信息
        """
        try:
            if not self.conv_manager:
                return Response().error("对话管理器未初始化").to_dict()

            session = self.conv_manager.get_session(session_id)
            if not session:
                return Response().error(f"会话不存在: {session_id}").to_dict()

            info = {
                "session_id": session.session_id,
                "platform_id": session.platform_id,
                "user_id": session.user_id,
                "channel_id": session.channel_id,
                "current_conversation_id": session.current_conversation_id,
                "conversation_ids": session.conversation_ids,
            }

            return Response().ok(data=info, message="获取会话成功").to_dict()

        except Exception as e:
            logger.error(f"获取会话失败: {e}", exc_info=True)
            return Response().error(f"获取会话失败: {str(e)}").to_dict()

    async def delete_session(self, session_id: str) -> Dict[str, Any]:
        """删除会话

        路径参数:
            session_id: 会话 ID

        返回:
            删除结果
        """
        try:
            if not self.conv_manager:
                return Response().error("对话管理器未初始化").to_dict()

            self.conv_manager.delete_session(session_id)

            logger.info(f"删除会话: {session_id}")

            return Response().ok(message="删除会话成功").to_dict()

        except Exception as e:
            logger.error(f"删除会话失败: {e}", exc_info=True)
            return Response().error(f"删除会话失败: {str(e)}").to_dict()

    async def switch_conversation(self, session_id: str) -> Dict[str, Any]:
        """切换会话的当前对话

        路径参数:
            session_id: 会话 ID

        请求体:
            conversation_id: 目标对话 ID

        返回:
            切换结果
        """
        try:
            data = await request.get_json()
            conversation_id = data.get("conversation_id")

            if not conversation_id:
                return Response().error("缺少 conversation_id 参数").to_dict()

            if not self.conv_manager:
                return Response().error("对话管理器未初始化").to_dict()

            session = self.conv_manager.get_session(session_id)
            if not session:
                return Response().error(f"会话不存在: {session_id}").to_dict()

            # 切换对话
            session.current_conversation_id = conversation_id

            logger.info(f"切换会话 {session_id} 到对话 {conversation_id}")

            return Response().ok(message="切换对话成功").to_dict()

        except Exception as e:
            logger.error(f"切换对话失败: {e}", exc_info=True)
            return Response().error(f"切换对话失败: {str(e)}").to_dict()
