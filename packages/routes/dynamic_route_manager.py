"""动态路由管理器

提供动态路由注册、注销和冲突检测功能
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from loguru import logger
from quart import Quart, Blueprint, request


class RouteConflictResolution(Enum):
    """路由冲突解决策略"""
    SKIP = "skip"  # 跳过新路由
    REPLACE = "replace"  # 替换旧路由
    MERGE = "merge"  # 合并路由


@dataclass
class RouteInfo:
    """路由信息"""
    route_id: str
    method: str
    path: str
    handler: Callable
    module: str  # 所属模块
    description: str = ""
    enabled: bool = True
    priority: int = 0  # 优先级，数值越大优先级越高


@dataclass
class RouteConflict:
    """路由冲突信息"""
    existing_route: RouteInfo
    new_route: RouteInfo
    conflict_type: str


class DynamicRouteManager:
    """动态路由管理器
    
    提供路由的动态注册、注销和冲突检测功能
    """
    
    def __init__(self, app: Quart):
        """初始化动态路由管理器
        
        Args:
            app: Quart 应用实例
        """
        self.app = app
        
        # 路由存储
        self._routes: Dict[str, RouteInfo] = {}
        self._path_routes: Dict[str, List[RouteInfo]] = {}  # 路径 -> 路由列表
        
        # 冲突解决策略
        self._conflict_resolution = RouteConflictResolution.SKIP
        
        # 锁
        self._lock = asyncio.Lock()
        
        # 事件回调
        self._on_route_registered: List[Callable[[RouteInfo], None]] = []
        self._on_route_unregistered: List[Callable[[RouteInfo], None]] = []
        self._on_route_conflict: List[Callable[[RouteConflict], None]] = []
        
        # 历史记录
        self._registration_history: List[Dict[str, Any]] = []
        self._max_history_size = 100
        
        logger.info("动态路由管理器已初始化")
    
    async def register_route(
        self,
        route_id: str,
        method: str,
        path: str,
        handler: Callable,
        module: str = "unknown",
        description: str = "",
        priority: int = 0,
        force: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """注册动态路由
        
        Args:
            route_id: 路由ID
            method: HTTP 方法（GET, POST, PUT, DELETE等）
            path: 路由路径
            handler: 处理函数
            module: 所属模块
            description: 路由描述
            priority: 优先级
            force: 是否强制注册（忽略冲突）
            
        Returns:
            (是否成功, 错误信息)
        """
        async with self._lock:
            # 检查路由ID是否已存在
            if route_id in self._routes:
                return False, f"路由 {route_id} 已存在"
            
            # 创建路由信息
            route_info = RouteInfo(
                route_id=route_id,
                method=method.upper(),
                path=path,
                handler=handler,
                module=module,
                description=description,
                enabled=True,
                priority=priority
            )
            
            # 检测冲突
            conflict = self._detect_conflict(route_info)
            if conflict and not force:
                # 触发冲突回调
                for callback in self._on_route_conflict:
                    try:
                        callback(conflict)
                    except Exception as e:
                        logger.error(f"路由冲突回调执行失败: {e}")
                
                # 根据策略处理冲突
                if self._conflict_resolution == RouteConflictResolution.SKIP:
                    logger.warning(
                        f"路由冲突检测: {route_id} ({method} {path}) "
                        f"与现有路由 {conflict.existing_route.route_id} 冲突，跳过注册"
                    )
                    return False, f"路由冲突: {conflict.conflict_type}"
                
                elif self._conflict_resolution == RouteConflictResolution.REPLACE:
                    # 先注销冲突的路由
                    await self._unregister_route_impl(conflict.existing_route.route_id)
                    logger.info(f"替换冲突路由: {conflict.existing_route.route_id}")
            
            # 注册路由到 Quart 应用
            try:
                if method.upper() == "GET":
                    self.app.route(path, methods=["GET"])(handler)
                elif method.upper() == "POST":
                    self.app.route(path, methods=["POST"])(handler)
                elif method.upper() == "PUT":
                    self.app.route(path, methods=["PUT"])(handler)
                elif method.upper() == "DELETE":
                    self.app.route(path, methods=["DELETE"])(handler)
                elif method.upper() == "PATCH":
                    self.app.route(path, methods=["PATCH"])(handler)
                else:
                    # 支持自定义方法
                    self.app.route(path, methods=[method.upper()])(handler)
                
                # 存储路由信息
                self._routes[route_id] = route_info
                
                # 按路径索引
                if path not in self._path_routes:
                    self._path_routes[path] = []
                self._path_routes[path].append(route_info)
                # 按优先级排序
                self._path_routes[path].sort(key=lambda r: r.priority, reverse=True)
                
                # 记录历史
                self._add_registration_history(route_info, action="register")
                
                # 触发注册回调
                for callback in self._on_route_registered:
                    try:
                        callback(route_info)
                    except Exception as e:
                        logger.error(f"路由注册回调执行失败: {e}")
                
                logger.debug(f"已注册动态路由: {route_id} ({method} {path})")
                return True, None
                
            except Exception as e:
                logger.error(f"注册路由 {route_id} 失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return False, f"注册失败: {str(e)}"
    
    async def unregister_route(self, route_id: str) -> Tuple[bool, Optional[str]]:
        """注销动态路由
        
        Args:
            route_id: 路由ID
            
        Returns:
            (是否成功, 错误信息)
        """
        async with self._lock:
            return await self._unregister_route_impl(route_id)
    
    async def _unregister_route_impl(self, route_id: str) -> Tuple[bool, Optional[str]]:
        """注销路由实现
        
        Args:
            route_id: 路由ID
            
        Returns:
            (是否成功, 错误信息)
        """
        if route_id not in self._routes:
            return False, f"路由 {route_id} 不存在"
        
        route_info = self._routes[route_id]
        
        # 从 Quart 应用中移除路由
        # 注意：Quart 没有直接移除路由的 API，
        # 这里我们只是从内部记录中移除，实际路由可能需要重启应用才能完全移除
        
        # 从路径索引中移除
        if route_info.path in self._path_routes:
            self._path_routes[route_info.path] = [
                r for r in self._path_routes[route_info.path]
                if r.route_id != route_id
            ]
            if not self._path_routes[route_info.path]:
                del self._path_routes[route_info.path]
        
        # 记录历史
        self._add_registration_history(route_info, action="unregister")
        
        # 触发注销回调
        for callback in self._on_route_unregistered:
            try:
                callback(route_info)
            except Exception as e:
                logger.error(f"路由注销回调执行失败: {e}")
        
        # 从主字典中移除
        del self._routes[route_id]
        
        logger.debug(f"已注销动态路由: {route_id}")
        return True, None
    
    def _detect_conflict(self, route_info: RouteInfo) -> Optional[RouteConflict]:
        """检测路由冲突
        
        Args:
            route_info: 要注册的路由信息
            
        Returns:
            冲突信息，如果没有冲突则返回 None
        """
        # 检查路径冲突
        if route_info.path in self._path_routes:
            for existing_route in self._path_routes[route_info.path]:
                # 同一路径同一方法
                if existing_route.method == route_info.method:
                    return RouteConflict(
                        existing_route=existing_route,
                        new_route=route_info,
                        conflict_type=f"路径和方法冲突: {route_info.method} {route_info.path}"
                    )
        
        return None
    
    def _add_registration_history(self, route_info: RouteInfo, action: str) -> None:
        """添加注册历史
        
        Args:
            route_info: 路由信息
            action: 操作类型（register/unregister）
        """
        import time
        history_entry = {
            "route_id": route_info.route_id,
            "method": route_info.method,
            "path": route_info.path,
            "module": route_info.module,
            "action": action,
            "timestamp": time.time()
        }
        self._registration_history.append(history_entry)
        
        # 限制历史记录大小
        if len(self._registration_history) > self._max_history_size:
            self._registration_history.pop(0)
    
    def set_conflict_resolution(self, strategy: RouteConflictResolution) -> None:
        """设置路由冲突解决策略
        
        Args:
            strategy: 冲突解决策略
        """
        self._conflict_resolution = strategy
        logger.info(f"路由冲突解决策略已设置为: {strategy.value}")
    
    def on_route_registered(self, callback: Callable[[RouteInfo], None]) -> None:
        """注册路由注册回调
        
        Args:
            callback: 回调函数
        """
        self._on_route_registered.append(callback)
    
    def on_route_unregistered(self, callback: Callable[[RouteInfo], None]) -> None:
        """注册路由注销回调
        
        Args:
            callback: 回调函数
        """
        self._on_route_unregistered.append(callback)
    
    def on_route_conflict(self, callback: Callable[[RouteConflict], None]) -> None:
        """注册路由冲突回调
        
        Args:
            callback: 回调函数
        """
        self._on_route_conflict.append(callback)
    
    def get_route(self, route_id: str) -> Optional[RouteInfo]:
        """获取路由信息
        
        Args:
            route_id: 路由ID
            
        Returns:
            路由信息，如果不存在则返回 None
        """
        return self._routes.get(route_id)
    
    def get_routes_by_path(self, path: str) -> List[RouteInfo]:
        """获取指定路径的所有路由
        
        Args:
            path: 路由路径
            
        Returns:
            路由信息列表
        """
        return self._path_routes.get(path, [])
    
    def get_routes_by_module(self, module: str) -> List[RouteInfo]:
        """获取指定模块的所有路由
        
        Args:
            module: 模块名
            
        Returns:
            路由信息列表
        """
        return [
            route for route in self._routes.values()
            if route.module == module
        ]
    
    def list_routes(self) -> List[Dict[str, Any]]:
        """列出所有动态路由
        
        Returns:
            路由信息字典列表
        """
        return [
            {
                "route_id": route.route_id,
                "method": route.method,
                "path": route.path,
                "module": route.module,
                "description": route.description,
                "enabled": route.enabled,
                "priority": route.priority
            }
            for route in self._routes.values()
        ]
    
    def get_registration_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取注册历史
        
        Args:
            limit: 返回的最大记录数
            
        Returns:
            历史记录列表
        """
        return self._registration_history[-limit:] if limit > 0 else self._registration_history
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        routes_by_module = {}
        for route in self._routes.values():
            if route.module not in routes_by_module:
                routes_by_module[route.module] = 0
            routes_by_module[route.module] += 1
        
        return {
            "total_routes": len(self._routes),
            "unique_paths": len(self._path_routes),
            "routes_by_module": routes_by_module,
            "conflict_resolution": self._conflict_resolution.value,
            "total_callbacks": len(self._on_route_registered) + 
                           len(self._on_route_unregistered) + 
                           len(self._on_route_conflict)
        }
    
    async def unregister_by_module(self, module: str) -> Tuple[int, List[str]]:
        """注销指定模块的所有路由
        
        Args:
            module: 模块名
            
        Returns:
            (成功注销的数量, 失败的路由ID列表)
        """
        routes = self.get_routes_by_module(module)
        success_count = 0
        failed_routes = []
        
        for route in routes:
            success, error = await self.unregister_route(route.route_id)
            if success:
                success_count += 1
            else:
                failed_routes.append(route.route_id)
        
        logger.info(f"已注销模块 {module} 的 {success_count}/{len(routes)} 个路由")
        return success_count, failed_routes
    
    async def enable_route(self, route_id: str) -> bool:
        """启用路由
        
        Args:
            route_id: 路由ID
            
        Returns:
            是否成功
        """
        route = self._routes.get(route_id)
        if not route:
            return False
        
        route.enabled = True
        logger.debug(f"已启用路由: {route_id}")
        return True
    
    async def disable_route(self, route_id: str) -> bool:
        """禁用路由
        
        Args:
            route_id: 路由ID
            
        Returns:
            是否成功
        """
        route = self._routes.get(route_id)
        if not route:
            return False
        
        route.enabled = False
        logger.debug(f"已禁用路由: {route_id}")
        return True
    
    def clear_history(self) -> None:
        """清空注册历史"""
        self._registration_history.clear()
        logger.debug("已清空路由注册历史")
    
    def export_routes_documentation(self) -> str:
        """导出路由文档
        
        Returns:
            Markdown 格式的路由文档
        """
        lines = [
            "# 动态路由文档",
            "",
            "## 路由列表",
            "",
            "| 路由ID | 方法 | 路径 | 模块 | 描述 | 状态 |",
            "|---------|------|------|------|------|------|"
        ]
        
        for route in sorted(self._routes.values(), key=lambda r: (r.module, r.path)):
            status = "✅" if route.enabled else "❌"
            lines.append(
                f"| {route.route_id} | {route.method} | {route.path} | "
                f"{route.module} | {route.description or '-'} | {status} |"
            )
        
        lines.extend([
            "",
            f"**总计:** {len(self._routes)} 个路由，{len(self._path_routes)} 个唯一路径",
            "",
            "## 按模块分类"
        ])
        
        routes_by_module = {}
        for route in self._routes.values():
            if route.module not in routes_by_module:
                routes_by_module[route.module] = []
            routes_by_module[route.module].append(route)
        
        for module in sorted(routes_by_module.keys()):
            lines.append(f"\n### {module} ({len(routes_by_module[module])} 个路由)")
            for route in sorted(routes_by_module[module], key=lambda r: r.path):
                status = "✅" if route.enabled else "❌"
                lines.append(
                    f"- `{route.method}` `{route.path}` - {route.description or '无描述'} {status}"
                )
        
        return "\n".join(lines)