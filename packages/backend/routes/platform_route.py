"""平台路由

提供平台统计信息和统一 Webhook 回调功能
"""

from typing import Dict, Any
from loguru import logger

from .route import Route, Response, RouteContext
from ..core.server import platform_manager


class PlatformRoute(Route):
    """平台路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.platform_manager = platform_manager
        self.routes = {
            "/api/platform/stats": ("GET", self.get_platform_stats),
        }

    async def get_platform_stats(self) -> Dict[str, Any]:
        """获取所有平台的统计信息

        Returns:
            包含平台统计信息的响应
        """
        try:
            stats = self.platform_manager.get_all_stats()
            return Response().ok(data=stats).to_dict()
        except Exception as e:
            logger.error(f"获取平台统计信息失败: {e}")
            return Response().error(f"获取统计信息失败: {str(e)}").to_dict()
