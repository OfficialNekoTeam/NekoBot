"""LLM 上下文管理器

提供会话历史管理和上下文压缩功能
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ContextCompressionStrategy(Enum):
    """上下文压缩策略"""

    NONE = "none"  # 不压缩
    FIFO = "fifo"  # 先进先出
    LRU = "lru"  # 最近最少使用
    SUMMARY = "summary"  # 摘要压缩
    CHAT_SUMMARY = "chat_summary"  # 聊天总结压缩


@dataclass
class MessageRecord:
    """消息记录"""

    role: str
    """消息角色（user, assistant, system）"""

    content: str
    """消息内容"""

    timestamp: datetime = field(default_factory=datetime.now)
    """消息时间戳"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """额外元数据"""


@dataclass
class ContextConfig:
    """上下文配置"""

    max_messages: int = 20
    """最大消息数量"""

    max_tokens: int = 4096
    """最大 token 数量（估算）"""

    compression_strategy: ContextCompressionStrategy = ContextCompressionStrategy.FIFO
    """压缩策略"""

    keep_system_messages: bool = True
    """是否保留系统消息"""

    enable_summary: bool = False
    """是否启用摘要压缩"""


class ContextManager:
    """上下文管理器

    管理会话历史和上下文压缩
    """

    def __init__(self, config: Optional[ContextConfig] = None) -> None:
        """初始化上下文管理器

        Args:
            config: 上下文配置
        """
        self.config = config or ContextConfig()
        self._messages: deque[MessageRecord] = deque()
        self._lock = asyncio.Lock()
        self._message_count = 0

    async def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """添加消息到上下文

        Args:
            role: 消息角色
            content: 消息内容
            metadata: 额外元数据
        """
        async with self._lock:
            record = MessageRecord(
                role=role,
                content=content,
                metadata=metadata or {},
            )
            self._messages.append(record)
            self._message_count += 1

            # 检查是否需要压缩
            await self._compress_if_needed()

    async def get_context(
        self,
        include_system: bool = True,
        max_messages: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """获取当前上下文

        Args:
            include_system: 是否包含系统消息
            max_messages: 最大消息数量（覆盖配置）

        Returns:
            上下文消息列表
        """
        async with self._lock:
            messages = list(self._messages)

            # 过滤系统消息
            if not include_system:
                messages = [m for m in messages if m.role != "system"]

            # 限制消息数量
            limit = max_messages or self.config.max_messages
            if len(messages) > limit:
                messages = messages[-limit:]

            # 转换为字典格式
            return [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    **m.metadata,
                }
                for m in messages
            ]

    async def pop_record(self, count: int = 1) -> list[MessageRecord]:
        """弹出最早的消息记录

        Args:
            count: 要弹出的记录数量

        Returns:
            被弹出的消息记录列表
        """
        async with self._lock:
            popped = []
            for _ in range(min(count, len(self._messages))):
                # 跳过系统消息（如果配置要求保留）
                if (
                    self.config.keep_system_messages
                    and self._messages[0].role == "system"
                ):
                    # 将系统消息移到队列末尾
                    system_msg = self._messages.popleft()
                    if self._messages:
                        popped.append(self._messages.popleft())
                    self._messages.appendleft(system_msg)
                else:
                    popped.append(self._messages.popleft())

            self._message_count -= len(popped)
            return popped

    async def clear(self) -> None:
        """清空上下文"""
        async with self._lock:
            self._messages.clear()
            self._message_count = 0

    async def get_message_count(self) -> int:
        """获取当前消息数量"""
        async with self._lock:
            return len(self._messages)

    async def estimate_tokens(self) -> int:
        """估算当前上下文的 token 数量

        Returns:
            估算的 token 数量
        """
        async with self._lock:
            # 简单估算：中文字符 * 1.5 + 英文单词 * 1
            total_tokens = 0
            for msg in self._messages:
                content = msg.content
                # 统计中文字符
                chinese_chars = sum(1 for c in content if "\u4e00" <= c <= "\u9fff")
                # 统计英文单词
                english_words = len(content.split())
                total_tokens += int(chinese_chars * 1.5 + english_words)

            return total_tokens

    async def _compress_if_needed(self) -> None:
        """检查并执行上下文压缩"""
        # 检查消息数量限制
        if len(self._messages) > self.config.max_messages:
            await self._compress_by_message_limit()

        # 检查 token 限制
        estimated_tokens = await self.estimate_tokens()
        if estimated_tokens > self.config.max_tokens:
            await self._compress_by_token_limit()

    async def _compress_by_message_limit(self) -> None:
        """根据消息数量限制压缩"""
        target_count = self.config.max_messages
        current_count = len(self._messages)

        if current_count <= target_count:
            return

        # 根据策略压缩
        if self.config.compression_strategy == ContextCompressionStrategy.FIFO:
            # 先进先出：移除最早的消息
            await self.pop_record(current_count - target_count)

        elif self.config.compression_strategy == ContextCompressionStrategy.LRU:
            # 最近最少使用：移除最早的消息（简化实现）
            await self.pop_record(current_count - target_count)

        elif self.config.compression_strategy in (
            ContextCompressionStrategy.SUMMARY,
            ContextCompressionStrategy.CHAT_SUMMARY,
        ):
            # 摘要压缩：将旧消息合并为摘要
            await self._compress_by_summary()

    async def _compress_by_token_limit(self) -> None:
        """根据 token 限制压缩"""
        target_tokens = self.config.max_tokens
        current_tokens = await self.estimate_tokens()

        if current_tokens <= target_tokens:
            return

        # 逐步移除消息直到满足 token 限制
        while current_tokens > target_tokens and len(self._messages) > 2:
            popped = await self.pop_record(1)
            if popped:
                current_tokens = await self.estimate_tokens()
            else:
                break

    async def _compress_by_summary(self) -> None:
        """使用摘要压缩

        将旧消息合并为摘要，保留最近的对话
        """
        # 保留最近的 5 条消息
        keep_count = 5
        if len(self._messages) <= keep_count:
            return

        # 获取要压缩的消息
        async with self._lock:
            messages_list = list(self._messages)
            old_messages = messages_list[:-keep_count]
            recent_messages = messages_list[-keep_count:]

            # 根据策略选择压缩方式
            if self.config.compression_strategy == ContextCompressionStrategy.SUMMARY:
                # 摘要压缩：将旧消息合并为简短摘要
                summary_parts = []
                for msg in old_messages:
                    if msg.role != "system":
                        # 只保留前 50 个字符作为摘要
                        summary = (
                            msg.content[:50] + "..."
                            if len(msg.content) > 50
                            else msg.content
                        )
                        summary_parts.append(f"[{msg.role}]: {summary}")

                summary_content = "\n".join(summary_parts)

                # 创建摘要消息
                summary_record = MessageRecord(
                    role="system",
                    content=f"以下是之前的对话摘要：\n{summary_content}",
                    metadata={"is_summary": True},
                )

                # 重建消息队列
                self._messages.clear()
                if self.config.keep_system_messages:
                    # 保留原有的系统消息
                    for msg in old_messages:
                        if msg.role == "system":
                            self._messages.append(msg)

                self._messages.append(summary_record)
                self._messages.extend(recent_messages)

            elif (
                self.config.compression_strategy
                == ContextCompressionStrategy.CHAT_SUMMARY
            ):
                # 聊天总结压缩：使用 LLM 生成对话总结
                # 这里应该调用 LLM 提供商来生成总结
                # 暂时使用简化实现
                user_messages = [m for m in old_messages if m.role == "user"]
                assistant_messages = [m for m in old_messages if m.role == "assistant"]

                if not user_messages:
                    return

                # 生成对话总结
                summary_parts = []
                for i, msg in enumerate(user_messages):
                    summary_parts.append(f"用户{i + 1}: {msg.content[:100]}")

                if assistant_messages:
                    for i, msg in enumerate(assistant_messages):
                        summary_parts.append(f"助手{i + 1}: {msg.content[:100]}")

                summary_content = "对话总结：\n" + "\n".join(summary_parts)

                # 创建总结消息
                summary_record = MessageRecord(
                    role="system",
                    content=summary_content,
                    metadata={"is_summary": True, "summary_type": "chat_summary"},
                )

                # 重建消息队列
                self._messages.clear()
                if self.config.keep_system_messages:
                    # 保留原有的系统消息
                    for msg in old_messages:
                        if msg.role == "system":
                            self._messages.append(msg)

                self._messages.append(summary_record)
                self._messages.extend(recent_messages)

    async def get_summary(self) -> str:
        """获取上下文摘要

        Returns:
            上下文摘要文本
        """
        messages = await self.get_context(include_system=False)
        if not messages:
            return "无对话历史"

        summary_parts = []
        for msg in messages[-10:]:  # 只取最近 10 条
            role_name = {"user": "用户", "assistant": "助手", "system": "系统"}.get(
                msg["role"], msg["role"]
            )
            content = (
                msg["content"][:100] + "..."
                if len(msg["content"]) > 100
                else msg["content"]
            )
            summary_parts.append(f"{role_name}: {content}")

        return "\n".join(summary_parts)
