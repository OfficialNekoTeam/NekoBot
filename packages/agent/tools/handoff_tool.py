"""Handoff工具

用于Agent切换和流程控制
"""

from typing import Dict, Any, Optional
from loguru import logger

from .base import BaseTool


class HandoffTool(BaseTool):
    """Handoff工具
    
    用于将对话权移交给另一个Agent或工具
    """

    def __init__(
        self,
        agent_name: str,
        description: str = "",
        next_agent: Optional[str] = None,
    ):
        """初始化Handoff工具
        
        Args:
            agent_name: 接管的Agent名称
            description: 工具描述
            next_agent: 下一个Agent的标识符
        """
        self._agent_name = agent_name
        self._description = description
        self._next_agent = next_agent
        self._parameters_schema = {
            "agent_name": {
                "type": "string",
                "description": "要切换到的Agent名称",
            },
            "description": {
                "type": "string",
                "description": "切换原因描述（可选）",
            },
            "next_agent": {
                "type": "string",
                "description": "下一个Agent的标识符（可选）",
            },
        }

    @property
    def name(self) -> str:
        """工具名称"""
        return self._agent_name

    @property
    def description(self) -> str:
        """工具描述"""
        return self._description

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        """参数Schema"""
        return self._parameters_schema

    async def execute(
        self,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """执行Handoff切换
        
        Args:
            parameters: 参数字典
            context: 执行上下文
            
        Returns:
            包含切换信息的字典
        """
        agent_name = parameters.get("agent_name", "")
        description = parameters.get("description", self._description)
        next_agent = parameters.get("next_agent", self._next_agent)
        
        logger.info(f"执行Handoff切换，从 {self._agent_name} 切换到 {next_agent}")
        
        return {
            "tool_name": self._agent_name,
            "agent_name": agent_name,
            "description": description,
            "next_agent": next_agent,
            "reason": f"切换到Agent: {next_agent}",
        }

    def __repr__(self) -> str:
        return f"HandoffTool({self._agent_name})"