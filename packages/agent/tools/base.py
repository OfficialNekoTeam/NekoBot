"""Agent工具基类

定义所有Agent工具的基类接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Any, Optional


class ToolCategory(Enum):
    """工具类别枚举"""
    
    SYSTEM = "system"  # 系统工具
    SEARCH = "search"  # 搜索工具
    FILE = "file"  # 文件操作工具
    CALCULATION = "calculation"  # 计算工具
    COMMUNICATION = "communication"  # 通信工具
    UTILITY = "utility"  # 实用工具
    CUSTOM = "custom"  # 自定义工具


@dataclass
class ToolDefinition:
    """工具定义
    
    用于描述工具的元数据和配置信息
    """
    name: str
    """工具名称"""
    
    category: ToolCategory
    """工具类别"""
    
    description: str
    """工具描述"""
    
    function: Callable
    """工具函数"""
    
    enabled: bool = True
    """是否启用"""
    
    requires_permission: bool = False
    """是否需要权限"""
    
    permission_level: str = "user"
    """权限级别"""
    
    def __repr__(self) -> str:
        return f"ToolDefinition(name={self.name}, category={self.category}, enabled={self.enabled})"


@dataclass
class ToolCall:
    """工具调用记录
    
    记录工具调用的结果信息
    """
    tool_name: str
    """工具名称"""
    
    parameters: Dict[str, Any]
    """调用参数"""
    
    result: str
    """执行结果"""
    
    success: bool = True
    """是否成功"""
    
    error: Optional[str] = None
    """错误信息"""
    
    def __repr__(self) -> str:
        status = "成功" if self.success else "失败"
        return f"ToolCall(tool={self.tool_name}, status={status}, result={self.result})"


class BaseTool(ABC):
    """工具基类

    所有Agent工具都应该继承此类并实现 execute 方法
    """

    @abstractmethod
    async def execute(
        self,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """执行工具

        Args:
            parameters: 工具参数
            context: 执行上下文

        Returns:
            工具执行结果
        """
        pass

    @property
    def name(self) -> str:
        """工具名称

        Returns:
            工具名称
        """
        return self.__class__.__name__

    @property
    def description(self) -> str:
        """工具描述

        Returns:
            工具描述
        """
        return getattr(self, "__doc__", self.__class__.__name__)

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        """工具参数Schema

        Returns:
            参数Schema定义
        """
        return getattr(self, "_parameters_schema", {})

    def __repr__(self) -> str:
        return f"{self.name}"
