"""插件基类和装饰器"""

import asyncio
import inspect
from typing import Dict, Any, Callable, List, Optional
from functools import wraps
from loguru import logger
from abc import ABC, abstractmethod


class BasePlugin(ABC):
    """插件基类"""

    def __init__(self):
        self.name = self.__class__.__name__
        self.version = "1.0.0"
        self.description = ""
        self.author = ""
        self.enabled = False
        self.commands: Dict[str, Callable] = {}
        self.message_handlers: List[Callable] = []
        # 平台服务器引用，用于发送消息
        self.platform_server = None
        # 插件配置 schema（从 _conf_schema.json 加载）
        self.conf_schema: Optional[Dict[str, Any]] = None

    @abstractmethod
    async def on_load(self):
        """插件加载时调用"""
        pass

    @abstractmethod
    async def on_unload(self):
        """插件卸载时调用"""
        pass

    async def on_enable(self):
        """插件启用时调用"""
        pass

    async def on_disable(self):
        """插件禁用时调用"""
        pass

    async def on_message(self, message):
        """收到消息时调用"""
        pass

    def set_platform_server(self, platform_server):
        """设置平台服务器引用"""
        self.platform_server = platform_server

    async def send_private_message(self, user_id: int, message: str) -> bool:
        """发送私聊消息"""
        from ..core.server import send_message

        # 创建一个模拟的事件对象来调用 send_message 函数
        event = {"message_type": "private", "user_id": user_id, "platform_id": "onebot"}
        await send_message(event, message)
        return True

    async def send_group_message(
        self, group_id: int, user_id: int, message: str
    ) -> bool:
        """发送群消息"""
        from ..core.server import send_message

        # 创建一个模拟的事件对象来调用 send_message 函数
        event = {
            "message_type": "group",
            "group_id": group_id,
            "user_id": user_id,
            "platform_id": "onebot",
        }
        await send_message(event, message)
        return True


# 装饰器实现
def register(command: str, description: str = "", aliases: List[str] = None):
    """注册命令装饰器"""

    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            return await func(self, *args, **kwargs)

        # 添加插件元数据
        if not hasattr(wrapper, "_nekobot_command"):
            wrapper._nekobot_command = {
                "name": command,
                "description": description,
                "aliases": aliases or [],
                "func": func,
            }
        return wrapper

    return decorator


def unregister(func):
    """注销命令装饰器"""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        return await func(self, *args, **kwargs)

    wrapper._nekobot_unregister = True
    return wrapper


def reload_plugin(func):
    """重载插件装饰器"""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        return await func(self, *args, **kwargs)

    wrapper._nekobot_reload = True
    return wrapper


def enable_plugin(func):
    """启用插件装饰器"""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        return await func(self, *args, **kwargs)

    wrapper._nekobot_enable = True
    return wrapper


def disable_plugin(func):
    """禁用插件装饰器"""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        return await func(self, *args, **kwargs)

    wrapper._nekobot_disable = True
    return wrapper


def export_commands(func):
    """导出命令装饰器"""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        return await func(self, *args, **kwargs)

    wrapper._nekobot_export = True
    return wrapper


def on_message(func):
    """消息处理器装饰器"""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        return await func(self, *args, **kwargs)

    wrapper._nekobot_on_message = True
    return wrapper


def on_private_message(func):
    """私聊消息处理器装饰器"""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        return await func(self, *args, **kwargs)

    wrapper._nekobot_on_private_message = True
    return wrapper


def on_group_message(func):
    """群消息处理器装饰器"""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        return await func(self, *args, **kwargs)

    wrapper._nekobot_on_group_message = True
    return wrapper


class PluginDecorator:
    """插件装饰器管理器"""

    def __init__(self, plugin_instance: BasePlugin):
        self.plugin = plugin_instance
        self._process_decorators()

    def _process_decorators(self):
        """处理插件中的装饰器"""
        # 遍历插件类的所有方法
        for name, method in inspect.getmembers(self.plugin, predicate=inspect.ismethod):
            self._process_method_decorators(method)

    def _process_method_decorators(self, method):
        """处理方法的装饰器"""
        # 处理命令注册
        if hasattr(method, "_nekobot_command"):
            cmd_info = method._nekobot_command
            self.plugin.commands[cmd_info["name"]] = method
            logger.info(f"注册命令: {cmd_info['name']}")

            # 注册到命令管理系统
            try:
                from ..core.command_management import register_command

                register_command(
                    handler_full_name=f"{self.plugin.name}.{method.__name__}",
                    handler_name=cmd_info["name"],
                    plugin_name=self.plugin.name,
                    module_path=self.plugin.__class__.__module__,
                    description=cmd_info.get("description", ""),
                    aliases=cmd_info.get("aliases", []),
                    permission="everyone",
                )
                logger.info(f"已将命令 {cmd_info['name']} 注册到命令管理系统")
            except ImportError:
                logger.warning("命令管理系统未导入，跳过命令注册")

        # 处理消息处理器
        if hasattr(method, "_nekobot_on_message"):
            self.plugin.message_handlers.append(method)
            logger.info(f"注册消息处理器: {method.__name__}")

        # 处理私聊消息处理器
        if hasattr(method, "_nekobot_on_private_message"):
            self.plugin.message_handlers.append(method)
            logger.info(f"注册私聊消息处理器: {method.__name__}")

        # 处理群消息处理器
        if hasattr(method, "_nekobot_on_group_message"):
            self.plugin.message_handlers.append(method)
            logger.info(f"注册群消息处理器: {method.__name__}")


def create_plugin_decorator(plugin_instance: BasePlugin) -> PluginDecorator:
    """创建插件装饰器管理器"""
    return PluginDecorator(plugin_instance)
