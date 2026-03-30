try:
    from importlib.metadata import version as _pkg_version
    __version__: str = _pkg_version("nekobot")
except Exception:
    try:
        import tomllib as _tomllib
        from pathlib import Path as _Path
        _pyproject = _Path(__file__).parent.parent / "pyproject.toml"
        __version__ = _tomllib.loads(_pyproject.read_text())["project"]["version"]
        del _tomllib, _Path, _pyproject
    except Exception:
        __version__ = "0.0.0"

from .app import NekoBotFramework, create_framework
from .conversations import (
    ConfigurationContext,
    ConversationContext,
    ConversationResolver,
)
from .moderation import ModerationService
from .permissions import PermissionEngine
from .plugins import BasePlugin
from .providers import ChatProvider, ProviderRegistry
from .runtime import EffectivePluginBinding, ExecutionContext, PluginContext

__all__ = [
    "__version__",
    "BasePlugin",
    "ChatProvider",
    "ConfigurationContext",
    "ConversationContext",
    "ConversationResolver",
    "EffectivePluginBinding",
    "ExecutionContext",
    "ModerationService",
    "NekoBotFramework",
    "PermissionEngine",
    "PluginContext",
    "ProviderRegistry",
    "create_framework",
]
