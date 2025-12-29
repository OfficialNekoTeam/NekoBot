"""用户认证模块"""

import json
from pathlib import Path
from typing import Dict, Optional, Any
from loguru import logger
from .hash import verify_password, get_password_hash

# 用户数据存储路径
USER_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "users.json"


class User:
    """用户模型"""

    def __init__(self, username: str, hashed_password: str, first_login: bool = False):
        self.username = username
        self.hashed_password = hashed_password
        self.first_login = first_login

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "username": self.username,
            "hashed_password": self.hashed_password,
            "first_login": self.first_login,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        """从字典创建用户"""
        return cls(
            username=data["username"],
            hashed_password=data["hashed_password"],
            first_login=data.get("first_login", False),
        )


def load_users() -> Dict[str, User]:
    """加载所有用户"""
    users: Dict[str, User] = {}

    # 如果文件不存在，创建默认用户
    if not USER_DATA_PATH.exists():
        # 创建默认用户，用户名和密码都是nekobot
        default_user = User(
            username="nekobot",
            hashed_password=get_password_hash("nekobot"),
            first_login=True,
        )
        users["nekobot"] = default_user
        save_users(users)
        return users

    try:
        with open(USER_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            for username, user_data in data.items():
                users[username] = User.from_dict(user_data)
        return users
    except Exception as e:
        # 如果加载失败，创建默认用户
        default_user = User(
            username="nekobot",
            hashed_password=get_password_hash("nekobot"),
            first_login=True,
        )
        users["nekobot"] = default_user
        save_users(users)
        return users


def save_users(users: Dict[str, User]) -> None:
    """保存所有用户"""
    data: Dict[str, Dict[str, Any]] = {}
    for username, user in users.items():
        data[username] = user.to_dict()

    # 确保目录存在
    USER_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(USER_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_user(username: str) -> Optional[User]:
    """获取用户"""
    try:
        users = load_users()
        return users.get(username)
    except Exception as e:
        logger.error(f"获取用户失败: {e}", exc_info=True)
        return None


def authenticate_user(username: str, password: str) -> Optional[User]:
    """验证用户"""
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def update_user_password(username: str, new_password: str) -> bool:
    """更新用户密码"""
    users = load_users()
    if username not in users:
        return False

    users[username].hashed_password = get_password_hash(new_password)
    users[username].first_login = False
    save_users(users)
    return True


def reset_user_password(username: str, new_password: str) -> bool:
    """重置用户密码（用于CLI）"""
    users = load_users()
    if username not in users:
        return False

    users[username].hashed_password = get_password_hash(new_password)
    users[username].first_login = False
    save_users(users)
    return True
