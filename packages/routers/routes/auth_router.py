from __future__ import annotations

import datetime

import jwt
from quart import Blueprint, request

from ..auth_store import init_auth_db, load_jwt_secret, update_password, verify_password

auth_bp = Blueprint("auth", __name__)

_JWT_SECRET: str = load_jwt_secret()


def _bearer_token() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def _decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


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

    await init_auth_db()
    if not await verify_password(username, password):
        return {"success": False, "message": "Invalid username or password."}, 401

    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + datetime.timedelta(days=7),
        "role": "admin",
    }
    token = jwt.encode(payload, _JWT_SECRET, algorithm="HS256")

    return {
        "success": True,
        "message": "Login successful",
        "data": {"access_token": token, "username": username},
    }


@auth_bp.route("/change-password", methods=["POST"])
async def change_password() -> dict[str, object]:
    """处理前端更改密码的请求"""
    token = _bearer_token()
    if token is None:
        return {"success": False, "message": "Authentication required."}, 401

    claims = _decode_token(token)
    if claims is None:
        return {"success": False, "message": "Invalid or expired token."}, 401

    username = str(claims.get("sub", ""))
    if not username:
        return {"success": False, "message": "Invalid token claims."}, 401

    data = await request.get_json()
    if not isinstance(data, dict):
        return {"success": False, "message": "Invalid payload format."}, 400

    old_password = str(data.get("old_password", ""))
    new_password = str(data.get("new_password", ""))

    if not old_password or not new_password:
        return {"success": False, "message": "Missing password fields."}, 400

    await init_auth_db()
    if not await verify_password(username, old_password):
        return {"success": False, "message": "Current password is incorrect."}, 403

    await update_password(username, new_password)
    return {"success": True, "message": "Password changed successfully."}
