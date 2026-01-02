"""Agent 管理路由

提供 Agent 状态、配置、执行日志和 Hook 管理
"""

from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger
from quart import request

from .route import Route, Response, RouteContext
from ..agent import (
    AgentConfig,
    BaseAgent,
    LLMAgent,
    AgentExecutor,
    AgentHookPhase,
    BaseAgentHooks,
    CompositeAgentHooks,
    LoggingAgentHooks,
    MetricsAgentHooks,
)
from ..types import Context, MessageChain


class AgentRoute(Route):
    """Agent 管理路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.routes = [
            ("/api/agent/list", "GET", self.list_agents),
            ("/api/agent/info", "GET", self.get_agent_info),
            ("/api/agent/config", "GET", self.get_agent_config),
            ("/api/agent/config", "POST", self.update_agent_config),
            ("/api/agent/execute", "POST", self.execute_agent),
            ("/api/agent/hooks/list", "GET", self.list_hooks),
            ("/api/agent/hooks/add", "POST", self.add_hook),
            ("/api/agent/hooks/remove", "POST", self.remove_hook),
            ("/api/agent/metrics", "GET", self.get_metrics),
            ("/api/agent/logs", "GET", self.get_logs),
        ]
        # 设置唯一的 endpoint 名称
        for path, method, handler in self.routes:
            handler.__func__.endpoint_name = f"agent_{handler.__name__}"

        # 获取 Agent 执行器
        self.agent_executor: Optional[AgentExecutor] = context.app.plugins.get("agent_executor")

    async def list_agents(self) -> Dict[str, Any]:
        """列出所有 Agent

        查询参数:
            page: 页码（默认1）
            page_size: 每页数量（默认10）

        返回:
            Agent 列表
        """
        try:
            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 10))

            if not self.agent_executor:
                return Response().ok(data={"agents": [], "total": 0}, message="Agent 执行器未初始化").to_dict()

            agent_ids = self.agent_executor.list_agents()
            total = len(agent_ids)

            # 分页
            start = (page - 1) * page_size
            end = start + page_size
            paged_ids = agent_ids[start:end]

            agents = []
            for agent_id in paged_ids:
                agent = self.agent_executor.get(agent_id)
                if agent:
                    agents.append({
                        "id": agent_id,
                        "name": agent.name,
                        "config": {
                            "llm_provider_id": agent.config.llm_provider_id,
                            "model": agent.config.model,
                            "temperature": agent.config.temperature,
                            "enable_tools": agent.config.enable_tools,
                            "enable_stream": agent.config.enable_stream,
                        }
                    })

            return Response().ok(
                data={
                    "agents": agents,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                },
                message="获取 Agent 列表成功"
            ).to_dict()

        except Exception as e:
            logger.error(f"获取 Agent 列表失败: {e}", exc_info=True)
            return Response().error(f"获取 Agent 列表失败: {str(e)}").to_dict()

    async def get_agent_info(self) -> Dict[str, Any]:
        """获取单个 Agent 信息

        查询参数:
            agent_id: Agent ID

        返回:
            Agent 详细信息
        """
        try:
            agent_id = request.args.get("agent_id")
            if not agent_id:
                return Response().error("缺少 agent_id 参数").to_dict()

            if not self.agent_executor:
                return Response().error("Agent 执行器未初始化").to_dict()

            agent = self.agent_executor.get(agent_id)
            if not agent:
                return Response().error(f"Agent 不存在: {agent_id}").to_dict()

            # 获取 Agent 状态信息
            info = {
                "id": agent_id,
                "name": agent.name,
                "config": {
                    "llm_provider_id": agent.config.llm_provider_id,
                    "model": agent.config.model,
                    "temperature": agent.config.temperature,
                    "max_tokens": agent.config.max_tokens,
                    "max_iterations": agent.config.max_iterations,
                    "enable_stream": agent.config.enable_stream,
                    "enable_tools": agent.config.enable_tools,
                    "system_prompt": agent.config.system_prompt,
                },
                "hooks_count": len(agent.config.hooks) if agent.config.hooks else 0,
                "tools_count": len(agent.config.tools.list_tools()) if agent.config.tools else 0,
            }

            return Response().ok(data=info, message="获取 Agent 信息成功").to_dict()

        except Exception as e:
            logger.error(f"获取 Agent 信息失败: {e}", exc_info=True)
            return Response().error(f"获取 Agent 信息失败: {str(e)}").to_dict()

    async def get_agent_config(self) -> Dict[str, Any]:
        """获取 Agent 配置

        查询参数:
            agent_id: Agent ID

        返回:
            Agent 配置
        """
        try:
            agent_id = request.args.get("agent_id")
            if not agent_id:
                return Response().error("缺少 agent_id 参数").to_dict()

            if not self.agent_executor:
                return Response().error("Agent 执行器未初始化").to_dict()

            agent = self.agent_executor.get(agent_id)
            if not agent:
                return Response().error(f"Agent 不存在: {agent_id}").to_dict()

            config = agent.config

            return Response().ok(
                data={
                    "name": config.name,
                    "llm_provider_id": config.llm_provider_id,
                    "model": config.model,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                    "max_iterations": config.max_iterations,
                    "enable_stream": config.enable_stream,
                    "enable_tools": config.enable_tools,
                    "system_prompt": config.system_prompt,
                    "metadata": config.metadata,
                },
                message="获取 Agent 配置成功"
            ).to_dict()

        except Exception as e:
            logger.error(f"获取 Agent 配置失败: {e}", exc_info=True)
            return Response().error(f"获取 Agent 配置失败: {str(e)}").to_dict()

    async def update_agent_config(self) -> Dict[str, Any]:
        """更新 Agent 配置

        请求体:
            agent_id: Agent ID
            config: 配置数据

        返回:
            更新结果
        """
        try:
            data = await request.get_json()
            agent_id = data.get("agent_id")
            config_data = data.get("config", {})

            if not agent_id:
                return Response().error("缺少 agent_id 参数").to_dict()

            if not self.agent_executor:
                return Response().error("Agent 执行器未初始化").to_dict()

            agent = self.agent_executor.get(agent_id)
            if not agent:
                return Response().error(f"Agent 不存在: {agent_id}").to_dict()

            # 更新配置
            if "temperature" in config_data:
                agent.config.temperature = config_data["temperature"]
            if "max_tokens" in config_data:
                agent.config.max_tokens = config_data["max_tokens"]
            if "enable_stream" in config_data:
                agent.config.enable_stream = config_data["enable_stream"]
            if "enable_tools" in config_data:
                agent.config.enable_tools = config_data["enable_tools"]
            if "system_prompt" in config_data:
                agent.config.system_prompt = config_data["system_prompt"]

            logger.info(f"Agent {agent_id} 配置已更新")

            return Response().ok(message="更新 Agent 配置成功").to_dict()

        except Exception as e:
            logger.error(f"更新 Agent 配置失败: {e}", exc_info=True)
            return Response().error(f"更新 Agent 配置失败: {str(e)}").to_dict()

    async def execute_agent(self) -> Dict[str, Any]:
        """执行 Agent

        请求体:
            agent_id: Agent ID
            message: 消息内容
            context: 上下文信息（可选）
            stream: 是否流式响应（默认 false）

        返回:
            Agent 响应结果
        """
        try:
            data = await request.get_json()
            agent_id = data.get("agent_id")
            message = data.get("message")
            context_data = data.get("context", {})
            stream = data.get("stream", False)

            if not agent_id:
                return Response().error("缺少 agent_id 参数").to_dict()
            if not message:
                return Response().error("缺少 message 参数").to_dict()

            if not self.agent_executor:
                return Response().error("Agent 执行器未初始化").to_dict()

            # 构建上下文
            context = Context(
                session_id=context_data.get("session_id", "default"),
                platform_id=context_data.get("platform_id", "api"),
                user_id=context_data.get("user_id", "api_user"),
                channel_id=context_data.get("channel_id"),
            )

            # 执行 Agent
            result = await self.agent_executor.execute(
                agent_id=agent_id,
                message=message,
                context=context,
                stream=stream
            )

            # 处理响应
            if hasattr(result, "to_dict"):
                response_data = result.to_dict()
            elif hasattr(result, "__aiter__"):
                # 流式响应 - 收集所有内容
                chunks = []
                async for chunk in result:
                    chunks.append(chunk)
                response_data = {
                    "content": "".join(chunks),
                    "finished": True
                }
            else:
                response_data = {"content": str(result), "finished": True}

            return Response().ok(data=response_data, message="Agent 执行成功").to_dict()

        except Exception as e:
            logger.error(f"执行 Agent 失败: {e}", exc_info=True)
            return Response().error(f"执行 Agent 失败: {str(e)}").to_dict()

    async def list_hooks(self) -> Dict[str, Any]:
        """列出 Agent 的 Hooks

        查询参数:
            agent_id: Agent ID

        返回:
            Hooks 列表
        """
        try:
            agent_id = request.args.get("agent_id")
            if not agent_id:
                return Response().error("缺少 agent_id 参数").to_dict()

            if not self.agent_executor:
                return Response().error("Agent 执行器未初始化").to_dict()

            agent = self.agent_executor.get(agent_id)
            if not agent:
                return Response().error(f"Agent 不存在: {agent_id}").to_dict()

            hooks = []
            if agent._hooks:
                for hook in agent._hooks._hooks:
                    hooks.append({
                        "type": type(hook).__name__,
                        "name": getattr(hook, "__class__", {}).get("__name__", "Unknown"),
                    })

            return Response().ok(data={"hooks": hooks}, message="获取 Hooks 列表成功").to_dict()

        except Exception as e:
            logger.error(f"获取 Hooks 列表失败: {e}", exc_info=True)
            return Response().error(f"获取 Hooks 列表失败: {str(e)}").to_dict()

    async def add_hook(self) -> Dict[str, Any]:
        """添加 Hook 到 Agent

        请求体:
            agent_id: Agent ID
            hook_type: Hook 类型 (logging/metrics)

        返回:
            添加结果
        """
        try:
            data = await request.get_json()
            agent_id = data.get("agent_id")
            hook_type = data.get("hook_type")

            if not agent_id:
                return Response().error("缺少 agent_id 参数").to_dict()
            if not hook_type:
                return Response().error("缺少 hook_type 参数").to_dict()

            if not self.agent_executor:
                return Response().error("Agent 执行器未初始化").to_dict()

            agent = self.agent_executor.get(agent_id)
            if not agent:
                return Response().error(f"Agent 不存在: {agent_id}").to_dict()

            # 创建 Hook
            if hook_type == "logging":
                hook = LoggingAgentHooks()
            elif hook_type == "metrics":
                hook = MetricsAgentHooks()
            else:
                return Response().error(f"不支持的 Hook 类型: {hook_type}").to_dict()

            # 添加 Hook
            agent.add_hook(hook)

            logger.info(f"Agent {agent_id} 添加 Hook: {hook_type}")

            return Response().ok(message="添加 Hook 成功").to_dict()

        except Exception as e:
            logger.error(f"添加 Hook 失败: {e}", exc_info=True)
            return Response().error(f"添加 Hook 失败: {str(e)}").to_dict()

    async def remove_hook(self) -> Dict[str, Any]:
        """从 Agent 移除 Hook

        请求体:
            agent_id: Agent ID
            hook_index: Hook 索引

        返回:
            移除结果
        """
        try:
            data = await request.get_json()
            agent_id = data.get("agent_id")
            hook_index = data.get("hook_index")

            if not agent_id:
                return Response().error("缺少 agent_id 参数").to_dict()
            if hook_index is None:
                return Response().error("缺少 hook_index 参数").to_dict()

            if not self.agent_executor:
                return Response().error("Agent 执行器未初始化").to_dict()

            agent = self.agent_executor.get(agent_id)
            if not agent:
                return Response().error(f"Agent 不存在: {agent_id}").to_dict()

            # 移除 Hook
            if agent._hooks and 0 <= hook_index < len(agent._hooks._hooks):
                hook = agent._hooks._hooks.pop(hook_index)
                logger.info(f"Agent {agent_id} 移除 Hook: {type(hook).__name__}")
                return Response().ok(message="移除 Hook 成功").to_dict()
            else:
                return Response().error("Hook 索引无效").to_dict()

        except Exception as e:
            logger.error(f"移除 Hook 失败: {e}", exc_info=True)
            return Response().error(f"移除 Hook 失败: {str(e)}").to_dict()

    async def get_metrics(self) -> Dict[str, Any]:
        """获取 Agent 指标

        查询参数:
            agent_id: Agent ID

        返回:
            Agent 执行指标
        """
        try:
            agent_id = request.args.get("agent_id")
            if not agent_id:
                return Response().error("缺少 agent_id 参数").to_dict()

            if not self.agent_executor:
                return Response().error("Agent 执行器未初始化").to_dict()

            agent = self.agent_executor.get(agent_id)
            if not agent:
                return Response().error(f"Agent 不存在: {agent_id}").to_dict()

            # 查找 MetricsAgentHooks
            metrics = {}
            if agent._hooks:
                for hook in agent._hooks._hooks:
                    if isinstance(hook, MetricsAgentHooks):
                        metrics = hook.get_metrics(agent.name)
                        break

            return Response().ok(data=metrics, message="获取指标成功").to_dict()

        except Exception as e:
            logger.error(f"获取指标失败: {e}", exc_info=True)
            return Response().error(f"获取指标失败: {str(e)}").to_dict()

    async def get_logs(self) -> Dict[str, Any]:
        """获取 Agent 执行日志

        查询参数:
            agent_id: Agent ID
            limit: 返回数量（默认 50）

        返回:
            执行日志列表
        """
        try:
            agent_id = request.args.get("agent_id")
            limit = int(request.args.get("limit", 50))

            if not agent_id:
                return Response().error("缺少 agent_id 参数").to_dict()

            # 从数据库获取操作日志
            from ..core.database import db_manager

            logs = db_manager.get_operation_logs(limit=limit)

            # 过滤出与该 Agent 相关的日志
            agent_logs = [
                log for log in logs
                if log.get("details", {}).get("agent_id") == agent_id
            ]

            return Response().ok(
                data={"logs": agent_logs, "count": len(agent_logs)},
                message="获取日志成功"
            ).to_dict()

        except Exception as e:
            logger.error(f"获取日志失败: {e}", exc_info=True)
            return Response().error(f"获取日志失败: {str(e)}").to_dict()
