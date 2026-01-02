"""NekoBot 配置管理

支持配置变更监听和热重载
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from pathlib import Path
from enum import Enum
import json
import asyncio
from datetime import datetime
from loguru import logger


# ============== 配置变更类型 ==============

class ConfigChangeType(str, Enum):
    """配置变更类型"""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


# ============== 配置变更事件 ==============

@dataclass
class ConfigChangeEvent:
    """配置变更事件"""
    key: str
    old_value: Any | None
    new_value: Any | None
    change_type: ConfigChangeType
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        return f"ConfigChangeEvent({self.change_type.value}: {self.key})"


# ============== 配置监听器类型 ==============

ConfigWatcher = Callable[[ConfigChangeEvent], Awaitable[None]]


# ============== 配置管理器 ==============

class ConfigManager:
    """配置管理器

    支持配置变更监听和持久化
    """

    def __init__(self, config_path: str):
        """初始化配置管理器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self._config: dict[str, Any] = {}
        self._watchers: list[ConfigWatcher] = []
        self._lock = asyncio.Lock()
        self._loaded = False

    async def load(self) -> None:
        """加载配置"""
        async with self._lock:
            await self._load_config()

    async def _load_config(self) -> None:
        """加载配置文件"""
        if self.config_path.exists():
            try:
                content = await asyncio.to_thread(
                    self.config_path.read_text,
                    encoding='utf-8'
                )
                self._config = json.loads(content)
                logger.info(f"Loaded config from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                self._config = {}
        else:
            self._config = {}
            logger.info(f"Config file not found, using empty config: {self.config_path}")

        self._loaded = True

    async def save(self) -> None:
        """保存配置"""
        async with self._lock:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            content = json.dumps(
                self._config,
                indent=2,
                ensure_ascii=False
            )
            await asyncio.to_thread(
                self.config_path.write_text,
                content,
                encoding='utf-8'
            )
            logger.debug(f"Saved config to {self.config_path}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值

        支持点号分隔的路径，如 "llm.openai.api_key"

        Args:
            key: 配置键（支持点号路径）
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

        return value if value is not None else default

    async def set(
        self,
        key: str,
        value: Any,
        notify: bool = True,
        save: bool = True
    ) -> None:
        """设置配置值

        Args:
            key: 配置键（支持点号路径）
            value: 配置值
            notify: 是否触发变更通知
            save: 是否保存到文件
        """
        async with self._lock:
            old_value = self.get(key)

            keys = key.split('.')
            config = self._config

            # 导航到父级
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]

            # 设置值
            config[keys[-1]] = value

            # 确定变更类型
            if old_value is None:
                change_type = ConfigChangeType.ADDED
            elif value is None:
                change_type = ConfigChangeType.DELETED
            else:
                change_type = ConfigChangeType.MODIFIED

            # 保存到文件
            if save:
                await self.save()

            # 触发通知
            if notify:
                event = ConfigChangeEvent(
                    key=key,
                    old_value=old_value,
                    new_value=value,
                    change_type=change_type
                )
                await self._notify(event)

            logger.debug(f"Config set: {key} = {value}")

    async def delete(self, key: str, save: bool = True) -> bool:
        """删除配置值

        Args:
            key: 配置键
            save: 是否保存到文件

        Returns:
            是否删除成功
        """
        async with self._lock:
            keys = key.split('.')
            config = self._config

            # 导航到父级
            for k in keys[:-1]:
                if k not in config:
                    return False
                config = config[k]

            if keys[-1] not in config:
                return False

            old_value = config.pop(keys[-1])

            # 触发通知
            event = ConfigChangeEvent(
                key=key,
                old_value=old_value,
                new_value=None,
                change_type=ConfigChangeType.DELETED
            )
            await self._notify(event)

            # 保存到文件
            if save:
                await self.save()

            logger.debug(f"Config deleted: {key}")
            return True

    def watch(self, watcher: ConfigWatcher) -> None:
        """添加配置监听器

        Args:
            watcher: 监听器函数
        """
        self._watchers.append(watcher)
        logger.debug(f"Added config watcher: {watcher}")

    def remove_watcher(self, watcher: ConfigWatcher) -> None:
        """移除配置监听器

        Args:
            watcher: 监听器函数
        """
        if watcher in self._watchers:
            self._watchers.remove(watcher)
            logger.debug(f"Removed config watcher: {watcher}")

    async def _notify(self, event: ConfigChangeEvent) -> None:
        """通知所有监听器

        Args:
            event: 配置变更事件
        """
        for watcher in self._watchers:
            try:
                await watcher(event)
            except Exception as e:
                logger.error(f"Config watcher error: {e}")

    @property
    def config(self) -> dict[str, Any]:
        """获取完整配置（只读副本）"""
        return self._config.copy()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "config_path": str(self.config_path),
            "loaded": self._loaded,
            "config": self._config,
        }


# ============== 全局配置实例 ==============

_config_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例

    Returns:
        配置管理器实例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager("data/config/config.json")
    return _config_manager


# 导出全局实例
config = get_config_manager()


# ============== 导出 ==============

__all__ = [
    "ConfigChangeType",
    "ConfigChangeEvent",
    "ConfigWatcher",
    "ConfigManager",
    "get_config_manager",
    "config",
]
