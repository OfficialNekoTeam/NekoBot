"""函数工具

用于LLM调用的普通函数工具
"""

from typing import Dict, Any, List, Optional
from loguru import logger

from .base import BaseTool


class FunctionTool(BaseTool):
    """函数工具
    
    封装普通Python函数，使其可被LLM调用
    """

    def __init__(
        self,
        func: callable,
        name: str,
        description: str = "",
        parameters_schema: Optional[Dict[str, Any]] = None,
    ):
        """初始化函数工具
        
        Args:
            func: 要封装的函数
            name: 工具名称
            description: 工具描述
            parameters_schema: 参数Schema定义
        """
        self._func = func
        self._name = name
        self._description = description
        self._parameters_schema = parameters_schema or {}

    @property
    def name(self) -> str:
        """工具名称"""
        return self._name

    @property
    def description(self) -> str:
        """工具描述"""
        return self._description

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        """参数Schema
        
        Returns:
            参数Schema字典
        """
        return self._parameters_schema

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
        try:
            # 检查函数签名
            import inspect
            sig = inspect.signature(self._func)
            
            # 过滤掉 'context' 参数（框架自动添加）
            params = {
                k: v
                for k, v in parameters.items()
                if k != "context"
            }
            
            # 执行函数
            result = self._func(**params)
            
            logger.info(f"函数工具 {self._name} 执行成功，结果: {result}")
            return result
            
        except Exception as e:
            logger.error(f"函数工具 {self._name} 执行失败: {e}")
            raise RuntimeError(f"工具执行错误: {e}")

    def __repr__(self) -> str:
        return f"FunctionTool({self._name})"

    @staticmethod
    def from_function(
        func: callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """从函数创建工具
        
        Args:
            func: 要封装的函数
            name: 工具名称（可选，默认使用函数名）
            description: 工具描述（可选）
            
        Returns:
            FunctionTool 实例
        """
        if name is None:
            name = func.__name__
        
        return FunctionTool(
            func=func,
            name=name,
            description=description or "",
        )

    @staticmethod
    def from_method(
        method: callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """从方法创建工具
        
        Args:
            method: 要封装的方法
            name: 工具名称（可选，默认使用方法名）
            description: 工具描述（可选）
            
        Returns:
            FunctionTool 实例
        """
        if name is None:
            name = method.__name__
        
        return FunctionTool(
            func=method,
            name=name,
            description=description or "",
        )