"""平台适配器基类"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from loguru import logger


class PlatformStatus(Enum):
    """平台运行状态"""

    PENDING = "pending"  # 待启动
    RUNNING = "running"  # 运行中
    ERROR = "error"  # 发生错误
    STOPPED = "stopped"  # 已停止


@dataclass
class PlatformError:
    """平台错误信息"""

    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    traceback: str | None = None


class BasePlatform(ABC):
    """平台适配器基类"""

    def __init__(
        self,
        platform_config: Dict[str, Any],
        platform_settings: Dict[str, Any],
        event_queue: Optional[asyncio.Queue] = None,
    ):
        self.config = platform_config
        self.settings = platform_settings
        self.event_queue = event_queue
        self.name = platform_config.get("type", "unknown")
        self.enabled = platform_config.get("enable", False)
        self.id = platform_config.get("id", "unknown")
        self.display_name = platform_config.get("name", self.name)

        # 平台运行状态
        self._status: PlatformStatus = PlatformStatus.PENDING
        self._errors: list[PlatformError] = []
        self._started_at: datetime | None = None

        # 消息统计
        self._message_count: int = 0
        self._previous_message_count: int = 0

    @abstractmethod
    async def start(self) -> None:
        """启动平台适配器"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止平台适配器"""
        pass

    @abstractmethod
    async def send_message(
        self, message_type: str, target_id: str, message: str, **kwargs
    ) -> Dict[str, Any]:
        """发送消息

        Args:
            message_type: 消息类型（private/group）
            target_id: 目标ID（用户ID/群ID）
            message: 消息内容
            **kwargs: 其他参数

        Returns:
            发送结果
        """
        pass

    async def handle_event(self, event: Dict[str, Any]) -> None:
        """处理平台事件

        Args:
            event: 事件数据
        """
        if self.event_queue:
            await self.event_queue.put(event)

    def is_enabled(self) -> bool:
        """检查平台是否启用"""
        return self.enabled

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self.config.get(key, default)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取设置项"""
        return self.settings.get(key, default)

    @property
    def status(self) -> PlatformStatus:
        """获取平台运行状态"""
        return self._status

    @status.setter
    def status(self, value: PlatformStatus):
        """设置平台运行状态"""
        self._status = value
        if value == PlatformStatus.RUNNING and self._started_at is None:
            self._started_at = datetime.now()

    @property
    def errors(self) -> list[PlatformError]:
        """获取错误列表"""
        return self._errors

    @property
    def last_error(self) -> PlatformError | None:
        """获取最近的错误"""
        return self._errors[-1] if self._errors else None

    def record_error(self, message: str, traceback_str: str | None = None):
        """记录一个错误"""
        self._errors.append(PlatformError(message=message, traceback=traceback_str))
        self._status = PlatformStatus.ERROR

    def clear_errors(self):
        """清除错误记录"""
        self._errors.clear()
        if self._status == PlatformStatus.ERROR:
            self._status = PlatformStatus.RUNNING

    def unified_webhook(self) -> bool:
        """是否正在使用统一 Webhook 模式"""
        return bool(
            self.config.get("unified_webhook_mode", False)
            and self.config.get("webhook_uuid")
        )

    def increment_message_count(self) -> None:
        """增加消息计数"""
        self._message_count += 1

    def get_message_count(self) -> int:
        """获取当前消息计数"""
        return self._message_count

    def reset_message_count(self) -> None:
        """重置消息计数（保存到 previous）"""
        self._previous_message_count = self._message_count
        self._message_count = 0

    def get_stats(self) -> dict:
        """获取平台统计信息"""
        return {
            "id": self.id,
            "type": self.name,
            "display_name": self.display_name,
            "status": self._status.value,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "error_count": len(self._errors),
            "last_error": {
                "message": self.last_error.message,
                "timestamp": self.last_error.timestamp.isoformat(),
                "traceback": self.last_error.traceback,
            }
            if self.last_error
            else None,
            "unified_webhook": self.unified_webhook(),
            "messages": self._message_count,
            "previous_messages": self._previous_message_count,
        }
