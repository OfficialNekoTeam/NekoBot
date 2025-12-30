"""NekoBot Quart 应用"""

from quart import Quart, websocket, send_from_directory, request, g
from quart_cors import cors
from werkzeug.exceptions import Unauthorized
from loguru import logger
import sys
import os

from .core.config import load_config

# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} <level>[{level}]</level> {message}",
    level="DEBUG",
    colorize=True,
)

# 创建 Quart 应用实例
app = Quart(__name__)

# 加载配置
CONFIG = load_config()

# 配置 CORS，使用配置文件中的设置
cors_config = CONFIG.get("cors", {})
app = cors(
    app,
    allow_origin=cors_config.get("allow_origin", "*"),
    allow_headers=cors_config.get("allow_headers", ["Content-Type", "Authorization"]),
    allow_methods=cors_config.get("allow_methods", ["GET", "POST", "PUT", "DELETE", "OPTIONS"]),
)

# 获取项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# 静态文件目录
STATIC_DIR = os.path.join(PROJECT_ROOT, "data", "dist")

# 应用配置
app.config.from_mapping(
    DEBUG=True,
    SECRET_KEY="dev",
    STATIC_FOLDER=STATIC_DIR,
)

# 导入并初始化核心模块
from .core.plugin_manager import plugin_manager
from .core.server import (
    platform_manager,
    event_queue,
    start_server as start_core_server,
)

# 导入路由模块
from .routes.route import RouteContext
from .routes.bot_config import BotConfigRoute
from .routes.plugin_route import PluginRoute
from .routes.log_route import LogRoute
from .routes.personality_route import PersonalityRoute
from .routes.mcp_route import McpRoute
from .routes.llm_route import LlmRoute
from .routes.settings_route import SettingsRoute
from .routes.platform_route import PlatformRoute
from .routes.chat_route import ChatRoute
from .routes.command_route import CommandRoute
from .routes.auth_route import AuthRoute
from .routes.platforms_route import PlatformsRoute
from .routes.stat_route import StatRoute
from .routes.system_route import SystemRoute

# 初始化应用状态
app.plugins = {
    "plugin_manager": plugin_manager,
    "platform_manager": platform_manager,
    "event_queue": event_queue,
}

# 创建路由上下文
route_context = RouteContext(CONFIG, app)

# 初始化路由
bot_config_route = BotConfigRoute(route_context)
plugin_route = PluginRoute(route_context)
log_route = LogRoute(route_context)
personality_route = PersonalityRoute(route_context)
mcp_route = McpRoute(route_context)
llm_route = LlmRoute(route_context)
settings_route = SettingsRoute(route_context)
platform_route = PlatformRoute(route_context)
chat_route = ChatRoute(route_context)
command_route = CommandRoute(route_context)
auth_route = AuthRoute(route_context)
platforms_route = PlatformsRoute(route_context)
stat_route = StatRoute(route_context)
system_route = SystemRoute(route_context)

# 注册所有路由
for route_class in [
    bot_config_route,
    plugin_route,
    log_route,
    personality_route,
    mcp_route,
    llm_route,
    settings_route,
    platform_route,
    chat_route,
    command_route,
    auth_route,
    platforms_route,
    stat_route,
    system_route,
]:
    for path, method, handler in route_class.routes:
        app.add_url_rule(path, view_func=handler, methods=[method])


# JWT认证中间件
@app.before_request
async def before_request():
    """请求前钩子，验证JWT令牌"""
        # 排除不需要认证的路径
    excluded_paths = [
        "/health",
        "/api/login",
        "/api/docs",
        "/",
        "/static",
        "/api/platform/stats",
        "/chat/send",
        "/chat/new_session",
        "/chat/sessions",
        "/chat/get_session",
        "/chat/delete_session",
        "/api/plugins/upload",
        "/api/plugins/delete",
        "/api/plugins/config",
        "/api/commands",
        "/api/commands/conflicts",
        "/api/auth/login",
        "/api/stat/version",
        "/api/system/cors/config",
    ]

    # WebUI API 相关路径（当 webui_api_enabled=False 时禁止访问）
    webui_api_paths = [
        "/api/system/webui/version",
        "/api/system/webui/update",
        "/api/system/info",
        "/api/stat/get",
    ]

    # 检查 WebUI API 是否禁用
    webui_api_disabled = not CONFIG.get("webui_api_enabled", True)
    if webui_api_disabled and any(
        path.startswith(api_path) for api_path in webui_api_paths
    ):
        return {"status": "error", "message": "WebUI API is disabled"}, 403

    # 检查当前路径是否需要认证
    path = request.path
    if path.startswith("/api") and not any(
        path.startswith(excluded_path) for excluded_path in excluded_paths
    ):
        # 获取Authorization头
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise Unauthorized("未提供认证令牌")

        # 检查Authorization头格式
        if not auth_header.startswith("Bearer "):
            raise Unauthorized("认证令牌格式错误")

        # 提取令牌
        token = auth_header.split(" ")[1]

        try:
            from jose import JWTError, jwt
            from .auth.jwt import SECRET_KEY, ALGORITHM
            from .auth.user import get_user
            from .core.database import db_manager

            # 检查令牌黑名单
            if db_manager.is_token_blacklisted(token):
                raise Unauthorized("令牌已失效，请重新登录")

            # 验证令牌
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise Unauthorized("无效的认证令牌")

            # 获取用户信息
            user = get_user(username)
            if not user:
                raise Unauthorized("用户不存在")

            # 设置用户对象到g.user
            g.user = user
        except JWTError:
            raise Unauthorized("无效的认证令牌")
        except Exception as e:
            logger.error(f"认证失败: {e}")
            raise Unauthorized("认证失败")


# 导入平台适配器以触发注册

# 导入 LLM 提供商以触发注册


# WebSocket 路由
@app.websocket("/ws")
async def ws():
    """处理 WebSocket 连接"""
    logger.debug("WebSocket 客户端已连接")
    try:
        while True:
            data = await websocket.receive()
            await websocket.send(f"收到: {data}")
    except Exception as e:
        logger.debug(f"WebSocket 连接错误: {e}")
    finally:
        logger.debug("WebSocket 客户端已断开")


# 健康检查端点
@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status": "healthy", "message": "NekoBot is running", "version": "1.0.0"}


# 静态文件路由
@app.get("/static/<path:filename>")
async def static_files(filename):
    """提供静态文件"""
    if not CONFIG.get("webui_enabled", True):
        return {"status": "error", "message": "WebUI is disabled"}, 403
    return await send_from_directory(STATIC_DIR, filename)


# 根路径路由 - 优先返回前端 index.html
@app.get("/")
async def root():
    """根路径返回前端页面或API信息"""
    if not CONFIG.get("webui_enabled", True):
        return {"status": "success", "message": "NekoBot API", "docs": "/docs"}
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return await send_from_directory(STATIC_DIR, "index.html")
    return {"status": "success", "message": "NekoBot API", "docs": "/docs"}


# 处理所有其他路径 - 支持前端 SPA 路由
@app.get("/<path:path>")
async def catch_all(path):
    """处理所有路径，支持前端 SPA 路由"""
    # 检查当前路径是否为API路径
    if path.startswith("api"):
        return {"status": "error", "message": "API路径不存在"}, 404

    # 检查 WebUI 是否启用
    if not CONFIG.get("webui_enabled", True):
        return {"status": "error", "message": "WebUI is disabled"}, 403

    # 检查文件是否存在
    file_path = os.path.join(STATIC_DIR, path)
    if os.path.isfile(file_path):
        return await send_from_directory(STATIC_DIR, path)
    # 否则返回 index.html，让前端路由处理
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return await send_from_directory(STATIC_DIR, "index.html")
    # 如果没有前端文件，返回 404
    return {"status": "error", "message": "Not Found"}, 404


# API 路由


# 用户登录
@app.post("/api/login")
async def login():
    """用户登录"""
    from .auth.user import authenticate_user
    from .auth.jwt import create_access_token

    try:
        data = await request.get_json()
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return {"status": "error", "message": "请提供用户名和密码"}, 400

        # 验证用户
        user = authenticate_user(username, password)
        if not user:
            return {"status": "error", "message": "用户名或密码错误"}, 401

        # 创建访问令牌
        access_token = create_access_token(data={"sub": user.username})

        return {
            "status": "success",
            "message": "登录成功",
            "data": {
                "access_token": access_token,
                "token_type": "bearer",
                "username": user.username,
                "first_login": user.first_login,
            },
        }
    except Exception as e:
        return {"status": "error", "message": f"登录失败: {str(e)}"}, 500


# 修改密码
@app.post("/api/change-password")
async def change_password():
    """修改密码"""
    from .auth.user import update_user_password

    try:
        # 检查是否为Demo模式
        if CONFIG.get("demo", False):
            return {"status": "error", "message": "Demo模式下不允许修改密码"}, 403

        data = await request.get_json()
        old_password = data.get("old_password")
        new_password = data.get("new_password")

        if not old_password or not new_password:
            return {"status": "error", "message": "请提供旧密码和新密码"}, 400

        # 获取当前用户
        user = g.user

        # 验证旧密码
        from .auth.hash import verify_password

        if not verify_password(old_password, user.hashed_password):
            return {"status": "error", "message": "旧密码错误"}, 401

        # 更新密码
        if update_user_password(user.username, new_password):
            return {"status": "success", "message": "密码修改成功"}
        else:
            return {"status": "error", "message": "密码修改失败"}, 500
    except Exception as e:
        return {"status": "error", "message": f"密码修改失败: {str(e)}"}, 500


# 获取用户信息
@app.get("/api/user-info")
async def get_user_info():
    """获取用户信息"""
    # 简化实现，直接返回成功响应
    return {
        "status": "success",
        "message": "获取用户信息成功",
        "data": {"username": "nekobot", "first_login": True},
    }


# 获取配置信息
@app.get("/api/config")
async def get_app_config():
    """获取配置信息（包括Demo模式）"""
    return {
        "status": "success",
        "message": "获取配置信息成功",
        "data": {"demo": CONFIG.get("demo", False)},
    }


# 获取系统统计数据API
@app.get("/api/stats")
async def get_stats():
    """获取系统统计数据"""
    import psutil

    # 获取插件数量
    plugins_count = len(plugin_manager.plugins)

    # 获取已启用插件数量
    enabled_plugins_count = len(plugin_manager.enabled_plugins)

    # 获取消息适配器数量
    adapters_count = len(platform_manager.platforms)

    # 获取运行中的适配器数量
    running_adapters_count = len(
        [p for p in platform_manager.platforms.values() if p.status.value == "running"]
    )

    # 获取真实的CPU和内存使用率
    cpu_usage = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    memory_usage = memory.percent

    # 获取平台消息统计
    platform_stats = platform_manager.get_all_stats()
    message_stats = []

    for stat in platform_stats:
        # 从平台统计中获取消息数据
        messages = stat.get("messages", 0)
        previous_messages = stat.get("previous_messages", 0)

        # 计算趋势和变化百分比
        if previous_messages > 0:
            change = abs((messages - previous_messages) / previous_messages * 100)
            trend = "up" if messages > previous_messages else "down"
        else:
            change = 0
            trend = "up"

        message_stats.append(
            {
                "platform": stat.get("display_name", stat.get("type", "Unknown")),
                "messages": messages,
                "trend": trend,
                "change": round(change, 1),
            }
        )

    return {
        "status": "success",
        "message": "获取系统统计数据成功",
        "data": {
            "system": {
                "cpuUsage": round(cpu_usage, 1),
                "memoryUsage": round(memory_usage, 1),
                "pluginsCount": plugins_count,
                "enabledPluginsCount": enabled_plugins_count,
                "adaptersCount": adapters_count,
                "runningAdaptersCount": running_adapters_count,
            },
            "messages": message_stats,
        },
    }


# 健康检查API
@app.get("/api/health")
async def api_health():
    """API健康检查"""
    return {"status": "healthy", "message": "API服务正常运行"}


# 启动应用
async def run_app():
    """启动 Quart 应用"""
    # 启动核心服务器
    await start_core_server()

    # 运行 Quart 应用
    host = CONFIG.get("server", {}).get("host", "0.0.0.0")
    port = CONFIG.get("server", {}).get("port", 6285)
    logger.info(f"启动 Quart 应用: http://{host}:{port}")
    await app.run_task(host=host, port=port)
