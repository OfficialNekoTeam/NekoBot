"""事件总线系统

提供解耦的事件驱动架构，支持事件的注册、分发、监听等功能
"""

import asyncio
from asyncio import Queue
from typing import Callable, Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
from loguru import logger
import inspect


class EventPriority(Enum):
    """事件优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class EventHandler:
    """事件处理器信息"""
    handler: Callable
    priority: EventPriority = EventPriority.NORMAL
    once: bool = False
    filter_func: Optional[Callable[[dict], bool]] = None
    name: Optional[str] = None


class EventBus:
    """事件总线

    提供事件驱动的架构，支持：
    - 事件注册和监听
    - 事件分发
    - 事件优先级
    - 事件过滤
    - 一次性事件处理器
    """

    def __init__(self, event_queue: Optional[Queue] = None):
        """初始化事件总线

        Args:
            event_queue: 事件队列（可选，用于与现有系统集成）
        """
        # 事件队列
        self.event_queue = event_queue or asyncio.Queue()

        # 事件监听器映射: event_type -> List[EventHandler]
        self._listeners: Dict[str, List[EventHandler]] = {}

        # 全局事件监听器
        self._global_listeners: List[EventHandler] = []

        # 已触发的一次性处理器集合
        self._triggered_once: Set[str] = set()

        # 事件分发任务
        self._dispatch_task: Optional[asyncio.Task] = None

        # 是否正在运行
        self._running = False

    async def start(self):
        """启动事件总线"""
        if self._running:
            logger.warning("事件总线已在运行中")
            return

        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        logger.info("事件总线已启动")

    async def stop(self):
        """停止事件总线"""
        if not self._running:
            return

        self._running = False

        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass

        logger.info("事件总线已停止")

    async def _dispatch_loop(self):
        """事件分发循环"""
        while self._running:
            try:
                event_data = await self.event_queue.get()
                await self.dispatch(event_data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"事件分发循环出错: {e}")

    async def put_event(self, event_type: str, data: dict):
        """发送事件到事件队列

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        event = {
            "type": event_type,
            "data": data,
            "timestamp": asyncio.get_event_loop().time(),
        }
        await self.event_queue.put(event)
        logger.debug(f"事件已加入队列: {event_type}")

    def on(
        self,
        event_type: str,
        priority: EventPriority = EventPriority.NORMAL,
        once: bool = False,
        filter_func: Optional[Callable[[dict], bool]] = None,
        name: Optional[str] = None,
    ):
        """事件监听装饰器

        Args:
            event_type: 事件类型
            priority: 事件优先级
            once: 是否只触发一次
            filter_func: 事件过滤函数
            name: 处理器名称

        Example:
            @event_bus.on("message", priority=EventPriority.HIGH)
            async def handle_message(event):
                print(f"收到消息: {event}")
        """

        def decorator(func):
            # 生成唯一处理器ID
            handler_id = f"{event_type}.{func.__name__}.{id(func)}"

            # 创建事件处理器
            handler = EventHandler(
                handler=func,
                priority=priority,
                once=once,
                filter_func=filter_func,
                name=name or handler_id,
            )

            # 注册监听器
            if event_type not in self._listeners:
                self._listeners[event_type] = []

            self._listeners[event_type].append(handler)

            # 按优先级排序
            self._listeners[event_type].sort(key=lambda h: h.priority.value, reverse=True)

            logger.debug(f"已注册事件监听器: {event_type} -> {handler.name}")

            return func

        return decorator

    def on_any(
        self,
        priority: EventPriority = EventPriority.NORMAL,
        once: bool = False,
        filter_func: Optional[Callable[[dict], bool]] = None,
        name: Optional[str] = None,
    ):
        """全局事件监听装饰器

        Args:
            priority: 事件优先级
            once: 是否只触发一次
            filter_func: 事件过滤函数
            name: 处理器名称
        """

        def decorator(func):
            handler_id = f"global.{func.__name__}.{id(func)}"

            handler = EventHandler(
                handler=func,
                priority=priority,
                once=once,
                filter_func=filter_func,
                name=name or handler_id,
            )

            self._global_listeners.append(handler)

            # 按优先级排序
            self._global_listeners.sort(key=lambda h: h.priority.value, reverse=True)

            logger.debug(f"已注册全局事件监听器: {handler.name}")

            return func

        return decorator

    def add_listener(
        self,
        event_type: str,
        handler: Callable,
        priority: EventPriority = EventPriority.NORMAL,
        once: bool = False,
        filter_func: Optional[Callable[[dict], bool]] = None,
    ):
        """添加事件监听器

        Args:
            event_type: 事件类型
            handler: 处理函数
            priority: 事件优先级
            once: 是否只触发一次
            filter_func: 事件过滤函数
        """
        handler_id = f"{event_type}.{handler.__name__}.{id(handler)}"

        event_handler = EventHandler(
            handler=handler,
            priority=priority,
            once=once,
            filter_func=filter_func,
            name=handler_id,
        )

        if event_type not in self._listeners:
            self._listeners[event_type] = []

        self._listeners[event_type].append(event_handler)

        # 按优先级排序
        self._listeners[event_type].sort(key=lambda h: h.priority.value, reverse=True)

        logger.debug(f"已添加事件监听器: {event_type} -> {handler_id}")

    def remove_listener(self, event_type: str, handler: Callable):
        """移除事件监听器

        Args:
            event_type: 事件类型
            handler: 处理函数
        """
        if event_type not in self._listeners:
            return

        self._listeners[event_type] = [
            h for h in self._listeners[event_type]
            if h.handler != handler
        ]

        logger.debug(f"已移除事件监听器: {event_type}")

    async def dispatch(self, event: dict):
        """分发事件到所有监听器

        Args:
            event: 事件数据，格式: {"type": str, "data": dict, "timestamp": float}
        """
        event_type = event.get("type", "unknown")
        event_data = event.get("data", {})

        # 分发到特定类型的监听器
        listeners = self._listeners.get(event_type, [])

        # 分发到全局监听器
        all_listeners = listeners + self._global_listeners

        for handler in all_listeners[:]:  # 复制列表，允许在处理中修改
            # 检查是否是一次性处理器且已触发
            if handler.once and handler.name in self._triggered_once:
                continue

            # 检查过滤条件
            if handler.filter_func and not handler.filter_func(event_data):
                continue

            try:
                # 检查是否是协程
                if inspect.iscoroutinefunction(handler.handler):
                    await handler.handler(event_data)
                else:
                    handler.handler(event_data)

                # 标记一次性处理器为已触发
                if handler.once:
                    self._triggered_once.add(handler.name)
                    # 从列表中移除
                    if handler in listeners:
                        listeners.remove(handler)
                    if handler in self._global_listeners:
                        self._global_listeners.remove(handler)

                logger.debug(f"事件已处理: {event_type} -> {handler.name}")

            except Exception as e:
                logger.error(f"事件处理器 {handler.name} 执行出错: {e}")

    def get_listeners(self, event_type: Optional[str] = None) -> List[EventHandler]:
        """获取事件监听器列表

        Args:
            event_type: 事件类型，为 None 时返回所有监听器

        Returns:
            事件监听器列表
        """
        if event_type:
            return self._listeners.get(event_type, []).copy()
        else:
            all_listeners = []
            for listeners in self._listeners.values():
                all_listeners.extend(listeners)
            all_listeners.extend(self._global_listeners)
            return all_listeners

    def clear_listeners(self, event_type: Optional[str] = None):
        """清除事件监听器

        Args:
            event_type: 事件类型，为 None 时清除所有监听器
        """
        if event_type:
            self._listeners.pop(event_type, None)
            logger.debug(f"已清除事件类型 {event_type} 的所有监听器")
        else:
            self._listeners.clear()
            self._global_listeners.clear()
            self._triggered_once.clear()
            logger.debug("已清除所有事件监听器")

    def emit(self, event_type: str, data: dict):
        """同步发送事件（立即处理）

        Args:
            event_type: 事件类型
            data: 事件数据

        Note:
            此方法会立即分发事件，不经过事件队列
        """
        event = {
            "type": event_type,
            "data": data,
            "timestamp": asyncio.get_event_loop().time(),
        }

        # 在当前事件循环中调度
        asyncio.create_task(self.dispatch(event))
        logger.debug(f"事件已立即分发: {event_type}")


# 创建全局事件总线实例
event_bus = EventBus()


# 便捷函数
def on(event_type: str, **kwargs):
    """便捷的事件监听装饰器

    Args:
        event_type: 事件类型
        **kwargs: 其他参数传递给 EventBus.on
    """
    return event_bus.on(event_type, **kwargs)


def on_any(**kwargs):
    """便捷的全局事件监听装饰器

    Args:
        **kwargs: 其他参数传递给 EventBus.on_any
    """
    return event_bus.on_any(**kwargs)


async def emit(event_type: str, data: dict):
    """便捷的事件发送函数

    Args:
        event_type: 事件类型
        data: 事件数据
    """
    await event_bus.put_event(event_type, data)


def emit_sync(event_type: str, data: dict):
    """便捷的同步事件发送函数

    Args:
        event_type: 事件类型
        data: 事件数据
    """
    event_bus.emit(event_type, data)


# 显式导出的符号
__all__ = [
    "EventBus",
    "EventPriority",
    "event_bus",
    "on",
    "on_any",
    "emit",
    "emit_sync"
]
