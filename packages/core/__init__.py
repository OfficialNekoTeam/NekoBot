"""NekoBot核心模块"""

__version__ = "2.0.0"

from .event_bus import event_bus, EventBus, EventPriority, on, on_any, emit, emit_sync
from .lifecycle import lifecycle, NekoBotLifecycle, get_lifecycle
from .agent import BaseAgent, FunctionTool, HandoffTool, ToolRegistry, agent_executor
from .agent import BaseAgent, FunctionTool, HandoffTool, ToolRegistry, agent_executor
