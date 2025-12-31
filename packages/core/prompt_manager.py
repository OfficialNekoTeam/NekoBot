"""提示词管理器

用于管理和加载系统提示词、工具提示词和人格
"""

from typing import Dict, Optional, List
from loguru import logger

from .database import db_manager


class PromptManager:
    """提示词管理器"""

    def __init__(self):
        """初始化提示词管理器"""
        self.system_prompts: Dict[str, str] = {}
        self.tool_prompts: Dict[str, str] = {}
        self.personalities: Dict[str, Dict[str, any]] = {}
        self.enabled_personalities: List[Dict[str, any]] = []
        
        # 系统提示词默认值
        self.default_system_prompts = {
            "default": "你是一个智能聊天机器人助手，友好、专业地回答用户的问题。",
        }
        
        # 工具提示词默认值
        self.default_tool_prompts = {
            "get_user_info": "获取当前对话用户的详细信息，包括QQ号、昵称、显示名称、消息类型等",
            "get_group_info": "获取当前群组的详细信息，包括群组ID、群组名称等（仅在群聊时可用）",
            "list_tools": "列出所有可用的工具及其详细描述，包括工具名称、功能、类别和状态",
        }
        
        # 人格默认值
        self.default_personalities = {
            "default": {
                "name": "default",
                "prompt": "你是一个友好、专业的AI助手，能够帮助用户解答各种问题。",
                "description": "默认人格",
                "enabled": True
            }
        }
        
        self.load_all_prompts()
    
    def load_all_prompts(self):
        """加载所有提示词"""
        self._load_system_prompts()
        self._load_tool_prompts()
        self._load_personalities()
        logger.info("所有提示词加载完成")
    
    def _load_system_prompts(self):
        """加载系统提示词"""
        # 加载数据库中的系统提示词
        db_system_prompts = db_manager.get_all_system_prompts()
        for prompt in db_system_prompts:
            self.system_prompts[prompt["name"]] = prompt["prompt"]
        
        # 确保默认提示词存在
        for name, default_prompt in self.default_system_prompts.items():
            if name not in self.system_prompts:
                db_manager.create_system_prompt(name, default_prompt, f"默认系统提示词: {name}")
                self.system_prompts[name] = default_prompt
        
        logger.debug(f"加载了 {len(self.system_prompts)} 个系统提示词")
    
    def _load_tool_prompts(self):
        """加载工具提示词"""
        # 加载数据库中的工具提示词
        db_tool_prompts = db_manager.get_all_tool_prompts()
        for prompt in db_tool_prompts:
            self.tool_prompts[prompt["tool_name"]] = prompt["prompt"]
        
        # 确保默认工具提示词存在
        for tool_name, default_prompt in self.default_tool_prompts.items():
            if tool_name not in self.tool_prompts:
                db_manager.create_tool_prompt(tool_name, default_prompt, f"默认工具提示词: {tool_name}")
                self.tool_prompts[tool_name] = default_prompt
        
        logger.debug(f"加载了 {len(self.tool_prompts)} 个工具提示词")
    
    def _load_personalities(self):
        """加载人格"""
        # 加载数据库中的人格
        db_personalities = db_manager.get_all_personalities()
        for personality in db_personalities:
            self.personalities[personality["name"]] = personality
        
        # 确保默认人格存在
        for name, default_personality in self.default_personalities.items():
            if name not in self.personalities:
                db_manager.create_personality(
                    name=name,
                    prompt=default_personality["prompt"],
                    description=default_personality["description"],
                    enabled=default_personality["enabled"]
                )
                self.personalities[name] = db_manager.get_personality(name)
        
        # 更新启用的人格列表
        self.enabled_personalities = [p for p in self.personalities.values() if p["enabled"]]
        logger.debug(f"加载了 {len(self.personalities)} 个人格，其中 {len(self.enabled_personalities)} 个已启用")
    
    def get_system_prompt(self, name: str = "default") -> str:
        """获取系统提示词
        
        Args:
            name: 提示词名称，默认为 "default"
            
        Returns:
            系统提示词内容
        """
        return self.system_prompts.get(name, self.default_system_prompts["default"])
    
    def get_tool_prompt(self, tool_name: str) -> str:
        """获取工具提示词
        
        Args:
            tool_name: 工具名称
            
        Returns:
            工具提示词内容
        """
        return self.tool_prompts.get(tool_name, self.default_tool_prompts.get(tool_name, ""))
    
    def get_enabled_personalities(self) -> List[Dict[str, any]]:
        """获取所有启用的人格
        
        Returns:
            启用的人格列表
        """
        return self.enabled_personalities
    
    def get_personality(self, name: str = "default") -> Optional[Dict[str, any]]:
        """获取人格
        
        Args:
            name: 人格名称，默认为 "default"
            
        Returns:
            人格信息，如果不存在则返回None
        """
        return self.personalities.get(name)
    
    def add_system_prompt(self, name: str, prompt: str, description: str = "") -> bool:
        """添加系统提示词
        
        Args:
            name: 提示词名称
            prompt: 提示词内容
            description: 描述
            
        Returns:
            是否添加成功
        """
        success = db_manager.create_system_prompt(name, prompt, description)
        if success:
            self.system_prompts[name] = prompt
            logger.info(f"添加系统提示词成功: {name}")
        return success
    
    def update_system_prompt(self, name: str, prompt: str, description: str = "") -> bool:
        """更新系统提示词
        
        Args:
            name: 提示词名称
            prompt: 新的提示词内容
            description: 新的描述
            
        Returns:
            是否更新成功
        """
        success = db_manager.update_system_prompt(name, prompt, description)
        if success:
            self.system_prompts[name] = prompt
            logger.info(f"更新系统提示词成功: {name}")
        return success
    
    def delete_system_prompt(self, name: str) -> bool:
        """删除系统提示词
        
        Args:
            name: 提示词名称
            
        Returns:
            是否删除成功
        """
        # 不能删除默认提示词
        if name == "default":
            logger.warning("不能删除默认系统提示词")
            return False
        
        success = db_manager.delete_system_prompt(name)
        if success:
            self.system_prompts.pop(name, None)
            logger.info(f"删除系统提示词成功: {name}")
        return success
    
    def add_tool_prompt(self, tool_name: str, prompt: str, description: str = "") -> bool:
        """添加工具提示词
        
        Args:
            tool_name: 工具名称
            prompt: 提示词内容
            description: 描述
            
        Returns:
            是否添加成功
        """
        success = db_manager.create_tool_prompt(tool_name, prompt, description)
        if success:
            self.tool_prompts[tool_name] = prompt
            logger.info(f"添加工具提示词成功: {tool_name}")
        return success
    
    def update_tool_prompt(self, tool_name: str, prompt: str, description: str = "") -> bool:
        """更新工具提示词
        
        Args:
            tool_name: 工具名称
            prompt: 新的提示词内容
            description: 新的描述
            
        Returns:
            是否更新成功
        """
        success = db_manager.update_tool_prompt(tool_name, prompt, description)
        if success:
            self.tool_prompts[tool_name] = prompt
            logger.info(f"更新工具提示词成功: {tool_name}")
        return success
    
    def delete_tool_prompt(self, tool_name: str) -> bool:
        """删除工具提示词
        
        Args:
            tool_name: 工具名称
            
        Returns:
            是否删除成功
        """
        success = db_manager.delete_tool_prompt(tool_name)
        if success:
            self.tool_prompts.pop(tool_name, None)
            logger.info(f"删除工具提示词成功: {tool_name}")
        return success
    
    def add_personality(self, name: str, prompt: str, description: str = "", enabled: bool = True) -> bool:
        """添加人格
        
        Args:
            name: 人格名称
            prompt: 人格提示词内容
            description: 描述
            enabled: 是否启用
            
        Returns:
            是否添加成功
        """
        success = db_manager.create_personality(name, prompt, description, enabled)
        if success:
            self.personalities[name] = db_manager.get_personality(name)
            if enabled:
                self.enabled_personalities.append(self.personalities[name])
            logger.info(f"添加人格成功: {name}")
        return success
    
    def update_personality(self, name: str, prompt: Optional[str] = None, description: Optional[str] = None, enabled: Optional[bool] = None) -> bool:
        """更新人格
        
        Args:
            name: 人格名称
            prompt: 新的人格提示词内容
            description: 新的描述
            enabled: 是否启用
            
        Returns:
            是否更新成功
        """
        # 获取旧人格信息
        old_personality = self.personalities.get(name)
        if not old_personality:
            logger.warning(f"人格 {name} 不存在")
            return False
        
        # 使用旧值填充缺失的参数
        if prompt is None:
            prompt = old_personality["prompt"]
        if description is None:
            description = old_personality["description"]
        if enabled is None:
            enabled = old_personality["enabled"]
        
        success = db_manager.update_personality(name, prompt, description, enabled)
        if success:
            # 更新内存中的人格信息
            self.personalities[name] = db_manager.get_personality(name)
            # 更新启用的人格列表
            self._load_personalities()
            logger.info(f"更新人格成功: {name}")
        return success
    
    def delete_personality(self, name: str) -> bool:
        """删除人格
        
        Args:
            name: 人格名称
            
        Returns:
            是否删除成功
        """
        # 不能删除默认人格
        if name == "default":
            logger.warning("不能删除默认人格")
            return False
        
        success = db_manager.delete_personality(name)
        if success:
            self.personalities.pop(name, None)
            # 更新启用的人格列表
            self._load_personalities()
            logger.info(f"删除人格成功: {name}")
        return success


# 显式导出的符号
__all__ = [
    "PromptManager",
    "prompt_manager"
]

# 创建全局提示词管理器实例
prompt_manager = PromptManager()
