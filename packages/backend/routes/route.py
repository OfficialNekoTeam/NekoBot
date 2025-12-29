"""路由基类和响应模型

提供统一的路由注册和响应格式
"""

from typing import Any, Dict, Optional
from quart import request
from loguru import logger


class Response:
    """统一API响应格式"""

    def __init__(
        self, status: str = "success", message: str = "", data: Optional[Any] = None
    ):
        self.status = status
        self.message = message
        self.data = data

    def ok(self, data: Optional[Any] = None, message: str = "操作成功") -> "Response":
        """返回成功响应"""
        return Response(status="success", message=message, data=data)

    def error(self, message: str = "操作失败") -> "Response":
        """返回错误响应"""
        return Response(status="error", message=message, data=None)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result: Dict[str, Any] = {"status": self.status, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result


class RouteContext:
    """路由上下文，包含配置和应用引用"""

    def __init__(self, config: Dict[str, Any], app: Any):
        self.config = config
        self.app = app


class Route:
    """路由基类，提供路由注册功能"""

    def __init__(self, context: RouteContext):
        self.context = context
        self.routes: Dict[str, tuple] = {}
        self.register_routes()

    def register_routes(self) -> None:
        """注册所有路由，子类需要实现此方法"""
        pass

    async def get_request_data(self) -> Optional[Dict[str, Any]]:
        """获取请求数据"""
        try:
            return await request.get_json()
        except Exception as e:
            logger.error(f"获取请求数据失败: {e}")
            return None

    async def validate_required_fields(
        self, data: Dict[str, Any], required_fields: list[str]
    ) -> tuple[bool, str]:
        """验证必填字段"""
        for field in required_fields:
            if field not in data or not data[field]:
                return False, f"缺少必填字段: {field}"
        return True, ""
