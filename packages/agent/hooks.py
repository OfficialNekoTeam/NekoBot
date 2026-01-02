"""NekoBot Agent Hooks 系统

支持 Agent 生命周期的钩子机制
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic

from ..types import T_Context, AgentResponse


# ============== Hook 阶段枚举 ==============

class AgentHookPhase(str, Enum):
    """Agent Hook 阶段"""
    PRE_RUN = "pre_run"
    POST_RUN = "post_run"
    ON_TOOL_CALL = "on_tool_call"
    ON_STREAM_CHUNK = "on_stream_chunk"
    ON_ERROR = "on_error"


# ============== Hook 上下文 ==============

@dataclass
class AgentHookContext:
    """Hook 上下文

    传递给 Hook 的上下文信息
    """
    phase: AgentHookPhase
    agent: "Agent"  # type: ignore
    input_text: str
    output_text: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    error: Exception | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_pre_run(self) -> bool:
        return self.phase == AgentHookPhase.PRE_RUN

    @property
    def is_post_run(self) -> bool:
        return self.phase == AgentHookPhase.POST_RUN

    @property
    def is_tool_call(self) -> bool:
        return self.phase == AgentHookPhase.ON_TOOL_CALL

    @property
    def is_error(self) -> bool:
        return self.phase == AgentHookPhase.ON_ERROR


# ============== Hooks 基类 ==============

class BaseAgentHooks(ABC, Generic[T_Context]):
    """Agent Hooks 基类

    定义 Agent 生命周期的钩子
    """

    async def pre_run(self, ctx: AgentHookContext) -> None:
        """运行前钩子

        在 Agent 执行前调用，可以修改输入或执行初始化逻辑
        """
        pass

    async def post_run(self, ctx: AgentHookContext) -> None:
        """运行后钩子

        在 Agent 执行后调用，可以处理输出或执行清理逻辑
        """
        pass

    async def on_tool_call(
        self,
        ctx: AgentHookContext,
        tool_name: str,
        tool_args: dict[str, Any]
    ) -> dict[str, Any] | None:
        """工具调用钩子

        在工具调用前调用，可以：
        - 修改工具参数
        - 阻止工具调用（返回 None）
        - 记录日志

        Returns:
            修改后的参数，返回 None 则不阻止调用
        """
        return None

    async def on_stream_chunk(
        self,
        ctx: AgentHookContext,
        chunk: str
    ) -> str:
        """流式响应块钩子

        在每个流式响应块返回时调用，可以修改响应内容

        Returns:
            修改后的内容
        """
        return chunk

    async def on_error(
        self,
        ctx: AgentHookContext,
        error: Exception
    ) -> AgentResponse | None:
        """错误处理钩子

        在 Agent 执行出错时调用，可以：
        - 返回自定义响应（阻止异常）
        - 记录错误日志
        - 返回 None 让异常继续传播

        Returns:
            自定义响应，返回 None 则重新抛出异常
        """
        return None


# ============== 组合 Hooks ==============

class CompositeAgentHooks(BaseAgentHooks[T_Context]):
    """组合 Hooks

    将多个 Hooks 组合在一起，按顺序执行
    """

    def __init__(self, *hooks: BaseAgentHooks[T_Context]):
        self._hooks = list(hooks)

    def add_hook(self, hook: BaseAgentHooks[T_Context]) -> None:
        """添加 Hook"""
        self._hooks.append(hook)

    def remove_hook(self, hook: BaseAgentHooks[T_Context]) -> None:
        """移除 Hook"""
        if hook in self._hooks:
            self._hooks.remove(hook)

    async def pre_run(self, ctx: AgentHookContext) -> None:
        for hook in self._hooks:
            await hook.pre_run(ctx)

    async def post_run(self, ctx: AgentHookContext) -> None:
        for hook in self._hooks:
            await hook.post_run(ctx)

    async def on_tool_call(
        self,
        ctx: AgentHookContext,
        tool_name: str,
        tool_args: dict[str, Any]
    ) -> dict[str, Any] | None:
        for hook in self._hooks:
            result = await hook.on_tool_call(ctx, tool_name, tool_args)
            if result is not None:
                tool_args = result
        return tool_args

    async def on_stream_chunk(
        self,
        ctx: AgentHookContext,
        chunk: str
    ) -> str:
        result = chunk
        for hook in self._hooks:
            result = await hook.on_stream_chunk(ctx, result)
        return result

    async def on_error(
        self,
        ctx: AgentHookContext,
        error: Exception
    ) -> AgentResponse | None:
        for hook in self._hooks:
            result = await hook.on_error(ctx, error)
            if result is not None:
                return result
        return None


# ============== 常用 Hooks 实现 ==============

class LoggingAgentHooks(BaseAgentHooks[T_Context]):
    """日志记录 Hooks

    记录 Agent 的执行过程
    """

    from loguru import logger

    async def pre_run(self, ctx: AgentHookContext) -> None:
        self.logger.info(f"[Agent:{ctx.agent.name}] Pre-run: {ctx.input_text[:100]}")

    async def post_run(self, ctx: AgentHookContext) -> None:
        self.logger.info(f"[Agent:{ctx.agent.name}] Post-run: {ctx.output_text[:100] if ctx.output_text else ''}")

    async def on_tool_call(
        self,
        ctx: AgentHookContext,
        tool_name: str,
        tool_args: dict[str, Any]
    ) -> None:
        self.logger.debug(f"[Agent:{ctx.agent.name}] Tool call: {tool_name}({tool_args})")

    async def on_error(
        self,
        ctx: AgentHookContext,
        error: Exception
    ) -> None:
        self.logger.error(f"[Agent:{ctx.agent.name}] Error: {error}")


class MetricsAgentHooks(BaseAgentHooks[T_Context]):
    """指标收集 Hooks

    收集 Agent 执行的指标数据
    """

    def __init__(self):
        from collections import defaultdict
        self.metrics = defaultdict(lambda: {
            "count": 0,
            "total_tokens": 0,
            "total_time": 0.0,
            "error_count": 0
        })
        self._current_start_time = 0.0

    async def pre_run(self, ctx: AgentHookContext) -> None:
        import time
        self._current_start_time = time.time()

    async def post_run(self, ctx: AgentHookContext) -> None:
        import time
        duration = time.time() - self._current_start_time
        agent_name = ctx.agent.name
        self.metrics[agent_name]["count"] += 1
        self.metrics[agent_name]["total_time"] += duration

        if ctx.metadata and "usage" in ctx.metadata:
            self.metrics[agent_name]["total_tokens"] += ctx.metadata["usage"].get("total_tokens", 0)

    async def on_error(
        self,
        ctx: AgentHookContext,
        error: Exception
    ) -> None:
        agent_name = ctx.agent.name
        self.metrics[agent_name]["error_count"] += 1

    def get_metrics(self, agent_name: str) -> dict[str, any]:
        """获取指定 Agent 的指标"""
        return dict(self.metrics.get(agent_name, {}))


# ============== 导出 ==============

__all__ = [
    "AgentHookPhase",
    "AgentHookContext",
    "BaseAgentHooks",
    "CompositeAgentHooks",
    "LoggingAgentHooks",
    "MetricsAgentHooks",
]
