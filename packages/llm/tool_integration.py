"""LLM 工具集成模块

将知识库检索结果和工具调用功能整合到 LLM 提示词中
"""

from typing import Dict, List, Optional, Any
from loguru import logger

from ..agent.base import ToolRegistry, ToolDefinition, ToolCall


class LLMToolIntegration:
    """LLM 工具集成器"""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        config: Dict[str, Any] = None
    ):
        """初始化工具集成器

        Args:
            tool_registry: 工具注册表
            config: 配置字典
        """
        self.tool_registry = tool_registry
        self.config = config or {}

        # 注册内置工具
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """注册内置工具"""
        # 网页搜索工具
        self.tool_registry.register_tool(ToolDefinition(
            name="web_search",
            category="search",
            description="在网络上搜索信息并返回结果",
            function=self._web_search,
            enabled=True
        ))

        # 文件读取工具
        self.tool_registry.register_tool(ToolDefinition(
            name="read_file",
            category="file",
            description="读取指定路径的文件内容",
            function=self._read_file,
            enabled=True,
            requires_permission=True,
            permission_level="admin"
        ))

        # 计算器工具
        self.tool_registry.register_tool(ToolDefinition(
            name="calculator",
            category="system",
            description="执行数学计算",
            function=self._calculator,
            enabled=True
        ))

        logger.info(f"已注册 {len(self.tool_registry.list_tools())} 个内置工具")

    async def _web_search(self, query: str) -> str:
        """网页搜索工具（示例实现）"""
        logger.info(f"执行网页搜索: {query}")
        return f"搜索结果：关于 '{query}' 的信息..."

    async def _read_file(self, file_path: str) -> str:
        """文件读取工具"""
        logger.info(f"读取文件: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content[:1000]  # 限制返回长度
        except Exception as e:
            logger.error(f"读取文件失败: {e}")
            return f"读取文件失败: {e}"

    async def _calculator(self, expression: str) -> str:
        """计算器工具"""
        logger.info(f"执行计算: {expression}")
        try:
            # 安全计算
            result = eval(expression)
            return str(result)
        except Exception as e:
            logger.error(f"计算失败: {e}")
            return f"计算失败: {e}"

    async def build_rag_enhanced_prompt(
        self,
        user_message: str,
        rag_context: Optional[Dict[str, Any]] = None,
        available_tools: List[str] = None
    ) -> str:
        """构建 RAG 增强的提示词

        Args:
            user_message: 用户消息
            rag_context: RAG 上下文
            available_tools: 可用工具列表

        Returns:
            增强后的提示词
        """
        prompt_parts = [f"用户消息: {user_message}"]

        # 添加 RAG 上下文
        if rag_context:
            context = rag_context.get("unknown", {})
            docs = context.get("results", [])
            if docs:
                prompt_parts.append("以下是来自知识库的相关信息：")
                for i, doc in enumerate(docs[:3]):  # 最多显示 3 个文档
                    doc.get("id", "")
                    doc_title = doc.get("title", "")
                    doc_content = doc.get("content", "")
                    prompt_parts.append(f"  {i}. {doc_title}")
                    if len(doc_content) > 200:
                        doc_content = doc_content[:200] + "..."
                    prompt_parts.append(f"  {doc_content}")
                prompt_parts.append(f"总计 {len(docs)} 个相关文档")

        # 添加可用工具信息
        if available_tools:
            tool_info = ", ".join(available_tools)
            prompt_parts.append(f"可用的工具: {tool_info}")

        prompt_parts.append("\n\n请根据以上上下文和工具，回答用户的问题。")

        return "\n".join(prompt_parts)

    async def execute_tool_call(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user_message: str
    ) -> ToolCall:
        """执行工具调用

        Args:
            tool_name: 工具名称
            parameters: 参数
            user_message: 用户消息

        Returns:
            工具调用结果
        """
        tool = self.tool_registry.get_tool(tool_name)

        if not tool:
            result_str = f"工具 {tool_name} 不存在"
        elif not tool.enabled:
            result_str = f"工具 {tool_name} 未启用"
        elif tool.requires_permission and not self._check_permission(tool.permission_level, None):
            result_str = f"需要 {tool.permission_level} 权限级别"
        else:
            try:
                result = tool.function(**parameters)
                result_str = f"工具 {tool_name} 执行成功，结果: {str(result)}"
            except Exception as e:
                logger.error(f"调用工具 {tool_name} 失败: {e}")
                result_str = f"工具 {tool_name} 失败，错误: {str(e)}"

        return ToolCall(
            tool_name=tool_name,
            parameters=parameters,
            result=result_str,
            success=tool.enabled and result is not None,
            error=None if tool.enabled and result is not None else result_str
        )

    def _check_permission(self, required_level: str, user_level: Optional[str] = None) -> bool:
        """检查权限

        Args:
            required_level: 需要的权限级别
            user_level: 用户权限级别

        Returns:
            是否有权限
        """
        # 权限级别从低到高：user < moderator < admin < system
        levels = {
            "user": 0,
            "moderator": 1,
            "admin": 2,
            "system": 3
        }

        if user_level is None:
            user_level = "user"

        current_level = levels.get(user_level, 0)
        return current_level >= levels.get(required_level, 0)

    def get_available_tools(self, user_level: str = "user") -> List[ToolDefinition]:
        """获取可用的工具列表

        Args:
            user_level: 用户权限级别

        Returns:
            工具列表
        """
        tools = []
        for tool in self.tool_registry.list_tools():
            if tool.requires_permission:
                required_level = tool.permission_level
                # 系统工具总是可用
                if required_level == "system":
                    tools.append(tool)
                # 检查用户权限
                levels = {
                    "user": 0,
                    "moderator": 1,
                    "admin": 2,
                    "system": 3
                }
                current_level = levels.get(user_level, 0)
                if current_level >= levels.get(required_level, 0):
                    tools.append(tool)
            elif not tool.requires_permission:
                tools.append(tool)
        return tools

    def format_tools_for_llm(self, tools: List[ToolDefinition]) -> str:
        """格式化工具描述供 LLM 使用

        Args:
            tools: 工具列表

        Returns:
            格式化后的工具描述
        """
        if not tools:
            return ""

        tool_descriptions = []
        for tool in tools:
            desc = f"- {tool.name}: {tool.description}"
            if tool.enabled:
                desc += " (已启用)"
            else:
                desc += " (已禁用)"
            if tool.requires_permission:
                desc += f" [权限: {tool.permission_level}]"
            tool_descriptions.append(desc)

        return "可用工具:\n" + "\n".join(tool_descriptions)
