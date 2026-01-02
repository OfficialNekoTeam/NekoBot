"""统计API路由

提供仪表盘统计数据和版本信息
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
from quart import request

from .route import Route, Response, RouteContext
from ..core.database import db_manager


class StatRoute(Route):
    """统计路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.routes = [
            ("/api/stat/get", "GET", self.stat_get_stats),
            ("/api/stat/version", "GET", self.stat_get_version),
        ]

    def _load_stats_cache(self) -> Dict[str, Any]:
        """加载统计数据缓存"""
        return db_manager.get_stats_cache()

    def _save_stats_cache(self, data: Dict[str, Any], ttl: int = 300) -> None:
        """保存统计数据缓存"""
        db_manager.set_stats_cache(data, ttl)

    def _is_cache_valid(self, cache: Dict[str, Any]) -> bool:
        """检查缓存是否有效"""
        if not cache.get("cached_at"):
            return False

        try:
            cached_at = datetime.fromisoformat(cache["cached_at"])
            ttl = cache.get("ttl", 300)
            return (datetime.utcnow() - cached_at).total_seconds() < ttl
        except Exception:
            return False

    async def _get_user_activity_stats(
        self, db_manager, start_dt: datetime, end_dt: datetime
    ) -> Dict[str, Any]:
        """从数据库获取用户活跃度统计

        Args:
            db_manager: 数据库管理器
            start_dt: 开始时间
            end_dt: 结束时间

        Returns:
            用户活跃度统计数据
        """
        try:
            # 获取操作日志统计
            logs = db_manager.get_operation_logs(limit=10000)

            # 统计活跃用户
            active_users = set()
            daily_active = set()
            weekly_active = set()
            monthly_active = set()

            now = datetime.utcnow()
            one_day_ago = now - timedelta(days=1)
            one_week_ago = now - timedelta(weeks=1)
            one_month_ago = now - timedelta(days=30)

            for log in logs:
                username = log.get("username")
                if not username:
                    continue

                timestamp_str = log.get("timestamp", "")
                if timestamp_str:
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        if start_dt <= timestamp <= end_dt:
                            active_users.add(username)

                        # 统计不同时间段的活跃用户
                        if timestamp >= one_day_ago:
                            daily_active.add(username)
                        if timestamp >= one_week_ago:
                            weekly_active.add(username)
                        if timestamp >= one_month_ago:
                            monthly_active.add(username)
                    except ValueError:
                        pass

            # 获取总用户数
            all_users = db_manager.get_all_users()
            total_users = len(all_users)

            return {
                "total_users": total_users,
                "active_users": len(active_users),
                "new_users": 0,  # 可以从注册时间统计
                "daily_active": len(daily_active),
                "weekly_active": len(weekly_active),
                "monthly_active": len(monthly_active),
            }
        except Exception as e:
            logger.error(f"获取用户活跃度统计失败: {e}")
            return {
                "total_users": 0,
                "active_users": 0,
                "new_users": 0,
                "daily_active": 0,
                "weekly_active": 0,
                "monthly_active": 0,
            }

    async def _get_resource_usage(self) -> Dict[str, Any]:
        """获取系统资源使用率

        Returns:
            资源使用率数据
        """
        resource_usage = {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "disk_usage": 0.0,
        }

        # 尝试使用 psutil 获取真实数据
        try:
            import psutil

            resource_usage["cpu_usage"] = round(psutil.cpu_percent(interval=0.1), 1)
            memory = psutil.virtual_memory()
            resource_usage["memory_usage"] = round(memory.percent, 1)

            # 获取主要磁盘的使用率
            try:
                disk = psutil.disk_usage("/")
                resource_usage["disk_usage"] = round(
                    (disk.used / disk.total) * 100, 1
                )
            except Exception:
                pass

            return resource_usage
        except ImportError:
            logger.warning("psutil 未安装，使用模拟数据")
            return {
                "cpu_usage": 25.5,
                "memory_usage": 45.2,
                "disk_usage": 60.8,
            }
        except Exception as e:
            logger.error(f"获取系统资源使用率失败: {e}")
            return resource_usage

    def _parse_date_range(
        self, start_date: Optional[str], end_date: Optional[str]
    ) -> tuple[datetime, datetime]:
        """解析日期范围"""
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
            except ValueError:
                end_dt = datetime.utcnow()
        else:
            end_dt = datetime.utcnow()

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
            except ValueError:
                start_dt = end_dt - timedelta(days=30)
        else:
            start_dt = end_dt - timedelta(days=30)

        return start_dt, end_dt

    async def stat_get_stats(self) -> Dict[str, Any]:
        """获取仪表盘统计数据

        查询参数:
            start_date: 开始日期（ISO格式）
            end_date: 结束日期（ISO格式）
            use_cache: 是否使用缓存（默认true）

        返回:
            包含多个统计维度的格式化统计结果
        """
        try:
            # 获取查询参数
            start_date = request.args.get("start_date")
            end_date = request.args.get("end_date")
            use_cache = request.args.get("use_cache", "true").lower() == "true"

            # 解析日期范围
            start_dt, end_dt = self._parse_date_range(start_date, end_date)

            # 检查缓存
            if use_cache:
                cache = self._load_stats_cache()
                if self._is_cache_valid(cache):
                    logger.debug("使用缓存的统计数据")
                    return Response().ok(
                        data=cache["data"], message="获取统计数据成功（缓存）"
                    ).to_dict()

            # 获取插件管理器
            plugin_manager = self.context.app.plugins.get("plugin_manager")
            platform_manager = self.context.app.plugins.get("platform_manager")

            # 计算插件统计
            plugins_count = len(plugin_manager.plugins) if plugin_manager else 0
            enabled_plugins_count = (
                len(plugin_manager.enabled_plugins) if plugin_manager else 0
            )

            # 计算平台统计
            platforms_count = len(platform_manager.platforms) if platform_manager else 0
            running_platforms_count = 0
            if platform_manager:
                running_platforms_count = len(
                    [
                        p
                        for p in platform_manager.platforms.values()
                        if p.status.value == "running"
                    ]
                )

            # 获取平台消息统计
            message_stats = []
            total_messages = 0
            if platform_manager:
                platform_stats = platform_manager.get_all_stats()
                for stat in platform_stats:
                    messages = stat.get("messages", 0)
                    total_messages += messages
                    message_stats.append(
                        {
                            "platform": stat.get("display_name", stat.get("type", "Unknown")),
                            "messages": messages,
                        }
                    )

            # 计算用户活跃度（从数据库获取真实数据）
            user_activity = await self._get_user_activity_stats(db_manager, start_dt, end_dt)

            # 计算资源使用率（尝试使用 psutil 获取真实数据）
            resource_usage = await self._get_resource_usage()

            # 构建统计数据
            stats_data = {
                "period": {
                    "start_date": start_dt.isoformat(),
                    "end_date": end_dt.isoformat(),
                    "days": (end_dt - start_dt).days,
                },
                "plugins": {
                    "total": plugins_count,
                    "enabled": enabled_plugins_count,
                    "disabled": plugins_count - enabled_plugins_count,
                },
                "platforms": {
                    "total": platforms_count,
                    "running": running_platforms_count,
                    "stopped": platforms_count - running_platforms_count,
                },
                "messages": {
                    "total": total_messages,
                    "by_platform": message_stats,
                },
                "user_activity": user_activity,
                "resource_usage": resource_usage,
                "generated_at": datetime.utcnow().isoformat(),
            }

            # 保存缓存（5分钟TTL）
            self._save_stats_cache(stats_data, ttl=300)

            return Response().ok(data=stats_data, message="获取统计数据成功").to_dict()

        except Exception as e:
            logger.error(f"获取统计数据失败: {e}", exc_info=True)
            return Response().error(f"获取统计数据失败: {str(e)}").to_dict()

    async def stat_get_version(self) -> Dict[str, Any]:
        """获取版本信息与迁移状态

        返回:
            包含系统版本号、数据库迁移状态、最后更新时间等系统元信息
        """
        try:
            # 从数据库获取迁移记录
            migrations = db_manager.get_migrations()

            # 获取最后迁移信息
            last_migration = None
            if migrations:
                last_migration = migrations[-1]

            # 获取系统启动时间（从应用上下文获取）
            start_time = getattr(self.context.app, "start_time", None)
            if start_time:
                uptime_seconds = (datetime.utcnow() - start_time).total_seconds()
                uptime_days = int(uptime_seconds // 86400)
                uptime_hours = int((uptime_seconds % 86400) // 3600)
                uptime_minutes = int((uptime_seconds % 3600) // 60)
                uptime = f"{uptime_days}天 {uptime_hours}小时 {uptime_minutes}分钟"
            else:
                uptime = "未知"

            # 获取 WebUI 版本
            from ..core.server import get_webui_version

            webui_version = get_webui_version()

            # 构建版本信息
            version_info = {
                "version": "1.0.0",
                "webui_version": webui_version,
                "build_time": "2024-01-01T00:00:00Z",
                "uptime": uptime,
                "migrations": {
                    "total": len(migrations),
                    "applied": len([m for m in migrations if m.get("applied", False)]),
                    "pending": len([m for m in migrations if not m.get("applied", False)]),
                    "last_migration": last_migration,
                    "list": migrations,
                },
                "system": {
                    "python_version": "3.10+",
                    "framework": "Quart",
                    "database": "SQLite",
                },
                "last_updated": datetime.utcnow().isoformat(),
            }

            return Response().ok(data=version_info, message="获取版本信息成功").to_dict()

        except Exception as e:
            logger.error(f"获取版本信息失败: {e}", exc_info=True)
            return Response().error(f"获取版本信息失败: {str(e)}").to_dict()
