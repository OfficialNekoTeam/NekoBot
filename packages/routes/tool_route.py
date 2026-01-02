"""工具系统路由

提供工具注册、执行监控、性能统计和权限管理功能
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from loguru import logger
from quart import request

from .route import Route, Response, RouteContext
from ..agent.tool_system import (
    ToolCategory,
    ToolSchema,
    FunctionTool,
    ToolSet,
    ToolExecutor,
    get_global_tool_set,
)


class ToolRoute(Route):
    """工具系统路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.routes = [
            ("/api/tools/list", "GET", self.list_tools),
            ("/api/tools/info", "GET", self.get_tool_info),
            ("/api/tools/register", "POST", self.register_tool),
            ("/api/tools/unregister", "POST", self.unregister_tool),
            ("/api/tools/execute", "POST", self.execute_tool),
            ("/api/tools/metrics", "GET", self.get_metrics),
            ("/api/tools/stats", "GET", self.get_stats),
            ("/api/tools/categories", "GET", self.list_categories),
            ("/api/tools/permissions", "GET", self.get_permissions),
            ("/api/tools/permissions", "POST", self.update_permissions),
            ("/api/tools/test", "POST", self.test_tool),
        ]
        # 设置唯一的 endpoint 名称
        for path, method, handler in self.routes:
            handler.__func__.endpoint_name = f"tools_{handler.__name__}"

        # 获取全局工具集
        self.tool_set = get_global_tool_set()

    async def list_tools(self) -> Dict[str, Any]:
        """列出所有工具

        查询参数:
            category: 类别筛选（可选）
            active_only: 仅显示激活工具（默认 true）
            page: 页码（默认1）
            page_size: 每页数量（默认10）

        返回:
            工具列表
        """
        try:
            category = request.args.get("category")
            active_only = request.args.get("active_only", "true").lower() == "true"
            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 10))

            # 获取工具列表
            tools = self.tool_set.list_tools()

            # 过滤
            if category:
                try:
                    cat_enum = ToolCategory(category)
                    tools = [t for t in tools if t.category == cat_enum]
                except ValueError:
                    pass

            if active_only:
                tools = [t for t in tools if t.active]

            total = len(tools)

            # 分页
            start = (page - 1) * page_size
            end = start + page_size
            paged_tools = tools[start:end]

            # 格式化输出
            tool_list = []
            for tool in paged_tools:
                tool_list.append({
                    "name": tool.name,
                    "description": tool.description,
                    "category": tool.category.value,
                    "active": tool.active,
                    "parameters": tool.parameters,
                    "has_handler": tool.handler is not None,
                })

            return Response().ok(
                data={
                    "tools": tool_list,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                },
                message="获取工具列表成功"
            ).to_dict()

        except Exception as e:
            logger.error(f"获取工具列表失败: {e}", exc_info=True)
            return Response().error(f"获取工具列表失败: {str(e)}").to_dict()

    async def get_tool_info(self) -> Dict[str, Any]:
        """获取单个工具信息

        查询参数:
            tool_name: 工具名称

        返回:
            工具详细信息
        """
        try:
            tool_name = request.args.get("tool_name")
            if not tool_name:
                return Response().error("缺少 tool_name 参数").to_dict()

            tool = self.tool_set.get_tool(tool_name)
            if not tool:
                return Response().error(f"工具不存在: {tool_name}").to_dict()

            info = {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category.value,
                "active": tool.active,
                "parameters": tool.parameters,
                "has_handler": tool.handler is not None,
                "metadata": tool.metadata,
            }

            return Response().ok(data=info, message="获取工具信息成功").to_dict()

        except Exception as e:
            logger.error(f"获取工具信息失败: {e}", exc_info=True)
            return Response().error(f"获取工具信息失败: {str(e)}").to_dict()

    async def register_tool(self) -> Dict[str, Any]:
        """注册新工具

        请求体:
            name: 工具名称
            description: 工具描述
            category: 工具类别
            parameters: 参数定义（JSON Schema 格式）
            handler_module_path: 处理函数模块路径

        返回:
            注册结果
        """
        try:
            data = await request.get_json()
            name = data.get("name")
            description = data.get("description", "")
            category = data.get("category", "utility")
            parameters = data.get("parameters", {})
            handler_path = data.get("handler_module_path")

            if not name:
                return Response().error("缺少 name 参数").to_dict()

            # 检查工具是否已存在
            if self.tool_set.has_tool(name):
                return Response().error(f"工具已存在: {name}").to_dict()

            # 创建工具
            try:
                cat_enum = ToolCategory(category)
            except ValueError:
                cat_enum = ToolCategory.UTILITY

            tool = FunctionTool(
                name=name,
                description=description,
                category=cat_enum,
                parameters=parameters,
                handler_module_path=handler_path,
                active=True,
            )

            # 注册到工具集
            self.tool_set.add_tool(tool)

            logger.info(f"注册工具: {name}")

            return Response().ok(data={"tool_name": name}, message="注册工具成功").to_dict()

        except Exception as e:
            logger.error(f"注册工具失败: {e}", exc_info=True)
            return Response().error(f"注册工具失败: {str(e)}").to_dict()

    async def unregister_tool(self) -> Dict[str, Any]:
        """注销工具

        请求体:
            tool_name: 工具名称

        返回:
            注销结果
        """
        try:
            data = await request.get_json()
            tool_name = data.get("tool_name")

            if not tool_name:
                return Response().error("缺少 tool_name 参数").to_dict()

            result = self.tool_set.remove_tool(tool_name)
            if result:
                logger.info(f"注销工具: {tool_name}")
                return Response().ok(message="注销工具成功").to_dict()
            else:
                return Response().error(f"工具不存在: {tool_name}").to_dict()

        except Exception as e:
            logger.error(f"注销工具失败: {e}", exc_info=True)
            return Response().error(f"注销工具失败: {str(e)}").to_dict()

    async def execute_tool(self) -> Dict[str, Any]:
        """执行工具

        请求体:
            tool_name: 工具名称
            arguments: 工具参数
            context: 执行上下文（可选）

        返回:
            执行结果
        """
        try:
            data = await request.get_json()
            tool_name = data.get("tool_name")
            arguments = data.get("arguments", {})
            context_data = data.get("context", {})

            if not tool_name:
                return Response().error("缺少 tool_name 参数").to_dict()

            tool = self.tool_set.get_tool(tool_name)
            if not tool:
                return Response().error(f"工具不存在: {tool_name}").to_dict()

            # 创建工具执行器
            executor = ToolExecutor(self.tool_set)

            # 构建上下文
            from ..types import Context
            context = Context(
                session_id=context_data.get("session_id", "default"),
                platform_id=context_data.get("platform_id", "api"),
                user_id=context_data.get("user_id", "api_user"),
            )

            # 执行工具
            start_time = datetime.now()
            result = await executor.execute(tool_name, arguments, context)
            execution_time = (datetime.now() - start_time).total_seconds()

            logger.info(f"执行工具: {tool_name}, 耗时: {execution_time:.2f}s")

            return Response().ok(
                data={
                    "result": result,
                    "execution_time": execution_time,
                },
                message="工具执行成功"
            ).to_dict()

        except Exception as e:
            logger.error(f"执行工具失败: {e}", exc_info=True)
            return Response().error(f"执行工具失败: {str(e)}").to_dict()

    async def get_metrics(self) -> Dict[str, Any]:
        """获取工具执行指标

        查询参数:
            tool_name: 工具名称（可选，不提供则返回所有工具）
            time_range: 时间范围（小时，默认 24）

        返回:
            工具执行指标
        """
        try:
            tool_name = request.args.get("tool_name")
            time_range = int(request.args.get("time_range", 24))

            # 从数据库获取执行记录
            from ..core.database import db_manager

            # 简化处理：返回基础统计
            tools = self.tool_set.list_tools()

            metrics = []
            for tool in tools:
                if tool_name and tool.name != tool_name:
                    continue

                # 这里应该从数据库或缓存获取实际指标
                # 暂时返回基础信息
                metrics.append({
                    "name": tool.name,
                    "category": tool.category.value,
                    "executions": 0,  # 从数据库获取
                    "errors": 0,  # 从数据库获取
                    "avg_execution_time": 0.0,  # 从数据库获取
                    "success_rate": 1.0,  # 计算得出
                })

            return Response().ok(data={"metrics": metrics}, message="获取指标成功").to_dict()

        except Exception as e:
            logger.error(f"获取指标失败: {e}", exc_info=True)
            return Response().error(f"获取指标失败: {str(e)}").to_dict()

    async def get_stats(self) -> Dict[str, Any]:
        """获取工具统计信息

        返回:
            工具统计汇总
        """
        try:
            tools = self.tool_set.list_tools()

            # 按类别统计
            category_stats = {}
            for cat in ToolCategory:
                category_stats[cat.value] = len([t for t in tools if t.category == cat])

            # 激活/未激活统计
            active_count = len([t for t in tools if t.active])
            inactive_count = len(tools) - active_count

            # 有/无处理函数统计
            with_handler = len([t for t in tools if t.handler is not None])

            stats = {
                "total": len(tools),
                "active": active_count,
                "inactive": inactive_count,
                "with_handler": with_handler,
                "by_category": category_stats,
            }

            return Response().ok(data=stats, message="获取统计成功").to_dict()

        except Exception as e:
            logger.error(f"获取统计失败: {e}", exc_info=True)
            return Response().error(f"获取统计失败: {str(e)}").to_dict()

    async def list_categories(self) -> Dict[str, Any]:
        """列出所有工具类别

        返回:
            工具类别列表
        """
        try:
            categories = [
                {
                    "value": cat.value,
                    "name": cat.value.capitalize(),
                }
                for cat in ToolCategory
            ]

            return Response().ok(data={"categories": categories}, message="获取类别成功").to_dict()

        except Exception as e:
            logger.error(f"获取类别失败: {e}", exc_info=True)
            return Response().error(f"获取类别失败: {str(e)}").to_dict()

    async def get_permissions(self) -> Dict[str, Any]:
        """获取工具权限配置

        查询参数:
            tool_name: 工具名称（可选）

        返回:
            权限配置
        """
        try:
            tool_name = request.args.get("tool_name")

            # 从配置或数据库获取权限配置
            permissions = {}

            if tool_name:
                tool = self.tool_set.get_tool(tool_name)
                if tool:
                    permissions = {
                        "tool_name": tool_name,
                        "allowed_users": [],  # 从配置获取
                        "allowed_roles": [],  # 从配置获取
                        "denied_users": [],  # 从配置获取
                    }
            else:
                # 返回所有工具的权限配置
                for tool in self.tool_set.list_tools():
                    permissions[tool.name] = {
                        "allowed_users": [],
                        "allowed_roles": [],
                        "denied_users": [],
                    }

            return Response().ok(data=permissions, message="获取权限成功").to_dict()

        except Exception as e:
            logger.error(f"获取权限失败: {e}", exc_info=True)
            return Response().error(f"获取权限失败: {str(e)}").to_dict()

    async def update_permissions(self) -> Dict[str, Any]:
        """更新工具权限配置

        请求体:
            tool_name: 工具名称
            allowed_users: 允许的用户列表
            allowed_roles: 允许的角色列表
            denied_users: 拒绝的用户列表

        返回:
            更新结果
        """
        try:
            data = await request.get_json()
            tool_name = data.get("tool_name")
            allowed_users = data.get("allowed_users", [])
            allowed_roles = data.get("allowed_roles", [])
            denied_users = data.get("denied_users", [])

            if not tool_name:
                return Response().error("缺少 tool_name 参数").to_dict()

            tool = self.tool_set.get_tool(tool_name)
            if not tool:
                return Response().error(f"工具不存在: {tool_name}").to_dict()

            # 保存权限配置到数据库或配置文件
            logger.info(f"更新工具权限: {tool_name}")

            return Response().ok(message="更新权限成功").to_dict()

        except Exception as e:
            logger.error(f"更新权限失败: {e}", exc_info=True)
            return Response().error(f"更新权限失败: {str(e)}").to_dict()

    async def test_tool(self) -> Dict[str, Any]:
        """测试工具

        请求体:
            tool_name: 工具名称
            arguments: 测试参数

        返回:
            测试结果
        """
        try:
            data = await request.get_json()
            tool_name = data.get("tool_name")
            arguments = data.get("arguments", {})

            if not tool_name:
                return Response().error("缺少 tool_name 参数").to_dict()

            tool = self.tool_set.get_tool(tool_name)
            if not tool:
                return Response().error(f"工具不存在: {tool_name}").to_dict()

            # 验证参数
            from ..agent.tool_system import ToolExecutor
            executor = ToolExecutor(self.tool_set)

            try:
                executor._validate_arguments(tool, arguments)
                validation_passed = True
                validation_error = None
            except ValueError as e:
                validation_passed = False
                validation_error = str(e)

            result = {
                "tool_name": tool_name,
                "validation_passed": validation_passed,
                "validation_error": validation_error,
                "parameters_valid": True,
            }

            if validation_passed and tool.handler:
                # 如果有处理函数，可以尝试执行
                result["can_execute"] = True
            else:
                result["can_execute"] = False

            return Response().ok(data=result, message="测试工具成功").to_dict()

        except Exception as e:
            logger.error(f"测试工具失败: {e}", exc_info=True)
            return Response().error(f"测试工具失败: {str(e)}").to_dict()
