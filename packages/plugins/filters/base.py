"""插件过滤器基类

定义所有过滤器的基类接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class HandlerFilter(ABC):
    """处理器过滤器基类
    
    所有过滤器都应该继承此类并实现 filter 方法
    """

    @abstractmethod
    def filter(self, event: Dict[str, Any], config: Dict[str, Any]) -> bool:
        """过滤事件
        
        Args:
            event: 事件数据
            config: 配置数据
            
        Returns:
            True 表示通过过滤（继续处理），False 表示过滤掉（停止处理）
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}"