"""Agent 系统

提供 MCP 协议支持、函数调用和 Agent 执行引擎
"""

# 新架构组件
from .base_new import AgentConfig, BaseAgent, LLMAgent, AgentExecutor
from .hooks import (
    AgentHookPhase,
    AgentHookContext,
    BaseAgentHooks,
    CompositeAgentHooks,
    LoggingAgentHooks,
    MetricsAgentHooks,
)
from .tool_system import (
    ToolCategory as NewToolCategory,
    ToolSchema,
    FunctionTool,
    ToolSet,
    ToolExecutor,
    register_tool,
    get_global_tool_set,
)

# 旧版工具系统（向后兼容）
try:
    from .tools import (
        BaseTool,
        ToolDefinition,
        ToolCategory,
        ToolCall,
        HandoffTool,
        ToolRegistry,
    )
except ImportError:
    pass

# 旧版组件（向后兼容）
try:
    from .base import BaseAgent as BaseAgentOld
except ImportError:
    pass

try:
    from .mcp import MCPClient, MCPServer
    from .executor import AgentExecutor as AgentExecutorOld
except ImportError:
    pass

__all__ = [
    # 新架构
    "AgentConfig",
    "BaseAgent",
    "LLMAgent",
    "AgentExecutor",
    "AgentHookPhase",
    "AgentHookContext",
    "BaseAgentHooks",
    "CompositeAgentHooks",
    "LoggingAgentHooks",
    "MetricsAgentHooks",
    "NewToolCategory",
    "ToolSchema",
    "FunctionTool",
    "ToolSet",
    "ToolExecutor",
    "register_tool",
    "get_global_tool_set",
    # 旧版组件（向后兼容）
    "BaseTool",
    "ToolDefinition",
    "ToolCategory",
    "ToolCall",
    "HandoffTool",
    "ToolRegistry",
    "MCPClient",
    "MCPServer",
]
