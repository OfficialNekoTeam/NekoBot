"""NekoBot Agent 基类

支持类型安全、Hooks 机制的 Agent 系统
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Callable, Awaitable, AsyncIterator, AsyncGenerator
from dataclasses import dataclass, field
from collections.abc import AsyncGenerator as AsyncGenType
from enum import Enum

from ..types import T_Context, MessageEvent, AgentResponse, MessageChain, StreamResponse
from .hooks import BaseAgentHooks, CompositeAgentHooks, AgentHookContext, AgentHookPhase
from .tool_system import FunctionTool, ToolSet


# ============== Agent 配置 ==============

@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str
    llm_provider_id: str = "openai"
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 2000
    max_iterations: int = 10
    enable_stream: bool = False
    enable_tools: bool = True
    system_prompt: str | None = None
    tools: ToolSet = field(default_factory=ToolSet)
    hooks: list[BaseAgentHooks] = field(default_factory=list)
    metadata: dict[str, any] = field(default_factory=dict)


# ============== Agent 基类 ==============

class BaseAgent(ABC, Generic[T_Context]):
    """Agent 基类

    所有 Agent 的基础接口，支持类型安全的上下文传递
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self._hooks: CompositeAgentHooks | None = None

        # 组合所有 hooks
        if config.hooks:
            self._hooks = CompositeAgentHooks(*config.hooks)

    @property
    def name(self) -> str:
        """Agent 名称"""
        return self.config.name

    def add_hook(self, hook: BaseAgentHooks) -> None:
        """添加 Hook"""
        if self._hooks is None:
            self._hooks = CompositeAgentHooks(hook)
        else:
            self._hooks.add_hook(hook)

    def remove_hook(self, hook: BaseAgentHooks) -> None:
        """移除 Hook"""
        if self._hooks:
            self._hooks.remove_hook(hook)

    @abstractmethod
    async def chat(
        self,
        message: str | MessageChain,
        context: T_Context,
        stream: bool = False
    ) -> AgentResponse | StreamResponse:
        """与 Agent 对话

        Args:
            message: 用户消息
            context: 对话上下文
            stream: 是否流式响应

        Returns:
            AgentResponse 或流式响应
        """
        pass

    @abstractmethod
    async def chat_with_history(
        self,
        messages: list[dict[str, str]],
        context: T_Context,
        stream: bool = False
    ) -> AgentResponse | StreamResponse:
        """带历史记录的对话

        Args:
            messages: 消息历史 [{"role": "user", "content": "..."}, ...]
            context: 对话上下文
            stream: 是否流式响应

        Returns:
            AgentResponse 或流式响应
        """
        pass

    async def _run_with_hooks(
        self,
        input_text: str,
        context: T_Context,
        chat_func: Callable[[], Awaitable[AgentResponse | StreamResponse]]
    ) -> AgentResponse | StreamResponse:
        """带 Hooks 的执行

        Args:
            input_text: 输入文本
            context: 上下文
            chat_func: 实际的聊天函数

        Returns:
            AgentResponse 或流式响应
        """
        if not self._hooks:
            return await chat_func()

        # 前置 Hook
        pre_ctx = AgentHookContext(
            phase=AgentHookPhase.PRE_RUN,
            agent=self,  # type: ignore
            input_text=input_text
        )
        await self._hooks.pre_run(pre_ctx)

        try:
            result = await chat_func()

            # 处理流式响应
            if hasattr(result, '__aiter__'):
                # 包装流式响应以支持 on_stream_chunk Hook
                async def wrapped_stream() -> AsyncIterator[str]:
                    chunks = []
                    async for chunk in result:
                        # 流式块 Hook
                        chunk_ctx = AgentHookContext(
                            phase=AgentHookPhase.ON_STREAM_CHUNK,
                            agent=self,  # type: ignore
                            input_text=input_text,
                            output_text=chunk
                        )
                        processed_chunk = await self._hooks.on_stream_chunk(chunk_ctx, chunk)
                        chunks.append(processed_chunk)
                        yield processed_chunk

                    # 所有块收集完成后
                    final_output = "".join(chunks)
                    post_ctx = AgentHookContext(
                        phase=AgentHookPhase.POST_RUN,
                        agent=self,  # type: ignore
                        input_text=input_text,
                        output_text=final_output
                    )
                    await self._hooks.post_run(post_ctx)

                return wrapped_stream()

            else:
                # 非流式响应
                output_text = result.content if isinstance(result, AgentResponse) else str(result)

                # 后置 Hook
                post_ctx = AgentHookContext(
                    phase=AgentHookPhase.POST_RUN,
                    agent=self,  # type: ignore
                    input_text=input_text,
                    output_text=output_text
                )
                await self._hooks.post_run(post_ctx)

                return result

        except Exception as e:
            # 错误 Hook
            error_ctx = AgentHookContext(
                phase=AgentHookPhase.ON_ERROR,
                agent=self,  # type: ignore
                input_text=input_text,
                error=e
            )

            if self._hooks:
                handled_result = await self._hooks.on_error(error_ctx, e)
                if handled_result is not None:
                    return handled_result

            raise

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.config.name})"


