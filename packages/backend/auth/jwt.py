"""JWT认证模块"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from ..core.config import load_config

# 加载配置
CONFIG = load_config()

# 获取或生成JWT密钥
if not CONFIG["jwt"]["secret_key"]:
    CONFIG["jwt"]["secret_key"] = secrets.token_urlsafe(32)
    # 保存生成的密钥到配置文件
    import json
    from pathlib import Path

    CONFIG_PATH = (
        Path(__file__).parent.parent.parent.parent / "data" / "cmd_config.json"
    )
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(CONFIG, f, indent=2, ensure_ascii=False)

# JWT配置
SECRET_KEY = CONFIG["jwt"]["secret_key"]
ALGORITHM = CONFIG["jwt"]["algorithm"]
ACCESS_TOKEN_EXPIRE_MINUTES = CONFIG["jwt"]["access_token_expire_minutes"]


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str, credentials_exception) -> Dict[str, Any]:
    """验证令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception
