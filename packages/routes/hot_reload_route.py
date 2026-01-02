"""热重载管理路由

提供热重载相关的 API 接口
"""

from .route import Route, Response, RouteContext
from loguru import logger


class HotReloadRoute(Route):
    """热重载管理路由"""

    def register_routes(self) -> None:
        """注册所有路由"""
        self.routes = [
            ("/api/hot_reload/stats", "GET", self.hot_get_stats),
            ("/api/hot_reload/history", "GET", self.hot_get_history),
            ("/api/hot_reload/routes", "GET", self.hot_get_routes),
            ("/api/hot_reload/reload_plugin", "POST", self.hot_reload_plugin),
            ("/api/hot_reload/reload_config", "POST", self.hot_reload_config),
            ("/api/hot_reload/register_route", "POST", self.hot_register_route),
            ("/api/hot_reload/unregister_route", "POST", self.hot_unregister_route),
            ("/api/hot_reload/enable_route", "POST", self.hot_enable_route),
            ("/api/hot_reload/disable_route", "POST", self.hot_disable_route),
            ("/api/hot_reload/start", "POST", self.start_hot_reload),
            ("/api/hot_reload/stop", "POST", self.stop_hot_reload),
            ("/api/hot_reload/routes_doc", "GET", self.get_routes_documentation),
        ]
        logger.info("热重载管理路由已注册")

    async def hot_get_stats(self):
        """获取热重载统计信息"""
        try:
            # 获取热重载管理器
            hot_reload_manager = self.context.app.plugins.get("hot_reload_manager")
            config_reload_manager = self.context.app.plugins.get("config_reload_manager")
            dynamic_route_manager = self.context.app.plugins.get("dynamic_route_manager")
            
            stats = {
                "hot_reload": hot_reload_manager.get_stats() if hot_reload_manager else {},
                "config_reload": config_reload_manager.get_stats() if config_reload_manager else {},
                "dynamic_routes": dynamic_route_manager.get_stats() if dynamic_route_manager else {}
            }
            
            return Response().ok(stats, "获取统计信息成功").to_dict()
        except Exception as e:
            logger.error(f"获取热重载统计失败: {e}")
            return Response().error(f"获取统计信息失败: {str(e)}").to_dict()

    async def hot_get_history(self):
        """获取重载历史"""
        try:
            limit = request.args.get("limit", 50, type=int)
            
            hot_reload_manager = self.context.app.plugins.get("hot_reload_manager")
            config_reload_manager = self.context.app.plugins.get("config_reload_manager")
            dynamic_route_manager = self.context.app.plugins.get("dynamic_route_manager")
            
            history = {
                "reload_history": hot_reload_manager.get_reload_history(limit) if hot_reload_manager else [],
                "config_reload_history": config_reload_manager.get_reload_history(limit) if config_reload_manager else [],
                "route_registration_history": dynamic_route_manager.get_registration_history(limit) if dynamic_route_manager else []
            }
            
            return Response().ok(history, "获取历史记录成功").to_dict()
        except Exception as e:
            logger.error(f"获取重载历史失败: {e}")
            return Response().error(f"获取历史记录失败: {str(e)}").to_dict()

    async def hot_get_routes(self):
        """获取动态路由列表"""
        try:
            dynamic_route_manager = self.context.app.plugins.get("dynamic_route_manager")
            
            if not dynamic_route_manager:
                return Response().error("动态路由管理器未初始化").to_dict()
            
            routes = dynamic_route_manager.list_routes()
            return Response().ok(routes, "获取路由列表成功").to_dict()
        except Exception as e:
            logger.error(f"获取动态路由列表失败: {e}")
            return Response().error(f"获取路由列表失败: {str(e)}").to_dict()

    async def hot_reload_plugin(self):
        """重载指定插件"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("请求数据无效").to_dict()
            
            plugin_name = data.get("plugin_name")
            if not plugin_name:
                return Response().error("缺少参数: plugin_name").to_dict()
            
            # 获取插件管理器
            plugin_manager = self.context.app.plugins.get("plugin_manager")
            if not plugin_manager:
                return Response().error("插件管理器未初始化").to_dict()
            
            # 执行重载
            success = await plugin_manager.reload_plugin(plugin_name)
            
            if success:
                return Response().ok(None, f"插件 {plugin_name} 重载成功").to_dict()
            else:
                return Response().error(f"插件 {plugin_name} 重载失败").to_dict()
        except Exception as e:
            logger.error(f"重载插件失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response().error(f"重载插件失败: {str(e)}").to_dict()

    async def hot_reload_config(self):
        """重载指定配置"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("请求数据无效").to_dict()
            
            config_name = data.get("config_name")
            if not config_name:
                return Response().error("缺少参数: config_name").to_dict()
            
            # 获取配置重载管理器
            config_reload_manager = self.context.app.plugins.get("config_reload_manager")
            if not config_reload_manager:
                return Response().error("配置重载管理器未初始化").to_dict()
            
            # 执行重载
            success = await config_reload_manager.reload_config(config_name)
            
            if success:
                return Response().ok(None, f"配置 {config_name} 重载成功").to_dict()
            else:
                return Response().error(f"配置 {config_name} 重载失败").to_dict()
        except Exception as e:
            logger.error(f"重载配置失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response().error(f"重载配置失败: {str(e)}").to_dict()

    async def hot_register_route(self):
        """注册动态路由"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("请求数据无效").to_dict()
            
            # 验证必填字段
            required_fields = ["route_id", "method", "path"]
            valid, error_msg = await self.validate_required_fields(data, required_fields)
            if not valid:
                return Response().error(error_msg).to_dict()
            
            dynamic_route_manager = self.context.app.plugins.get("dynamic_route_manager")
            if not dynamic_route_manager:
                return Response().error("动态路由管理器未初始化").to_dict()
            
            # 注册路由（这里需要从数据中获取处理函数）
            # 实际应用中，处理函数应该通过其他方式传递
            # 这里只是示例，实际需要更复杂的处理
            
            return Response().ok(None, "动态路由注册功能需要通过代码实现").to_dict()
        except Exception as e:
            logger.error(f"注册动态路由失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response().error(f"注册路由失败: {str(e)}").to_dict()

    async def hot_unregister_route(self):
        """注销动态路由"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("请求数据无效").to_dict()
            
            route_id = data.get("route_id")
            if not route_id:
                return Response().error("缺少参数: route_id").to_dict()
            
            dynamic_route_manager = self.context.app.plugins.get("dynamic_route_manager")
            if not dynamic_route_manager:
                return Response().error("动态路由管理器未初始化").to_dict()
            
            success, error = await dynamic_route_manager.unregister_route(route_id)
            
            if success:
                return Response().ok(None, f"路由 {route_id} 注销成功").to_dict()
            else:
                return Response().error(error or f"路由 {route_id} 注销失败").to_dict()
        except Exception as e:
            logger.error(f"注销动态路由失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response().error(f"注销路由失败: {str(e)}").to_dict()

    async def hot_enable_route(self):
        """启用路由"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("请求数据无效").to_dict()
            
            route_id = data.get("route_id")
            if not route_id:
                return Response().error("缺少参数: route_id").to_dict()
            
            dynamic_route_manager = self.context.app.plugins.get("dynamic_route_manager")
            if not dynamic_route_manager:
                return Response().error("动态路由管理器未初始化").to_dict()
            
            success = await dynamic_route_manager.enable_route(route_id)
            
            if success:
                return Response().ok(None, f"路由 {route_id} 已启用").to_dict()
            else:
                return Response().error(f"路由 {route_id} 启用失败").to_dict()
        except Exception as e:
            logger.error(f"启用路由失败: {e}")
            return Response().error(f"启用路由失败: {str(e)}").to_dict()

    async def hot_disable_route(self):
        """禁用路由"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("请求数据无效").to_dict()
            
            route_id = data.get("route_id")
            if not route_id:
                return Response().error("缺少参数: route_id").to_dict()
            
            dynamic_route_manager = self.context.app.plugins.get("dynamic_route_manager")
            if not dynamic_route_manager:
                return Response().error("动态路由管理器未初始化").to_dict()
            
            success = await dynamic_route_manager.disable_route(route_id)
            
            if success:
                return Response().ok(None, f"路由 {route_id} 已禁用").to_dict()
            else:
                return Response().error(f"路由 {route_id} 禁用失败").to_dict()
        except Exception as e:
            logger.error(f"禁用路由失败: {e}")
            return Response().error(f"禁用路由失败: {str(e)}").to_dict()

    async def start_hot_reload(self):
        """启动热重载"""
        try:
            hot_reload_manager = self.context.app.plugins.get("hot_reload_manager")
            if not hot_reload_manager:
                return Response().error("热重载管理器未初始化").to_dict()
            
            if hot_reload_manager.is_running():
                return Response().error("热重载已经在运行中").to_dict()
            
            await hot_reload_manager.start()
            return Response().ok(None, "热重载已启动").to_dict()
        except Exception as e:
            logger.error(f"启动热重载失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response().error(f"启动热重载失败: {str(e)}").to_dict()

    async def stop_hot_reload(self):
        """停止热重载"""
        try:
            hot_reload_manager = self.context.app.plugins.get("hot_reload_manager")
            if not hot_reload_manager:
                return Response().error("热重载管理器未初始化").to_dict()
            
            if not hot_reload_manager.is_running():
                return Response().error("热重载未在运行").to_dict()
            
            await hot_reload_manager.stop()
            return Response().ok(None, "热重载已停止").to_dict()
        except Exception as e:
            logger.error(f"停止热重载失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response().error(f"停止热重载失败: {str(e)}").to_dict()

    async def get_routes_documentation(self):
        """获取动态路由文档"""
        try:
            dynamic_route_manager = self.context.app.plugins.get("dynamic_route_manager")
            
            if not dynamic_route_manager:
                return Response().error("动态路由管理器未初始化").to_dict()
            
            documentation = dynamic_route_manager.export_routes_documentation()
            
            from quart import Response as QuartResponse
            return QuartResponse(
                documentation,
                mimetype="text/markdown"
            )
        except Exception as e:
            logger.error(f"获取路由文档失败: {e}")
            return Response().error(f"获取路由文档失败: {str(e)}").to_dict()