# ============== LLM Agent 实现 ==============

class LLMAgent(BaseAgent[T_Context]):
    """基于 LLM 的 Agent 实现

    提供了基础的 LLM 聊天功能实现
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._llm_client = None  # 由子类初始化

    async def chat(
        self,
        message: str | MessageChain,
        context: T_Context,
        stream: bool = False
    ) -> AgentResponse | StreamResponse:
        """与 Agent 对话"""
        text = message.plain_text if isinstance(message, MessageChain) else message

        async def chat_func():
            return await self._chat(text, context, stream)

        return await self._run_with_hooks(text, context, chat_func)

    async def chat_with_history(
        self,
        messages: list[dict[str, str]],
        context: T_Context,
        stream: bool = False
    ) -> AgentResponse | StreamResponse:
        """带历史记录的对话"""
        async def chat_func():
            return await self._chat_with_messages(messages, context, stream)

        # 提取最后一条用户消息作为输入
        last_user_msg = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        return await self._run_with_hooks(last_user_msg, context, chat_func)

    @abstractmethod
    async def _chat(
        self,
        message: str,
        context: T_Context,
        stream: bool = False
    ) -> AgentResponse | StreamResponse:
        """实际聊天实现"""
        pass

    @abstractmethod
    async def _chat_with_messages(
        self,
        messages: list[dict[str, str]],
        context: T_Context,
        stream: bool = False
    ) -> AgentResponse | StreamResponse:
        """带消息历史的聊天实现"""
        pass

    def set_llm_client(self, client: any) -> None:
        """设置 LLM 客户端"""
        self._llm_client = client


# ============== Agent 执行器 ==============

class AgentExecutor:
    """Agent 执行器

    负责 Agent 的执行和管理
    """

    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent_id: str, agent: BaseAgent) -> None:
        """注册 Agent"""
        self._agents[agent_id] = agent

    def unregister(self, agent_id: str) -> None:
        """注销 Agent"""
        if agent_id in self._agents:
            del self._agents[agent_id]

    def get(self, agent_id: str) -> BaseAgent | None:
        """获取 Agent"""
        return self._agents.get(agent_id)

    def has(self, agent_id: str) -> bool:
        """检查 Agent 是否存在"""
        return agent_id in self._agents

    def list_agents(self) -> list[str]:
        """列出所有 Agent ID"""
        return list(self._agents.keys())

    async def execute(
        self,
        agent_id: str,
        message: str | MessageChain,
        context: T_Context,
        stream: bool = False
    ) -> AgentResponse | StreamResponse:
        """执行 Agent

        Args:
            agent_id: Agent ID
            message: 用户消息
            context: 对话上下文
            stream: 是否流式响应

        Returns:
            AgentResponse 或流式响应
        """
        agent = self.get(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        return await agent.chat(message, context, stream)

    def __len__(self) -> int:
        return len(self._agents)

    def __contains__(self, agent_id: str) -> bool:
        return self.has(agent_id)


# ============== 导出 ==============

__all__ = [
    "AgentConfig",
    "BaseAgent",
    "LLMAgent",
    "AgentExecutor",
]
