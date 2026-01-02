"""NekoBot 工具系统

支持 JSON Schema 验证的工具定义和管理
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Awaitable, AsyncGenerator
from collections.abc import Coroutine
from dataclasses import dataclass, field
from enum import Enum
import jsonschema

from ..types import T_Context, MessageEventResult, StreamResponse


# ============== 工具 Schema ==============

@dataclass
class ToolSchema:
    """工具 Schema

    定义工具的接口，使用 JSON Schema 格式
    """
    name: str
    description: str
    parameters: dict[str, Any]

    def __post_init__(self):
        # 验证 JSON Schema 格式
        try:
            jsonschema.validate(
                self.parameters,
                jsonschema.Draft202012Validator.META_SCHEMA
            )
        except jsonschema.ValidationError as e:
            raise ValueError(f"Invalid JSON Schema for tool '{self.name}': {e}")

    def to_openai_format(self) -> dict[str, Any]:
        """转换为 OpenAI 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    def to_anthropic_format(self) -> dict[str, Any]:
        """转换为 Anthropic 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters
        }

    def to_gemini_format(self) -> dict[str, Any]:
        """转换为 Gemini 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

    def to_dict(self) -> dict[str, Any]:
        """转换为通用字典格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


# ============== 函数工具类型 ==============

ToolHandlerType = Callable[..., Awaitable[str | None] | AsyncGenerator[str | MessageEventResult, None]]


# ============== 函数工具 ==============

@dataclass
class FunctionTool(ToolSchema):
    """函数工具

    可调用的工具实现
    """
    handler: ToolHandlerType | None = None
    handler_module_path: str | None = None  # 重要！保存模块路径
    active: bool = True

    async def call(
        self,
        context: T_Context,
        **kwargs
    ) -> str | MessageEventResult | AsyncGenerator[str | MessageEventResult, None]:
        """调用工具

        Args:
            context: 调用上下文
            **kwargs: 工具参数

        Returns:
            工具执行结果
        """
        if not self.handler:
            raise NotImplementedError(f"Tool {self.name} has no handler")

        result = self.handler(context, **kwargs)

        if hasattr(result, '__aiter__'):
            # 异步生成器，直接返回
            return result
        else:
            # 协程，需要 await
            return await result


# ============== 工具集 ==============

@dataclass
class ToolSet:
    """工具集

    管理多个工具，提供查询和转换功能
    """
    tools: list[FunctionTool] = field(default_factory=list)

    def add_tool(self, tool: FunctionTool) -> None:
        """添加工具（覆盖同名工具）"""
        for i, existing in enumerate(self.tools):
            if existing.name == tool.name:
                self.tools[i] = tool
                return
        self.tools.append(tool)

    def remove_tool(self, name: str) -> None:
        """移除工具"""
        self.tools = [t for t in self.tools if t.name != name]

    def get_tool(self, name: str) -> FunctionTool | None:
        """获取工具"""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def has_tool(self, name: str) -> bool:
        """检查是否存在工具"""
        return self.get_tool(name) is not None

    def filter_active(self) -> "ToolSet":
        """过滤活跃的工具"""
        return ToolSet([t for t in self.tools if t.active])

    def empty(self) -> bool:
        """是否为空"""
        return len(self.tools) == 0

    def to_openai_format(self) -> list[dict]:
        """转换为 OpenAI 格式"""
        return [t.to_openai_format() for t in self.tools]

    def to_anthropic_format(self) -> list[dict]:
        """转换为 Anthropic 格式"""
        return [t.to_anthropic_format() for t in self.tools]

    def to_gemini_format(self) -> list[dict]:
        """转换为 Gemini 格式"""
        return [t.to_gemini_format() for t in self.tools]

    def to_dict(self) -> list[dict]:
        """转换为通用字典格式"""
        return [t.to_dict() for t in self.tools]

    def __len__(self) -> int:
        return len(self.tools)

    def __iter__(self):
        return iter(self.tools)

    def __contains__(self, name: str) -> bool:
        return self.has_tool(name)


# ============== 工具注册装饰器 ==============

def register_tool(
    name: str | None = None,
    description: str = "",
    parameters: dict[str, Any] | None = None
):
    """注册工具装饰器

    使用方式:
    ```python
    # 方式1：使用装饰器参数
    @register_tool(
        name="get_weather",
        description="获取天气信息",
        parameters={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称"
                }
            },
            "required": ["city"]
        }
    )
    async def get_weather(ctx: Context, city: str) -> str:
        return f"{city} 今天晴天"

    # 方式2：使用函数名作为工具名
    @register_tool()
    async def get_weather(ctx: Context, city: str) -> str:
        '''获取天气信息'''
        return f"{city} 今天晴天"
    ```
    """
    def decorator(func: ToolHandlerType) -> FunctionTool:
        # 从函数获取元数据
        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or ""
        tool_parameters = parameters or {
            "type": "object",
            "properties": {},
            "required": []
        }

        tool = FunctionTool(
            name=tool_name,
            description=tool_description,
            parameters=tool_parameters,
            handler=func,
            handler_module_path=func.__module__,
            active=True
        )

        # 将工具附加到函数上，方便注册
        func._nekobot_tool = tool  # type: ignore

        return func
    return decorator


# ============== 工具执行器 ==============

class ToolExecutor:
    """工具执行器

    负责执行工具调用
    """

    def __init__(self, tool_set: ToolSet):
        self.tool_set = tool_set

    async def execute(
        self,
        tool_name: str,
        context: T_Context,
        **kwargs
    ) -> str | MessageEventResult | AsyncGenerator[str | MessageEventResult, None]:
        """执行工具

        Args:
            tool_name: 工具名称
            context: 调用上下文
            **kwargs: 工具参数

        Returns:
            工具执行结果
        """
        tool = self.tool_set.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        if not tool.active:
            raise ValueError(f"Tool is not active: {tool_name}")

        return await tool.call(context, **kwargs)


# ============== 导出 ==============

__all__ = [
    "ToolSchema",
    "FunctionTool",
    "ToolSet",
    "ToolExecutor",
    "register_tool",
]
