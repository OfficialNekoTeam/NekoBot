"""Agent示例

提供示例Agent实现和内置工具
"""

from ..base import BaseAgent
from ..tools import FunctionTool
from typing import Dict, Any, Optional


class SimpleAssistantAgent(BaseAgent):
    """简单助手Agent
    
    提供基本的对话响应功能
    """

    def __init__(self):
        """初始化简单助手Agent"""
        pass

    async def process_message(
        self,
        message: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[str]:
        """处理消息
        
        Args:
            message: 消息数据
            context: 对话上下文
            
        Returns:
            Agent响应
        """
        # 获取消息内容
        content = message.get("content", "")
        user_id = message.get("user_id", "unknown")
        
        # 简单的响应逻辑
        if "你好" in content or "hi" in content.lower():
            return f"你好，{user_id}！我是NekoBot助手，有什么可以帮助您的吗？"
        
        elif "再见" in content or "bye" in content.lower():
            return f"再见，{user_id}！祝您有美好的一天！"
        
        elif "时间" in content or "几点" in content.lower():
            import datetime
            now = datetime.datetime.now().strftime("%H:%M:%S")
            return f"现在是{now}"
        
        else:
            # 默认响应
            return f"我收到您的消息了：{content}"

    async def call_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> Any:
        """调用工具（简单助手不支持工具调用）
        
        Args:
            tool_name: 工具名称
            parameters: 工具参数
            
        Returns:
            工具执行结果
        """
        return {
            "error": f"简单助手Agent不支持工具调用",
            "tool": tool_name,
        }

    async def get_context(self, session_id: str) -> Dict[str, Any]:
        """获取对话上下文（简单实现，不存储历史）
        
        Args:
            session_id: 会话ID
            
        Returns:
            空的上下文字典
        """
        return {"session_id": session_id}

    async def update_context(
        self,
        session_id: str,
        context: Dict[str, Any],
    ) -> bool:
        """更新对话上下文（简单实现，不存储）
        
        Args:
            session_id: 会话ID
            context: 新的上下文
            
        Returns:
            是否更新成功
        """
        return True


# 创建示例工具
def get_current_time():
    """获取当前时间"""
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def search_knowledge_base(query: str, top_k: int = 5):
    """搜索知识库（示例函数）
    
    Args:
        query: 查询文本
        top_k: 返回前 K 个结果
        
    Returns:
        搜索结果
    """
    # 简化实现，返回示例数据
    return {
        "query": query,
        "results": [
            f"示例结果 1: {query}的答案",
            f"示例结果 2: {query}的更多信息",
        ][:top_k],
    }


# 创建工具实例
time_tool = FunctionTool.from_function(
    func=get_current_time,
    name="get_time",
    description="获取当前时间",
)

kb_search_tool = FunctionTool.from_function(
    func=search_knowledge_base,
    name="search_kb",
    description="搜索知识库",
)