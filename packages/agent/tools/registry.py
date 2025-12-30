"""工具注册表

管理所有Agent工具的注册和发现
"""

from typing import Dict, List, Optional
from loguru import logger

from .base import BaseTool
from .function_tool import FunctionTool
from .handoff_tool import HandoffTool


class ToolRegistry:
    """工具注册表
    
    管理所有可用工具的注册、发现和获取
    """

    def __init__(self):
        """初始化工具注册表"""
        self._tools: Dict[str, BaseTool] = {}  # name -> tool
        self._tools_by_type: Dict[str, List[BaseTool]] = {}  # type -> tools
        self._agent_assignments: Dict[str, List[str]] = {}  # agent_id -> tool names

    def register_tool(
        self,
        tool: BaseTool,
        agent_id: Optional[str] = None,
    ):
        """注册工具
        
        Args:
            tool: 工具实例
            agent_id: Agent标识符（可选）
        """
        tool_name = tool.name
        
        # 检查工具名称是否已存在
        if tool_name in self._tools:
            logger.warning(f"工具 {tool_name} 已存在，将被覆盖")
        
        # 注册工具
        self._tools[tool_name] = tool
        
        # 按类型分类
        tool_type = tool.__class__.__name__
        if tool_type not in self._tools_by_type:
            self._tools_by_type[tool_type] = []
        
        if tool not in self._tools_by_type[tool_type]:
            self._tools_by_type[tool_type].append(tool)
        
        # 分配给Agent
        if agent_id and agent_id not in self._agent_assignments:
            self._agent_assignments[agent_id] = []
        
        if agent_id:
            self._agent_assignments[agent_id].append(tool_name)
        
        logger.info(f"已注册工具: {tool_name} ({tool_type})")

    def unregister_tool(self, tool_name: str, agent_id: Optional[str] = None):
        """注销工具
        
        Args:
            tool_name: 工具名称
            agent_id: Agent标识符（可选）
        """
        if tool_name not in self._tools:
            logger.warning(f"工具 {tool_name} 不存在")
            return False
        
        tool = self._tools[tool_name]
        tool_type = tool.__class__.__name__
        
        # 从类型列表中移除
        if tool in self._tools_by_type.get(tool_type, []):
            self._tools_by_type[tool_type].remove(tool)
        
        # 从工具字典中移除
        del self._tools[tool_name]
        
        # 从Agent分配中移除
        if agent_id:
            if agent_id in self._agent_assignments:
                if tool_name in self._agent_assignments[agent_id]:
                    self._agent_assignments[agent_id].remove(tool_name)
        
        logger.info(f"已注销工具: {tool_name}")
        return True

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """获取工具
        
        Args:
            tool_name: 工具名称
            
        Returns:
            工具实例，如果不存在则返回 None
        """
        return self._tools.get(tool_name)

    def get_tools_by_type(self, tool_type: str) -> List[BaseTool]:
        """按类型获取工具列表
        
        Args:
            tool_type: 工具类型
            
        Returns:
            工具列表
        """
        return self._tools_by_type.get(tool_type, [])

    def get_all_tools(self) -> List[BaseTool]:
        """获取所有工具
        
        Returns:
            所有工具列表
        """
        return list(self._tools.values())

    def get_tools_for_agent(self, agent_id: str) -> List[BaseTool]:
        """获取Agent可用的工具
        
        Args:
            agent_id: Agent标识符
            
        Returns:
            工具列表
        """
        tool_names = self._agent_assignments.get(agent_id, [])
        tools = []
        
        for tool_name in tool_names:
            tool = self.get_tool(tool_name)
            if tool:
                tools.append(tool)
        
        return tools

    def list_tools(self) -> Dict[str, Dict[str, Any]]:
        """列出所有工具及其信息
        
        Returns:
            工具字典列表
        """
        tools_info = []
        
        for tool in self.get_all_tools():
            info = {
                "name": tool.name,
                "type": tool.__class__.__name__,
                "description": tool.description,
                "parameters_schema": tool.parameters_schema,
            }
            tools_info.append(info)
        
        return {"tools": tools_info}

    def assign_to_agent(self, agent_id: str, tool_names: List[str]) -> bool:
        """分配工具给Agent
        
        Args:
            agent_id: Agent标识符
            tool_names: 工具名称列表
            
        Returns:
            是否分配成功
        """
        # 验证工具是否存在
        for tool_name in tool_names:
            if tool_name not in self._tools:
                logger.error(f"工具 {tool_name} 不存在")
                return False
        
        # 分配工具
        if agent_id not in self._agent_assignments:
            self._agent_assignments[agent_id] = []
        
        self._agent_assignments[agent_id].extend(tool_names)
        
        logger.info(f"已将 {len(tool_names)} 个工具分配给Agent {agent_id}")
        return True

    def remove_from_agent(self, agent_id: str, tool_name: str) -> bool:
        """从Agent移除工具
        
        Args:
            agent_id: Agent标识符
            tool_name: 工具名称
            
        Returns:
            是否移除成功
        """
        if agent_id not in self._agent_assignments:
            logger.warning(f"Agent {agent_id} 没有分配的工具")
            return False
        
        if tool_name in self._agent_assignments[agent_id]:
            self._agent_assignments[agent_id].remove(tool_name)
            logger.info(f"已从Agent {agent_id} 移除工具 {tool_name}")
            return True
        
        logger.warning(f"工具 {tool_name} 未分配给Agent {agent_id}")
        return False

    def find_tools_by_keywords(self, keywords: str, top_k: int = 5) -> List[BaseTool]:
        """按关键词搜索工具
        
        Args:
            keywords: 搜索关键词
            top_k: 返回前 K 个结果
            
        Returns:
            工具列表
        """
        keywords_lower = keywords.lower()
        matched_tools = []
        
        for tool in self.get_all_tools():
            # 搜索工具名称
            if keywords_lower in tool.name.lower():
                if tool not in matched_tools:
                    matched_tools.append(tool)
                    if len(matched_tools) >= top_k:
                        break
            
            # 搜索工具描述
            if len(matched_tools) < top_k:
                for tool in self.get_all_tools():
                    if tool.description and keywords_lower in tool.description.lower():
                        if tool not in matched_tools:
                            matched_tools.append(tool)
                            if len(matched_tools) >= top_k:
                                break
        
        return matched_tools[:top_k]

    def get_tool_count(self) -> int:
        """获取工具总数
        
        Returns:
            工具总数
        """
        return len(self._tools)

    def get_agent_count(self) -> int:
        """获取Agent总数
        
        Returns:
            Agent总数
        """
        return len(self._agent_assignments)


# 创建全局工具注册表实例
tool_registry = ToolRegistry()