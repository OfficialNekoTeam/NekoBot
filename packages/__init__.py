"""NekoBot 核心 API 导出

提供统一的 API 入口，这是框架的公共接口层。
所有外部模块应该从这里导入。

使用示例:
```python
from packages import (
    MessageEvent,
    MessageChain,
    Context,
    register_plugin,
    register_command,
    config,
    logger,
)
```
"""

from typing import TYPE_CHECKING

# 版本信息
__version__ = "2.0.0"

# ============== 核心类型 ==============
from .types import (
    # 类型变量
    T as TypeVar,
    T_Context as TypeVar_Context,
    # 消息类型
    MessageType,
    MessageSegment,
    MessageChain,
    # 事件类型
    MessageEvent,
    CommandEvent,
    EventResultType,
    MessageEventResult,
    # Agent 类型
    AgentResponse,
    StreamResponse,
    # 上下文类型
    BaseContext,
    Context,
)

# ============== 核心实例 ==============
# Logger 是 loguru 库的直接导出
from loguru import logger as _logger
logger = _logger

# EventBus 从 core 模块导出
from .core import event_bus

# ============== Agent 相关 ==============
from .agent import (
    # 新架构
    AgentConfig,
    BaseAgent,
    LLMAgent,
    AgentExecutor,
    AgentHookPhase,
    AgentHookContext,
    BaseAgentHooks,
    CompositeAgentHooks,
    LoggingAgentHooks,
    MetricsAgentHooks,
    ToolSchema,
    FunctionTool,
    ToolSet,
    ToolExecutor,
    register_tool,
)

# ============== 平台相关 ==============
# 注意：这些需要在后续步骤中实现
# from .platform import (
#     BasePlatform,
#     PlatformManager,
#     PlatformMetadata,
# )

# ============== 插件相关 ==============
# 注意：这些需要在后续步骤中实现
# from .plugins import (
#     BasePlugin,
#     PluginMetadata,
#     PluginManager,
#     register_plugin,
#     register_command,
#     register_event_filter,
# )

# ============== 配置相关 ==============
from .config import (
    ConfigChangeType,
    ConfigChangeEvent,
    ConfigWatcher,
    ConfigManager,
    get_config_manager,
    config as config_manager,
)

# ============== 会话相关 ==============
from .conversation import (
    Session,
    Conversation,
    ConversationManager,
    SessionDeletedCallback,
)

# ============== Pipeline 相关 ==============
from .pipeline.scheduler_new import (
    BaseStage,
    SimpleStage,
    PipelineContext,
    PipelineScheduler,
    StagePriority,
    register_stage,
)

# ============== 导出列表 ==============
__all__ = [
    # 版本
    "__version__",
    # 核心类型
    "MessageType",
    "MessageSegment",
    "MessageChain",
    "MessageEvent",
    "CommandEvent",
    "EventResultType",
    "MessageEventResult",
    "AgentResponse",
    "StreamResponse",
    "BaseContext",
    "Context",
    "TypeVar",
    "TypeVar_Context",
    # 核心实例
    "logger",
    "event_bus",
    # Agent 相关
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
    "ToolSchema",
    "FunctionTool",
    "ToolSet",
    "ToolExecutor",
    "register_tool",
    # 配置相关
    "ConfigChangeType",
    "ConfigChangeEvent",
    "ConfigWatcher",
    "ConfigManager",
    "get_config_manager",
    "config_manager",
    # 会话相关
    "Session",
    "Conversation",
    "ConversationManager",
    "SessionDeletedCallback",
    # Pipeline 相关
    "BaseStage",
    "SimpleStage",
    "PipelineContext",
    "PipelineScheduler",
    "StagePriority",
    "register_stage",
]
