from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

import jwt
from quart import g, request

from .auth_store import load_jwt_secret

_JWT_SECRET: str = load_jwt_secret()

F = TypeVar("F", bound=Callable[..., Any])


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


def require_auth(fn: F) -> F:
    """验证 Bearer JWT，通过后将 claims 存入 g.claims；失败返回 401。"""
    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        token = _bearer_token()
        if token is None:
            return {"success": False, "message": "Authentication required."}, 401
        claims = _decode_token(token)
        if claims is None:
            return {"success": False, "message": "Invalid or expired token."}, 401
        g.claims = claims
        return await fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def current_user() -> str:
    """返回当前请求的用户名，须在 require_auth 路由内调用。"""
    claims: dict = getattr(g, "claims", {})
    return str(claims.get("sub", ""))
