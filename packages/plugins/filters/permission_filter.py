"""权限过滤器

基于用户权限过滤事件
"""

from ..base import HandlerFilter
from typing import Dict, Any


class PermissionType:
    """权限类型"""
    ADMIN = "admin"
    MEMBER = "member"


class PermissionFilter(HandlerFilter):
    """权限过滤器
    
    检查用户是否有权限执行操作
    """

    def __init__(self, permission_type: str = PermissionType.MEMBER, raise_error: bool = True):
        """初始化权限过滤器
        
        Args:
            permission_type: 权限类型（admin 或 member）
            raise_error: 是否在权限不足时抛出错误
        """
        self.permission_type = permission_type
        self.raise_error = raise_error

    def filter(self, event: Dict[str, Any], config: Dict[str, Any]) -> bool:
        """过滤事件
        
        Args:
            event: 事件数据
            config: 配置数据
            
        Returns:
            True 表示通过过滤，False 表示被过滤
        """
        # 获取管理员列表
        admins = config.get("admins_id", [])
        
        # 获取用户ID
        user_id = event.get("user_id")
        if not user_id:
            return True
        
        # 检查权限
        if self.permission_type == PermissionType.ADMIN:
            # 需要管理员权限
            if str(user_id) not in admins:
                if self.raise_error:
                    raise PermissionError(f"用户 {user_id} 没有权限执行管理员操作")
                return False
        elif self.permission_type == PermissionType.MEMBER:
            # 普通成员权限，总是允许
            pass
        
        return True


class PermissionError(Exception):
    """权限错误
    
    当用户权限不足时抛出此错误
    """
    pass