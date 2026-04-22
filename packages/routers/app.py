from __future__ import annotations

import importlib
import pkgutil
from quart import Quart, request, Response, Blueprint

from ..app import NekoBotFramework
from . import routes

def create_app(framework: NekoBotFramework) -> Quart:
    """创建并配置 Quart 实例，接入核心框架依赖。"""
    app = Quart(__name__)
    
    # 简单的 CORS 设置
    @app.after_request
    async def add_cors_headers(response: Response) -> Response:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    @app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
    @app.route("/<path:path>", methods=["OPTIONS"])
    async def cors_preflight(path: str) -> Response:
        return Response("", status=204, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS, PUT, DELETE",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
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
        except Exception as e:
            # logger.error(f"Failed to load route module {full_module_name}: {e}")
            pass
