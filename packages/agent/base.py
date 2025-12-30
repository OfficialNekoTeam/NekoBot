"""Agent基类

定义所有Agent的基类接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from loguru import logger


class BaseAgent(ABC):
    """Agent基类
    
    所有Agent都应该继承此类并实现核心方法
    """

    @abstractmethod
    async def process_message(
        self,
        message: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[str]:
        """处理消息
        
        Args:
            message: 消息数据
            context: 对话上下文
            
        Returns:
            Agent响应，如果Agent无法处理则返回 None
        """
        pass

    @abstractmethod
    async def call_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> Any:
        """调用工具
        
        Args:
            tool_name: 工具名称
            parameters: 工具参数
            
        Returns:
            工具执行结果
        """
        pass

    @abstractmethod
    async def get_context(self, session_id: str) -> Dict[str, Any]:
        """获取对话上下文
        
        Args:
            session_id: 会话ID
            
        Returns:
            对话上下文
        """
        pass

    @abstractmethod
    async def update_context(
        self,
        session_id: str,
        context: Dict[str, Any],
    ) -> bool:
        """更新对话上下文
        
        Args:
            session_id: 会话ID
            context: 新的上下文
            
        Returns:
            是否更新成功
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}"
