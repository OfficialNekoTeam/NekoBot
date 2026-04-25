from __future__ import annotations

import datetime

import jwt
from quart import Blueprint, request

from ..auth_store import load_jwt_secret, update_password, verify_password
from ..deps import current_user, require_auth

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

_JWT_SECRET: str = load_jwt_secret()


@auth_bp.route("/token", methods=["POST"])
async def create_token() -> tuple[dict, int] | dict:
    """登录，返回 JWT access token。"""
    data = await request.get_json()
    if not isinstance(data, dict):
        return {"success": False, "message": "Invalid payload."}, 400

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return {"success": False, "message": "username and password are required."}, 400

    if not await verify_password(username, password):
        return {"success": False, "message": "Invalid credentials."}, 401

    now = datetime.datetime.now(datetime.timezone.utc)
    token = jwt.encode(
        {
            "sub": username,
            "iat": now,
            "exp": now + datetime.timedelta(days=7),
            "role": "admin",
        },
        _JWT_SECRET,
        algorithm="HS256",
    )
    return {
        "success": True,
        "data": {"access_token": token, "token_type": "Bearer", "username": username},
    }


@auth_bp.route("/me", methods=["GET"])
@require_auth
async def get_me() -> dict:
    """返回当前登录用户的基本信息。"""
    return {"success": True, "data": {"username": current_user(), "role": "admin"}}


@auth_bp.route("/password", methods=["PUT"])
@require_auth
async def change_password() -> tuple[dict, int] | dict:
    """修改当前用户密码。"""
    username = current_user()
    data = await request.get_json()
    if not isinstance(data, dict):
        return {"success": False, "message": "Invalid payload."}, 400

    old_password = str(data.get("old_password", ""))
    new_password = str(data.get("new_password", ""))

    if not old_password or not new_password:
        return {"success": False, "message": "old_password and new_password are required."}, 400

    if len(new_password) < 6:
        return {"success": False, "message": "New password must be at least 6 characters."}, 400

    if not await verify_password(username, old_password):
        return {"success": False, "message": "Current password is incorrect."}, 403

    await update_password(username, new_password)
    return {"success": True, "message": "Password updated."}
