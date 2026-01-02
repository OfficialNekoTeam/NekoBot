"""NekoBot 工具系统

支持 JSON Schema 验证的工具调用系统
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, ParamSpec
from enum import Enum
import json
import inspect
from functools import wraps

from ..types import T_Context


# ============== 类型定义 ==============

P = ParamSpec('P')
ToolHandlerType = Callable[P, Awaitable[Any]]


# ============== 工具类别 ==============

class ToolCategory(str, Enum):
    """工具类别"""
    QUERY = "query"  # 查询类工具
    ACTION = "action"  # 操作类工具
    UTILITY = "utility"  # 实用工具
    HANDOFF = "handoff"  # 交接工具


# ============== 工具 Schema ==============

@dataclass
class ToolSchema:
    """工具 Schema 基类"""
    name: str  # 工具名称
    description: str  # 工具描述
    category: ToolCategory = ToolCategory.UTILITY
    parameters: dict[str, Any] = field(default_factory=dict)  # JSON Schema 格式的参数定义
    active: bool = True  # 是否激活

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    def to_openai_format(self) -> dict[str, Any]:
        """转换为 OpenAI 格式"""
        return self.to_dict()


# ============== 函数工具 ==============

@dataclass
class FunctionTool(ToolSchema):
    """函数工具

    将 Python 函数包装为可调用工具
    """
    handler: ToolHandlerType | None = None
    handler_module_path: str | None = None  # 用于动态加载
    metadata: dict[str, Any] = field(default_factory=dict)

    async def execute(self, **kwargs: Any) -> Any:
        """执行工具

        Args:
            **kwargs: 工具参数

        Returns:
            执行结果
        """
        if self.handler is None:
            raise RuntimeError(f"Tool {self.name} has no handler")

        # 调用处理函数
        if inspect.iscoroutinefunction(self.handler):
            return await self.handler(**kwargs)
        else:
            return self.handler(**kwargs)

    @classmethod
    def from_function(
        cls,
        func: Callable[P, Awaitable[Any]] | Callable[P, Any],
        name: str | None = None,
        description: str | None = None,
        category: ToolCategory = ToolCategory.UTILITY
    ) -> "FunctionTool":
        """从函数创建工具

        Args:
            func: 函数
            name: 工具名称（默认使用函数名）
            description: 工具描述（默认使用函数文档字符串）
            category: 工具类别

        Returns:
            FunctionTool 实例
        """
        # 提取函数签名
        sig = inspect.signature(func)
        parameters = {}

        # 构建 JSON Schema
        required = []
        props = {}

        for param_name, param in sig.parameters.items():
            # 跳过 self 和 context 参数
            if param_name in ('self', 'cls', 'context'):
                continue

            # 确定类型
            param_type = param.annotation
            if param_type == inspect.Parameter.empty:
                param_type = 'string'

            # 转换为 JSON Schema 类型
            json_type = _python_type_to_json_type(param_type)

            prop_def = {"type": json_type}

            # 处理默认值
            if param.default != inspect.Parameter.empty:
                prop_def["default"] = param.default
            else:
                required.append(param_name)

            # 从文档字符串提取描述
            # 简化处理，实际可以解析更详细的文档
            props[param_name] = prop_def

        parameters = {
            "type": "object",
            "properties": props
        }

        if required:
            parameters["required"] = required

        return cls(
            name=name or func.__name__,
            description=description or inspect.getdoc(func) or "",
            category=category,
            parameters=parameters,
            handler=func,
            metadata={"source": "function"}
        )


def _python_type_to_json_type(python_type: Any) -> str:
    """将 Python 类型转换为 JSON Schema 类型"""
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    # 处理泛型类型
    origin = getattr(python_type, "__origin__", None)
    if origin:
        return type_map.get(origin, "string")

    return type_map.get(python_type, "string")


# ============== 工具集 ==============

class ToolSet:
    """工具集

    管理多个工具
    """

    def __init__(self, tools: list[FunctionTool] | None = None):
        self._tools: dict[str, FunctionTool] = {}
        if tools:
            for tool in tools:
                self.add_tool(tool)

    def add_tool(self, tool: FunctionTool) -> None:
        """添加工具"""
        self._tools[tool.name] = tool

    def remove_tool(self, tool_name: str) -> bool:
        """移除工具"""
        if tool_name in self._tools:
            del self._tools[tool_name]
            return True
        return False

    def get_tool(self, tool_name: str) -> FunctionTool | None:
        """获取工具"""
        return self._tools.get(tool_name)

    def has_tool(self, tool_name: str) -> bool:
        """检查工具是否存在"""
        return tool_name in self._tools

    def list_tools(self, category: ToolCategory | None = None) -> list[FunctionTool]:
        """列出工具

        Args:
            category: 可选的类别过滤器

        Returns:
            工具列表
        """
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def to_openai_format(self) -> list[dict[str, Any]]:
        """转换为 OpenAI 格式"""
        return [tool.to_openai_format() for tool in self.list_tools() if tool.active]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, tool_name: str) -> bool:
        return self.has_tool(tool_name)

    def __iter__(self):
        return iter(self._tools.values())


# ============== 工具执行器 ==============

class ToolExecutor:
    """工具执行器

    负责工具的验证和执行
    """

    def __init__(self, tool_set: ToolSet):
        self.tool_set = tool_set

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: T_Context | None = None
    ) -> Any:
        """执行工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            context: 执行上下文

        Returns:
            执行结果

        Raises:
            ValueError: 工具不存在
            RuntimeError: 执行失败
        """
        tool = self.tool_set.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        # 验证参数
        self._validate_arguments(tool, arguments)

        # 执行工具
        try:
            result = await tool.execute(**arguments)
            return result
        except Exception as e:
            raise RuntimeError(f"Tool execution failed: {tool_name}: {e}") from e

    def _validate_arguments(self, tool: FunctionTool, arguments: dict[str, Any]) -> None:
        """验证工具参数

        Args:
            tool: 工具
            arguments: 参数

        Raises:
            ValueError: 参数验证失败
        """
        schema = tool.parameters
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        # 检查必需参数
        for param in required:
            if param not in arguments:
                raise ValueError(f"Missing required parameter: {param}")

        # 检查参数类型
        for param_name, param_value in arguments.items():
            if param_name in properties:
                param_schema = properties[param_name]
                expected_type = param_schema.get("type")
                if expected_type:
                    self._check_type(param_name, param_value, expected_type)

    def _check_type(self, param_name: str, value: Any, expected_type: str) -> None:
        """检查参数类型"""
        type_checks = {
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
        }

        check_func = type_checks.get(expected_type)
        if check_func and not check_func(value):
            raise ValueError(
                f"Parameter '{param_name}' should be {expected_type}, got {type(value).__name__}"
            )


# ============== 工具装饰器 ==============

def register_tool(
    name: str | None = None,
    description: str | None = None,
    category: ToolCategory = ToolCategory.UTILITY
) -> Callable:
    """注册工具装饰器

    使用示例:
    ```python
    @register_tool(
        name="get_weather",
        description="获取天气信息",
        category=ToolCategory.QUERY
    )
    async def get_weather(city: str) -> str:
        return f"{city}的天气是晴天"
    ```

    Args:
        name: 工具名称
        description: 工具描述
        category: 工具类别

    Returns:
        装饰器函数
    """

    def decorator(func: Callable[P, Awaitable[Any]] | Callable[P, Any]) -> FunctionTool:
        tool = FunctionTool.from_function(
            func=func,
            name=name,
            description=description,
            category=category
        )
        # 这里可以注册到全局工具注册表
        # _global_tool_registry.register(tool)
        return func

    return decorator


# ============== 全局工具注册表 ==============

_global_tool_set: ToolSet | None = None


def get_global_tool_set() -> ToolSet:
    """获取全局工具集"""
    global _global_tool_set
    if _global_tool_set is None:
        _global_tool_set = ToolSet()
    return _global_tool_set


# ============== 导出 ==============

__all__ = [
    "ToolCategory",
    "ToolSchema",
    "FunctionTool",
    "ToolSet",
    "ToolExecutor",
    "register_tool",
    "get_global_tool_set",
    "ToolHandlerType",
]
