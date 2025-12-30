"""Agent执行引擎

管理Agent的生命周期、工具调用和错误处理
"""

from typing import Dict, Any, Optional
from loguru import logger
import asyncio

from .base import BaseAgent
from .tools import ToolRegistry


class AgentExecutor:
    """Agent执行引擎
    
    负责Agent的生命周期管理、工具调用和错误处理
    """

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        """初始化Agent执行引擎
        
        Args:
            tool_registry: 工具注册表（可选）
        """
        self.tool_registry = tool_registry or ToolRegistry()
        self._agents: Dict[str, BaseAgent] = {}
        self._running = False

    def register_agent(self, agent_id: str, agent: BaseAgent):
        """注册Agent
        
        Args:
            agent_id: Agent标识符
            agent: Agent实例
        """
        self._agents[agent_id] = agent
        logger.info(f"已注册Agent: {agent_id}")

    def unregister_agent(self, agent_id: str) -> bool:
        """注销Agent
        
        Args:
            agent_id: Agent标识符
            
        Returns:
            是否注销成功
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"已注销Agent: {agent_id}")
            return True
        
        logger.warning(f"Agent {agent_id} 不存在")
        return False

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """获取Agent
        
        Args:
            agent_id: Agent标识符
            
        Returns:
            Agent实例，如果不存在则返回 None
        """
        return self._agents.get(agent_id)

    def list_agents(self):
        """列出所有Agent ID
        
        Returns:
            Agent ID列表
        """
        return list(self._agents.keys())

    async def start(self):
        """启动Agent执行引擎"""
        self._running = True
        logger.info("Agent执行引擎已启动")

    async def stop(self):
        """停止Agent执行引擎"""
        self._running = False
        logger.info("Agent执行引擎已停止")

    def is_running(self) -> bool:
        """检查是否正在运行
        
        Returns:
            是否正在运行
        """
        return self._running

    async def process_message(
        self,
        agent_id: str,
        message: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[str]:
        """使用Agent处理消息
        
        Args:
            agent_id: Agent标识符
            message: 消息数据
            context: 对话上下文
            
        Returns:
            Agent响应，如果Agent无法处理则返回 None
        """
        agent = self.get_agent(agent_id)
        
        if not agent:
            logger.error(f"Agent {agent_id} 不存在")
            return None
        
        try:
            # 获取对话上下文
            session_id = message.get("session_id", "default")
            agent_context = await agent.get_context(session_id)
            
            # 处理消息
            response = await agent.process_message(message, agent_context)
            
            # 更新对话上下文
            if agent_context:
                await agent.update_context(session_id, agent_context)
            
            return response
        except Exception as e:
            logger.error(f"Agent {agent_id} 处理消息时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    async def call_tool(
        self,
        agent_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> Any:
        """调用工具
        
        Args:
            agent_id: Agent标识符
            tool_name: 工具名称
            parameters: 工具参数
            
        Returns:
            工具执行结果
        """
        agent = self.get_agent(agent_id)
        
        if not agent:
            raise ValueError(f"Agent {agent_id} 不存在")
        
        try:
            return await agent.call_tool(tool_name, parameters)
        except Exception as e:
            logger.error(f"Agent {agent_id} 调用工具 {tool_name} 时出错: {e}")
            raise RuntimeError(f"工具调用错误: {e}")

    def get_agent_count(self) -> int:
        """获取Agent总数
        
        Returns:
            Agent总数
        """
        return len(self._agents)

    def get_tool_registry(self) -> ToolRegistry:
        """获取工具注册表
        
        Returns:
            工具注册表实例
        """
        return self.tool_registry


# 创建全局Agent执行引擎实例
agent_executor = AgentExecutor()