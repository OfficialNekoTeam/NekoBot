"""Agent工具基类

定义所有Agent工具的基类接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from loguru import logger


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