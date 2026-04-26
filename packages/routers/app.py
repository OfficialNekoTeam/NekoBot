from __future__ import annotations

import datetime
import importlib
import os
import pkgutil
from pathlib import Path

from quart import Blueprint, Quart, Response, request, send_file

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
    app.config["START_TIME"] = datetime.datetime.now(datetime.timezone.utc)

    # 动态注册路由组
    _discover_and_register_routes(app, routes)

    @app.route("/api/v1/ping", methods=["GET"])
    async def ping() -> dict[str, object]:
        try:
            from importlib.metadata import version as _pkg_version
            _version = _pkg_version("nekobot")
        except Exception:
            _version = "unknown"
        return {"success": True, "message": "pong", "version": _version}

    # 静态文件 + SPA fallback（仅当 dist 目录存在时生效）
    # 优先取环境变量，否则相对于当前工作目录（通常是项目根目录）
    _dist_raw = os.environ.get("NEKOBOT_DIST_DIR", "data/dist")
    _dist = Path(_dist_raw) if os.path.isabs(_dist_raw) else (Path.cwd() / _dist_raw)
    _dist = _dist.resolve()
    from loguru import logger as _log
    if not _dist.is_dir():
        _log.warning("WebUI dist 目录不存在，静态文件服务已跳过: {}", _dist)
    else:
        _index = _dist / "index.html"
        _log.info("Serving WebUI from: {}", _dist)

        @app.route("/")
        async def _root() -> Response:
            return await send_file(_index)

        @app.route("/<path:path>", methods=["GET"])
        async def _static_or_spa(path: str) -> Response:
            # API 路径不应到达此处，但防止意外匹配
            if path.startswith("api/"):
                return Response('{"success":false,"message":"Not found"}', status=404, content_type="application/json")
            candidate = _dist / path
            try:
                candidate.relative_to(_dist)  # 防止路径穿越
            except ValueError:
                return await send_file(_index)
            if candidate.is_file():
                return await send_file(candidate)
            return await send_file(_index)

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
