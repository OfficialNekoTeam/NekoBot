"""认证模块

提供用户认证和密码管理功能
"""

from .user import (
    User,
    load_users,
    save_users,
    get_user,
    authenticate_user,
    update_user_password,
    reset_user_password,
)
from .hash import (
    verify_password,
    get_password_hash,
)
from .jwt import (
    create_access_token,
    verify_token,
)

__all__ = [
    "User",
    "load_users",
    "save_users",
    "get_user",
    "authenticate_user",
    "update_user_password",
    "reset_user_password",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "verify_token",
]