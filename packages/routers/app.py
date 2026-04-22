from __future__ import annotations

import importlib
import os
import pkgutil

from quart import Blueprint, Quart, Response, request

from ..app import NekoBotFramework
from . import routes

_DEFAULT_ORIGINS = frozenset({
    "http://localhost:6285",
    "http://127.0.0.1:6285",
})


def _allowed_origins() -> frozenset[str]:
    """Read comma-separated allowed origins from NEKOBOT_CORS_ORIGINS env var.
    Defaults to localhost:6285 when not set.
    Set NEKOBOT_CORS_ORIGINS=* to disable CORS restrictions (development only).
    """
    raw = os.environ.get("NEKOBOT_CORS_ORIGINS", "").strip()
    if not raw:
        return _DEFAULT_ORIGINS
    if raw == "*":
        return frozenset({"*"})
    return frozenset(o.strip() for o in raw.split(",") if o.strip())


_CORS_ORIGINS: frozenset[str] = _allowed_origins()


def create_app(framework: NekoBotFramework) -> Quart:
    """创建并配置 Quart 实例，接入核心框架依赖。"""
    app = Quart(__name__)

    def _cors_origin(origin: str) -> str | None:
        if "*" in _CORS_ORIGINS:
            return "*"
        return origin if origin in _CORS_ORIGINS else None

    @app.after_request
    async def add_cors_headers(response: Response) -> Response:
        origin = request.headers.get("Origin", "")
        allowed = _cors_origin(origin)
        if allowed:
            response.headers["Access-Control-Allow-Origin"] = allowed
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            if allowed != "*":
                response.headers["Vary"] = "Origin"
        return response

    @app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
    @app.route("/<path:path>", methods=["OPTIONS"])
    async def cors_preflight(path: str) -> Response:
        origin = request.headers.get("Origin", "")
        allowed = _cors_origin(origin)
        if not allowed:
            return Response("", status=403)
        return Response("", status=204, headers={
            "Access-Control-Allow-Origin": allowed,
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS, PUT, DELETE",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Vary": "Origin",
        })

    # 注入框架实例
    app.config["FRAMEWORK"] = framework

    # 动态注册路由组
    _discover_and_register_routes(app, routes)

    @app.route("/api/ping", methods=["GET"])
    async def ping() -> dict[str, object]:
        return {"success": True, "message": "pong", "version": "0.1.0"}

    return app

def _discover_and_register_routes(app: Quart, routes_pkg: object) -> None:
    """自动扫描并注册指定包下的所有 Blueprint。"""
    pkg_path = getattr(routes_pkg, "__path__", None)
    if not pkg_path:
        return
        
    for _, name, is_pkg in pkgutil.iter_modules(pkg_path):
        if is_pkg:
            continue
        
        full_module_name = f"{routes_pkg.__name__}.{name}"
        try:
            module = importlib.import_module(full_module_name)
            # 搜索模块中的 Blueprint 实例
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, Blueprint):
                    # 默认使用 /api/{bp_name} 作为路由前缀，除非 bp 已经自带前缀
                    # or conventionally use url_prefix defined in bp
                    url_prefix = getattr(attr, "url_prefix", None) or f"/api/{attr.name}"
                    app.register_blueprint(attr, url_prefix=url_prefix)
                    # logger.info(f"Registered blueprint: {attr.name} from {full_module_name}")
        except Exception:
            # logger.error(f"Failed to load route module {full_module_name}: {e}")
            pass
