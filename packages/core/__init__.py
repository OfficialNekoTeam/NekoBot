"""NekoBot核心模块"""

__version__ = "1.0.0"

from .event_bus import event_bus, EventBus, EventPriority, on, on_any, emit, emit_sync
from .lifecycle import lifecycle, NekoBotLifecycle, get_lifecycle
from .database import DatabaseManager, db_manager
from .prompt_manager import PromptManager, prompt_manager
