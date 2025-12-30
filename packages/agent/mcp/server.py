"""MCP服务器

提供简化的MCP协议服务器基础实现
"""

from typing import Dict, Any, Optional, Callable
from loguru import logger
import asyncio


class MCPServer:
    """MCP服务器
    
    用于处理MCP协议的请求和响应
    """

    def __init__(
        self,
        name: str = "nekobot_server",
        version: str = "2024-11-05",
    ):
        """初始化MCP服务器
        
        Args:
            name: 服务器名称
            version: 协议版本
        """
        self.name = name
        self.version = version
        self._tools: Dict[str, Callable] = {}  # tool name -> tool handler
        self._prompts: Dict[str, Dict[str, Any]] = {}  # tool name -> prompts
        self._resources: Dict[str, Any] = {}  # resource URI -> resource data
        self._running = False

    async def start(self) -> None:
        """启动MCP服务器"""
        self._running = True
        logger.info(f"MCP服务器 {self.name} (v{self.version}) 已启动")

    async def stop(self) -> None:
        """停止MCP服务器"""
        self._running = False
        logger.info(f"MCP服务器 {self.name} 已停止")

    def register_tool(self, tool_name: str, handler: Callable):
        """注册工具处理器
        
        Args:
            tool_name: 工具名称
            handler: 处理函数
        """
        self._tools[tool_name] = handler
        logger.debug(f"已注册MCP工具: {tool_name}")

    def set_tool_prompt(self, tool_name: str, prompt: Dict[str, Any]):
        """设置工具提示词
        
        Args:
            tool_name: 工具名称
            prompt: 提示词配置
        """
        self._prompts[tool_name] = prompt
        logger.debug(f"已设置工具 {tool_name} 的提示词")

    def register_resource(self, resource_uri: str, data: Any):
        """注册资源处理器
        
        Args:
            resource_uri: 资源URI
            data: 资源数据
        """
        self._resources[resource_uri] = data
        logger.debug(f"已注册资源: {resource_uri}")

    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """处理工具调用请求
        
        Args:
            tool_name: 工具名称
            arguments: 调用参数
            
        Returns:
            工具执行结果
        """
        if tool_name not in self._tools:
            logger.error(f"工具 {tool_name} 未注册")
            return {
                "toolCallId": tool_name,
                "result": {
                    "content": f"错误：工具 {tool_name} 未找到",
                    "isError": True,
                },
            }
        
        handler = self._tools[tool_name]
        
        try:
            # 执行工具
            result = await handler(arguments)
            
            logger.info(f"工具 {tool_name} 执行成功")
            return {
                "toolCallId": tool_name,
                "result": {
                    "content": result,
                    "isError": False,
                },
            }
        except Exception as e:
            logger.error(f"工具 {tool_name} 执行失败: {e}")
            return {
                "toolCallId": tool_name,
                "result": {
                    "content": f"执行失败: {str(e)}",
                    "isError": True,
                },
            }

    async def list_tools(self):
        """列出可用工具
        
        Returns:
            工具列表
        """
        if not self._running:
            logger.warning("MCP服务器未运行")
            return []
        
        tools = []
        for tool_name, handler in self._tools.items():
            tools.append({
                "name": tool_name,
                "description": handler.__doc__ if hasattr(handler, "__doc__") else tool_name,
            })
        
        logger.info(f"返回 {len(tools)} 个工具")
        return tools

    def get_server_info(self) -> Dict[str, Any]:
        """获取服务器信息
        
        Returns:
            服务器信息字典
        """
        return {
            "name": self.name,
            "version": self.version,
            "capabilities": [
                "tools",
                "resources",
            ],
            "protocolVersion": self.version,
            "instructions": "使用 tools/call 方法调用工具",
        }

    def is_running(self) -> bool:
        """检查服务器是否正在运行
        
        Returns:
            是否正在运行
        """
        return self._running


# 创建全局MCP服务器实例
mcp_server = MCPServer()