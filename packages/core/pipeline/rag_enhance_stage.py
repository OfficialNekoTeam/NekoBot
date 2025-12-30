"""RAG 增强阶段

将知识库检索结果注入到 LLM 提示词中
"""

from typing import AsyncGenerator, Optional
from loguru import logger
from .stage import Stage, register_stage
from .context import PipelineContext
from ..core.knowledge_base import KnowledgeManager
from ..config import load_config


@register_stage
class RAGEnhanceStage(Stage):
    """RAG 增强阶段"""

    def __init__(self, ctx: PipelineContext) -> None:
        """初始化阶段"""
        logger.debug("RAGEnhanceStage 初始化")
        self.knowledge_manager = KnowledgeManager(ctx.db, {})

    async def initialize(self, ctx: PipelineContext) -> None:
        """初始化阶段"""
        logger.debug("RAGEnhanceStage 初始化完成")

    async def process(
        self,
        event: dict,
        ctx: PipelineContext
    ) -> Optional[AsyncGenerator[None, None]]:
        """处理消息事件，注入知识库检索结果"""
        post_type = event.get("post_type")

        if post_type == "message":
            await self._process_message(event, ctx)
        else:
            return None

    async def _process_message(self, event: dict, ctx: PipelineContext) -> None:
        """处理消息事件"""
        event.get("message_type", "private")
        event.get("user_id", "unknown")
        event.get("group_id", "private")

        # 获取 RAG 配置
        config = load_config()
        rag_config = config.get("rag", {})
        enabled = rag_config.get("enabled", False)
        threshold = rag_config.get("relevance_threshold", 0.7)
        max_docs = rag_config.get("max_docs", 5)

        if not enabled:
            logger.debug("RAG 未启用，跳过知识库检索")
            return

        logger.info(f"RAG 已启用，阈值: {threshold}，最大文档数: {max_docs}")

        # 提取查询内容
        message_text = self._extract_text_content(event)
        if not message_text:
            logger.debug("消息内容为空，跳过 RAG")
            return

        # 检索知识库
        retrieval_result = await self._retrieve_knowledge(message_text, threshold, max_docs)

        if not retrieval_result or not retrieval_result.results:
            logger.debug("知识库检索无结果，跳过 RAG 注入")
            return

        # 构建增强上下文
        enhanced_context = self._build_rag_context(retrieval_result, message_text)

        # 将增强上下文存储到 PipelineContext 中
        if "rag_context" not in ctx.data:
            ctx.data["rag_context"] = {}
        ctx.data["rag_context"][event.get("platform_id", "unknown")] = enhanced_context

        logger.debug(f"RAG 上下文已注入，包含 {len(retrieval_result.results)} 个相关文档")

    async def _extract_text_content(self, event: dict) -> str:
        """提取消息文本内容"""
        message = event.get("message", "")

        if isinstance(message, str):
            return message
        elif isinstance(message, list):
            # 过滤纯文本消息
            text_parts = []
            for segment in message:
                if segment.get("type") == "text":
                    text_parts.append(segment.get("data", {}).get("text", ""))

            return "".join(text_parts)
        else:
            return ""

    async def _retrieve_knowledge(
        self,
        query: str,
        threshold: float,
        max_docs: int
    ) -> Optional[dict]:
        """检索知识库

        Args:
            query: 查询内容
            threshold: 相似度阈值
            max_docs: 最大返回文档数

        Returns:
            检索结果
        """
        try:
            retrieval_result = await self.knowledge_manager.retrieve(
                query=query,
                top_k=max_docs,
                min_similarity=threshold
            )
            logger.info(f"知识库检索完成，返回 {len(retrieval_result.results)} 个文档")
            return retrieval_result
        except Exception as e:
            logger.error(f"知识库检索失败: {e}")
            return None

    def _build_rag_context(self, retrieval_result: dict, original_query: str) -> str:
        """构建 RAG 上下文"""
        if not retrieval_result or not retrieval_result.results:
            return ""

        # 构建上下文文本
        context_parts = []
        context_parts.append("<knowledge_context>")

        # 添加检索到的文档
        for i, doc in enumerate(retrieval_result.results[:retrieval_result.total_docs]):
            doc_id = doc.get("id", "")
            doc_title = doc.get("title", "")
            doc_content = doc.get("content", "")

            # 截断过长的内容
            if len(doc_content) > 500:
                doc_content = doc_content[:500] + "..."

            context_parts.append(f"<document_{i}>")
            context_parts.append(f"<document_{i}_id>{doc_id}")
            context_parts.append(f"<document_{i}_title>{doc_title}")
            context_parts.append(f"<document_{i}_content>{doc_content}")

        context_parts.append("</knowledge_context>")

        return "\n".join(context_parts)
