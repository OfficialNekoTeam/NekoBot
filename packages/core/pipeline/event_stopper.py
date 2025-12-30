"""事件停止控制器

提供事件传播控制功能，允许在流水线中停止事件传播
"""

from dataclasses import dataclass


@dataclass
class EventStopper:
    """事件停止控制器
    
    用于在流水线中停止事件的传播
    """
    stopped: bool = False
    """是否已停止事件传播"""
    reason: str = ""
    """停止原因"""
    
    def stop(self, reason: str = ""):
        """停止事件传播
        
        Args:
            reason: 停止原因
        """
        self.stopped = True
        self.reason = reason
    
    def is_stopped(self) -> bool:
        """检查事件是否已停止
        
        Returns:
            是否已停止
        """
        return self.stopped
    
    def reset(self):
        """重置停止状态"""
        self.stopped = False
        self.reason = ""