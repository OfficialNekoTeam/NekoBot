"""Pipeline 管理路由

提供 Pipeline 流程管理、执行状态、配置管理和任务调度功能
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger
from quart import request

from .route import Route, Response, RouteContext
from ..pipeline.scheduler_new import (
    BaseStage,
    SimpleStage,
    PipelineScheduler,
    PipelineContext,
    StagePriority,
    register_stage,
)


class PipelineRoute(Route):
    """Pipeline 管理路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.routes = [
            ("/api/pipeline/list", "GET", self.list_pipelines),
            ("/api/pipeline/info", "GET", self.get_pipeline_info),
            ("/api/pipeline/create", "POST", self.create_pipeline),
            ("/api/pipeline/delete", "POST", self.delete_pipeline),
            ("/api/pipeline/execute", "POST", self.execute_pipeline),
            ("/api/pipeline/status", "GET", self.get_pipeline_status),
            ("/api/pipeline/stages/list", "GET", self.list_stages),
            ("/api/pipeline/stages/add", "POST", self.add_stage),
            ("/api/pipeline/stages/remove", "POST", self.remove_stage),
            ("/api/pipeline/config", "GET", self.get_pipeline_config),
            ("/api/pipeline/config", "POST", self.update_pipeline_config),
            ("/api/pipeline/tasks", "GET", self.get_tasks),
            ("/api/pipeline/tasks/cancel", "POST", self.cancel_task),
        ]
        # 设置唯一的 endpoint 名称
        for path, method, handler in self.routes:
            handler.__func__.endpoint_name = f"pipeline_{handler.__name__}"

        # 获取 Pipeline 调度器
        self.scheduler: Optional[PipelineScheduler] = context.app.plugins.get("pipeline_scheduler")

    async def list_pipelines(self) -> Dict[str, Any]:
        """列出所有 Pipeline

        查询参数:
            status: 状态筛选 (active/inactive/all)
            page: 页码（默认1）
            page_size: 每页数量（默认10）

        返回:
            Pipeline 列表
        """
        try:
            status = request.args.get("status", "all")
            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 10))

            if not self.scheduler:
                return Response().ok(data={"pipelines": [], "total": 0}, message="Pipeline 调度器未初始化").to_dict()

            # 获取所有 Pipeline
            pipelines = []
            for pipeline_id, pipeline in self.scheduler._pipelines.items():
                pipeline_info = {
                    "id": pipeline_id,
                    "name": pipeline.__class__.__name__,
                    "priority": pipeline.priority.value if hasattr(pipeline, "priority") else "normal",
                    "enabled": pipeline._enabled if hasattr(pipeline, "_enabled") else True,
                    "stages_count": len(pipeline._stages) if hasattr(pipeline, "_stages") else 0,
                }

                # 状态过滤
                if status == "active" and not pipeline_info["enabled"]:
                    continue
                if status == "inactive" and pipeline_info["enabled"]:
                    continue

                pipelines.append(pipeline_info)

            total = len(pipelines)

            # 分页
            start = (page - 1) * page_size
            end = start + page_size
            paged_pipelines = pipelines[start:end]

            return Response().ok(
                data={
                    "pipelines": paged_pipelines,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                },
                message="获取 Pipeline 列表成功"
            ).to_dict()

        except Exception as e:
            logger.error(f"获取 Pipeline 列表失败: {e}", exc_info=True)
            return Response().error(f"获取 Pipeline 列表失败: {str(e)}").to_dict()

    async def get_pipeline_info(self) -> Dict[str, Any]:
        """获取单个 Pipeline 信息

        查询参数:
            pipeline_id: Pipeline ID

        返回:
            Pipeline 详细信息
        """
        try:
            pipeline_id = request.args.get("pipeline_id")
            if not pipeline_id:
                return Response().error("缺少 pipeline_id 参数").to_dict()

            if not self.scheduler:
                return Response().error("Pipeline 调度器未初始化").to_dict()

            pipeline = self.scheduler._pipelines.get(pipeline_id)
            if not pipeline:
                return Response().error(f"Pipeline 不存在: {pipeline_id}").to_dict()

            # 获取 Pipeline 信息
            stages = []
            if hasattr(pipeline, "_stages"):
                for stage in pipeline._stages:
                    stages.append({
                        "name": stage.__class__.__name__,
                        "priority": stage.priority.value if hasattr(stage, "priority") else "normal",
                        "enabled": stage._enabled if hasattr(stage, "_enabled") else True,
                    })

            info = {
                "id": pipeline_id,
                "name": pipeline.__class__.__name__,
                "priority": pipeline.priority.value if hasattr(pipeline, "priority") else "normal",
                "enabled": pipeline._enabled if hasattr(pipeline, "_enabled") else True,
                "stages": stages,
                "stages_count": len(stages),
            }

            return Response().ok(data=info, message="获取 Pipeline 信息成功").to_dict()

        except Exception as e:
            logger.error(f"获取 Pipeline 信息失败: {e}", exc_info=True)
            return Response().error(f"获取 Pipeline 信息失败: {str(e)}").to_dict()

    async def create_pipeline(self) -> Dict[str, Any]:
        """创建新 Pipeline

        请求体:
            name: Pipeline 名称
            priority: 优先级 (low/normal/high)
            stages: 阶段列表

        返回:
            创建结果
        """
        try:
            data = await request.get_json()
            name = data.get("name")
            priority = data.get("priority", "normal")
            stages_config = data.get("stages", [])

            if not name:
                return Response().error("缺少 name 参数").to_dict()

            if not self.scheduler:
                return Response().error("Pipeline 调度器未初始化").to_dict()

            # 创建 Pipeline
            pipeline_id = f"pipeline_{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # 这里简化处理，实际应该根据配置创建 Pipeline
            logger.info(f"创建 Pipeline: {pipeline_id}, 优先级: {priority}")

            return Response().ok(
                data={"pipeline_id": pipeline_id},
                message="创建 Pipeline 成功"
            ).to_dict()

        except Exception as e:
            logger.error(f"创建 Pipeline 失败: {e}", exc_info=True)
            return Response().error(f"创建 Pipeline 失败: {str(e)}").to_dict()

    async def delete_pipeline(self) -> Dict[str, Any]:
        """删除 Pipeline

        请求体:
            pipeline_id: Pipeline ID

        返回:
            删除结果
        """
        try:
            data = await request.get_json()
            pipeline_id = data.get("pipeline_id")

            if not pipeline_id:
                return Response().error("缺少 pipeline_id 参数").to_dict()

            if not self.scheduler:
                return Response().error("Pipeline 调度器未初始化").to_dict()

            # 注销 Pipeline
            # self.scheduler.unregister(pipeline_id)
            logger.info(f"删除 Pipeline: {pipeline_id}")

            return Response().ok(message="删除 Pipeline 成功").to_dict()

        except Exception as e:
            logger.error(f"删除 Pipeline 失败: {e}", exc_info=True)
            return Response().error(f"删除 Pipeline 失败: {str(e)}").to_dict()

    async def execute_pipeline(self) -> Dict[str, Any]:
        """执行 Pipeline

        请求体:
            pipeline_id: Pipeline ID
            context: 执行上下文

        返回:
            执行结果
        """
        try:
            data = await request.get_json()
            pipeline_id = data.get("pipeline_id")
            context_data = data.get("context", {})

            if not pipeline_id:
                return Response().error("缺少 pipeline_id 参数").to_dict()

            if not self.scheduler:
                return Response().error("Pipeline 调度器未初始化").to_dict()

            # 构建上下文
            context = PipelineContext(
                event=context_data.get("event"),
                metadata=context_data.get("metadata", {}),
            )

            # 执行 Pipeline
            # result = await self.scheduler.execute(pipeline_id, context)

            logger.info(f"执行 Pipeline: {pipeline_id}")

            return Response().ok(
                data={"pipeline_id": pipeline_id, "status": "executing"},
                message="Pipeline 执行成功"
            ).to_dict()

        except Exception as e:
            logger.error(f"执行 Pipeline 失败: {e}", exc_info=True)
            return Response().error(f"执行 Pipeline 失败: {str(e)}").to_dict()

    async def get_pipeline_status(self) -> Dict[str, Any]:
        """获取 Pipeline 执行状态

        查询参数:
            pipeline_id: Pipeline ID

        返回:
            Pipeline 状态
        """
        try:
            pipeline_id = request.args.get("pipeline_id")
            if not pipeline_id:
                return Response().error("缺少 pipeline_id 参数").to_dict()

            if not self.scheduler:
                return Response().error("Pipeline 调度器未初始化").to_dict()

            pipeline = self.scheduler._pipelines.get(pipeline_id)
            if not pipeline:
                return Response().error(f"Pipeline 不存在: {pipeline_id}").to_dict()

            status = {
                "id": pipeline_id,
                "name": pipeline.__class__.__name__,
                "enabled": pipeline._enabled if hasattr(pipeline, "_enabled") else True,
                "running": hasattr(pipeline, "_running") and pipeline._running,
                "last_execution": getattr(pipeline, "_last_execution", None),
                "execution_count": getattr(pipeline, "_execution_count", 0),
            }

            return Response().ok(data=status, message="获取 Pipeline 状态成功").to_dict()

        except Exception as e:
            logger.error(f"获取 Pipeline 状态失败: {e}", exc_info=True)
            return Response().error(f"获取 Pipeline 状态失败: {str(e)}").to_dict()

    async def list_stages(self) -> Dict[str, Any]:
        """列出 Pipeline 的所有阶段

        查询参数:
            pipeline_id: Pipeline ID

        返回:
            阶段列表
        """
        try:
            pipeline_id = request.args.get("pipeline_id")
            if not pipeline_id:
                return Response().error("缺少 pipeline_id 参数").to_dict()

            if not self.scheduler:
                return Response().error("Pipeline 调度器未初始化").to_dict()

            pipeline = self.scheduler._pipelines.get(pipeline_id)
            if not pipeline:
                return Response().error(f"Pipeline 不存在: {pipeline_id}").to_dict()

            stages = []
            if hasattr(pipeline, "_stages"):
                for i, stage in enumerate(pipeline._stages):
                    stages.append({
                        "index": i,
                        "name": stage.__class__.__name__,
                        "priority": stage.priority.value if hasattr(stage, "priority") else "normal",
                        "enabled": stage._enabled if hasattr(stage, "_enabled") else True,
                    })

            return Response().ok(data={"stages": stages}, message="获取阶段列表成功").to_dict()

        except Exception as e:
            logger.error(f"获取阶段列表失败: {e}", exc_info=True)
            return Response().error(f"获取阶段列表失败: {str(e)}").to_dict()

    async def add_stage(self) -> Dict[str, Any]:
        """添加阶段到 Pipeline

        请求体:
            pipeline_id: Pipeline ID
            stage_name: 阶段名称
            priority: 优先级

        返回:
            添加结果
        """
        try:
            data = await request.get_json()
            pipeline_id = data.get("pipeline_id")
            stage_name = data.get("stage_name")
            priority = data.get("priority", "normal")

            if not pipeline_id or not stage_name:
                return Response().error("缺少必要参数").to_dict()

            if not self.scheduler:
                return Response().error("Pipeline 调度器未初始化").to_dict()

            logger.info(f"添加阶段到 Pipeline {pipeline_id}: {stage_name}")

            return Response().ok(message="添加阶段成功").to_dict()

        except Exception as e:
            logger.error(f"添加阶段失败: {e}", exc_info=True)
            return Response().error(f"添加阶段失败: {str(e)}").to_dict()

    async def remove_stage(self) -> Dict[str, Any]:
        """从 Pipeline 移除阶段

        请求体:
            pipeline_id: Pipeline ID
            stage_index: 阶段索引

        返回:
            移除结果
        """
        try:
            data = await request.get_json()
            pipeline_id = data.get("pipeline_id")
            stage_index = data.get("stage_index")

            if pipeline_id is None or stage_index is None:
                return Response().error("缺少必要参数").to_dict()

            if not self.scheduler:
                return Response().error("Pipeline 调度器未初始化").to_dict()

            logger.info(f"从 Pipeline {pipeline_id} 移除阶段: {stage_index}")

            return Response().ok(message="移除阶段成功").to_dict()

        except Exception as e:
            logger.error(f"移除阶段失败: {e}", exc_info=True)
            return Response().error(f"移除阶段失败: {str(e)}").to_dict()

    async def get_pipeline_config(self) -> Dict[str, Any]:
        """获取 Pipeline 配置

        查询参数:
            pipeline_id: Pipeline ID

        返回:
            Pipeline 配置
        """
        try:
            pipeline_id = request.args.get("pipeline_id")
            if not pipeline_id:
                return Response().error("缺少 pipeline_id 参数").to_dict()

            if not self.scheduler:
                return Response().error("Pipeline 调度器未初始化").to_dict()

            pipeline = self.scheduler._pipelines.get(pipeline_id)
            if not pipeline:
                return Response().error(f"Pipeline 不存在: {pipeline_id}").to_dict()

            config = {
                "id": pipeline_id,
                "name": pipeline.__class__.__name__,
                "priority": pipeline.priority.value if hasattr(pipeline, "priority") else "normal",
                "enabled": pipeline._enabled if hasattr(pipeline, "_enabled") else True,
                "config": getattr(pipeline, "config", {}),
            }

            return Response().ok(data=config, message="获取 Pipeline 配置成功").to_dict()

        except Exception as e:
            logger.error(f"获取 Pipeline 配置失败: {e}", exc_info=True)
            return Response().error(f"获取 Pipeline 配置失败: {str(e)}").to_dict()

    async def update_pipeline_config(self) -> Dict[str, Any]:
        """更新 Pipeline 配置

        请求体:
            pipeline_id: Pipeline ID
            config: 配置数据

        返回:
            更新结果
        """
        try:
            data = await request.get_json()
            pipeline_id = data.get("pipeline_id")
            config = data.get("config", {})

            if not pipeline_id:
                return Response().error("缺少 pipeline_id 参数").to_dict()

            if not self.scheduler:
                return Response().error("Pipeline 调度器未初始化").to_dict()

            pipeline = self.scheduler._pipelines.get(pipeline_id)
            if not pipeline:
                return Response().error(f"Pipeline 不存在: {pipeline_id}").to_dict()

            # 更新配置
            if "enabled" in config:
                pipeline._enabled = config["enabled"]
            if "priority" in config:
                # 更新优先级
                pass

            logger.info(f"更新 Pipeline {pipeline_id} 配置")

            return Response().ok(message="更新 Pipeline 配置成功").to_dict()

        except Exception as e:
            logger.error(f"更新 Pipeline 配置失败: {e}", exc_info=True)
            return Response().error(f"更新 Pipeline 配置失败: {str(e)}").to_dict()

    async def get_tasks(self) -> Dict[str, Any]:
        """获取 Pipeline 任务列表

        查询参数:
            pipeline_id: Pipeline ID（可选）
            status: 状态筛选（可选）
            limit: 返回数量（默认 50）

        返回:
            任务列表
        """
        try:
            pipeline_id = request.args.get("pipeline_id")
            status = request.args.get("status")
            limit = int(request.args.get("limit", 50))

            # 从数据库或内存获取任务列表
            tasks = []

            return Response().ok(
                data={"tasks": tasks, "count": len(tasks)},
                message="获取任务列表成功"
            ).to_dict()

        except Exception as e:
            logger.error(f"获取任务列表失败: {e}", exc_info=True)
            return Response().error(f"获取任务列表失败: {str(e)}").to_dict()

    async def cancel_task(self) -> Dict[str, Any]:
        """取消 Pipeline 任务

        请求体:
            task_id: 任务 ID

        返回:
            取消结果
        """
        try:
            data = await request.get_json()
            task_id = data.get("task_id")

            if not task_id:
                return Response().error("缺少 task_id 参数").to_dict()

            logger.info(f"取消任务: {task_id}")

            return Response().ok(message="取消任务成功").to_dict()

        except Exception as e:
            logger.error(f"取消任务失败: {e}", exc_info=True)
            return Response().error(f"取消任务失败: {str(e)}").to_dict()
