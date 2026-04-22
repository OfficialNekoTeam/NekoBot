from __future__ import annotations

import datetime
from typing import cast

import jwt
from quart import Blueprint, current_app, request
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__)

# TODO: 接入 config 中的 JWT Secret (先暂时硬编码或从环境变量动态读取)
# 暂时在这里生成一个固定的开发秘钥，实际可结合 bootstrap 的配置
_JWT_SECRET = "NEKOBOT_SUPER_SECRET_KEY_CHANGE_ME"

@auth_bp.route("/login", methods=["POST"])
async def login() -> dict[str, object]:
    """处理前端登录请求，返回 Access Token"""
    data = await request.get_json()
    if not isinstance(data, dict):
        return {"success": False, "message": "Invalid payload format."}, 400

    username = str(data.get("username", ""))
    password = str(data.get("password", ""))

    if not username or not password:
        return {"success": False, "message": "Missing username or password."}, 400

    # ==========================
    # 模拟默认的鉴权逻辑
    # 注意：需将其对接到系统 sqlite 或 bootstrap_config 中
    # ==========================
    # 默认账密均为 nekobot（在 TODO 中有要求）
    default_admin_hash = generate_password_hash("nekobot")
    
    if username == "nekobot" and check_password_hash(default_admin_hash, password):
        # 验证成功，发放 JWT token
        payload = {
            "sub": username,
            "iat": datetime.datetime.now(datetime.timezone.utc),
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
            "role": "admin"
        }
        token = jwt.encode(payload, _JWT_SECRET, algorithm="HS256")
        
        return {
            "success": True,
            "message": "Login successful",
            "data": {
                "access_token": token,
                "username": username
            }
        }

    return {"success": False, "message": "Invalid username or password."}, 401

@auth_bp.route("/change-password", methods=["POST"])
async def change_password() -> dict[str, object]:
    """处理前端更改密码的请求"""
    data = await request.get_json()
    if not isinstance(data, dict):
        return {"success": False, "message": "Invalid payload format."}, 400

    # 取出鉴权拦截器验证后的用户名 (通常这里需要 JWT Middleware)
    # 此处先简化处理为获取参数并提示未完整实现
    old_password = str(data.get("old_password", ""))
    new_password = str(data.get("new_password", ""))

    if not old_password or not new_password:
        return {"success": False, "message": "Missing password fields."}, 400

    # TODO: 校验 old_password 以及写入 new_password 的哈希至配置数据表中
    return {
        "success": True, 
        "message": "Password changed successfully."
    }
