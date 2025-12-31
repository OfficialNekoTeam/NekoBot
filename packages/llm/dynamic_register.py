"""动态注册管理模块

该模块负责管理LLM提供商和平台适配器的动态注册，根据配置文件动态加载和注册组件，减少内存占用。
"""

import importlib
import json
import os
from typing import Dict, Any, Optional, Type
from loguru import logger
from pathlib import Path


class DynamicRegisterManager:
    """动态注册管理器
    
    负责根据配置文件动态加载和注册LLM提供商和平台适配器。
    """
    
    def __init__(self):
        """初始化动态注册管理器"""
        self.llm_providers: Dict[str, Type] = {}
        self.platform_adapters: Dict[str, Type] = {}
        
        # 配置文件路径
        self.data_dir = Path("data")
        self.llm_providers_config_path = self.data_dir / "llm_providers.json"
        self.platforms_config_path = self.data_dir / "platforms_sources.json"
        
        # 动态导入映射
        self.llm_provider_module_map = {
            "openai": "packages.llm.sources.openai_provider",
            "claude": "packages.llm.sources.claude_provider",
            "gemini": "packages.llm.sources.gemini_provider",
            "dashscope": "packages.llm.sources.dashscope_provider",
            "deepseek": "packages.llm.sources.deepseek_provider",
            "moonshot": "packages.llm.sources.moonshot_provider",
            "zhipu": "packages.llm.sources.zhipu_provider",
            "glm": "packages.llm.sources.glm_provider",
            "ollama": "packages.llm.sources.ollama_provider",
            "lm_studio": "packages.llm.sources.lm_studio_provider",
            "openai_compatible": "packages.llm.sources.openai_compatible_provider",
        }
        
        self.platform_adapter_module_map = {
            "aiocqhttp": "packages.platform.sources.aiocqhttp.aiocqhttp_platform",
            "discord": "packages.platform.sources.discord.discord_platform",
            "telegram": "packages.platform.sources.telegram.telegram_platform",
            "lark": "packages.platform.sources.lark.lark_platform",
            "kook": "packages.platform.sources.kook.kook_platform",
            "qqchannel": "packages.platform.sources.qqchannel.qqchannel_platform",
            "slack": "packages.platform.sources.slack.slack_platform",
            "wecom": "packages.platform.sources.wecom.wecom_platform",
        }
    
    def load_configs(self) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """加载配置文件
        
        Returns:
            tuple: (llm_providers_config, platforms_config)
        """
        # 加载LLM提供商配置
        llm_providers_config = {}
        if self.llm_providers_config_path.exists():
            with open(self.llm_providers_config_path, "r", encoding="utf-8") as f:
                llm_providers_config = json.load(f)
        
        # 加载平台适配器配置
        platforms_config = {}
        if self.platforms_config_path.exists():
            with open(self.platforms_config_path, "r", encoding="utf-8") as f:
                platforms_config = json.load(f)
        
        return llm_providers_config, platforms_config
    
    def dynamic_register_llm_providers(self) -> Dict[str, Type]:
        """动态注册LLM提供商
        
        Returns:
            Dict[str, Type]: 注册的LLM提供商字典
        """
        logger.info("开始动态注册LLM提供商...")
        
        # 加载配置
        llm_providers_config, _ = self.load_configs()
        
        # 动态注册启用的LLM提供商
        registered_providers = {}
        
        for provider_id, provider_config in llm_providers_config.items():
            if provider_config.get("enabled", False):
                provider_type = provider_config.get("type", provider_id)
                
                try:
                    # 动态导入模块
                    module_name = self.llm_provider_module_map.get(provider_type)
                    if not module_name:
                        logger.warning(f"未找到LLM提供商 {provider_type} 的模块映射，跳过注册")
                        continue
                    
                    logger.debug(f"动态导入LLM提供商模块: {module_name}")
                    module = importlib.import_module(module_name)
                    
                    # 直接从模块中获取提供商类（假设类名是ProviderType+Provider）
                    class_name = provider_type.capitalize() + "Provider"
                    if class_name not in module.__dict__:
                        # 尝试其他命名方式
                        class_name = provider_type.replace("_", "").capitalize() + "Provider"
                    
                    if class_name in module.__dict__:
                        provider_cls = module.__dict__[class_name]
                        registered_providers[provider_type] = provider_cls
                        logger.info(f"成功注册LLM提供商: {provider_type}")
                    else:
                        # 遍历模块中的所有类，找到继承自BaseLLMProvider的类
                        from .base import BaseLLMProvider
                        found = False
                        for name, cls in module.__dict__.items():
                            if isinstance(cls, type) and issubclass(cls, BaseLLMProvider) and cls != BaseLLMProvider:
                                registered_providers[provider_type] = cls
                                logger.info(f"成功注册LLM提供商: {provider_type}，使用类: {name}")
                                found = True
                                break
                        
                        if not found:
                            logger.warning(f"未找到LLM提供商类: {provider_type}")
                        
                except Exception as e:
                    logger.error(f"动态注册LLM提供商 {provider_type} 失败: {e}")
        
        # 更新全局变量
        from .register import llm_provider_cls_map
        llm_provider_cls_map.clear()
        llm_provider_cls_map.update(registered_providers)
        
        logger.info(f"LLM提供商动态注册完成，共注册 {len(registered_providers)} 个提供商")
        self.llm_providers = registered_providers
        return registered_providers
    
    def dynamic_register_platform_adapters(self) -> Dict[str, Type]:
        """动态注册平台适配器
        
        Returns:
            Dict[str, Type]: 注册的平台适配器字典
        """
        logger.info("开始动态注册平台适配器...")
        
        # 加载配置
        _, platforms_config = self.load_configs()
        
        # 动态注册启用的平台适配器
        registered_adapters = {}
        
        for adapter_id, adapter_config in platforms_config.items():
            if adapter_config.get("enable", False):
                adapter_type = adapter_config.get("type", adapter_id)
                
                try:
                    # 动态导入模块
                    module_name = self.platform_adapter_module_map.get(adapter_type)
                    if not module_name:
                        logger.warning(f"未找到平台适配器 {adapter_type} 的模块映射，跳过注册")
                        continue
                    
                    logger.debug(f"动态导入平台适配器模块: {module_name}")
                    module = importlib.import_module(module_name)
                    
                    # 直接从模块中获取适配器类（假设类名是AdapterType+Platform）
                    class_name = adapter_type.capitalize() + "Platform"
                    if class_name not in module.__dict__:
                        # 尝试其他命名方式
                        class_name = adapter_type.replace("_", "").capitalize() + "Platform"
                    
                    if class_name in module.__dict__:
                        adapter_cls = module.__dict__[class_name]
                        registered_adapters[adapter_type] = adapter_cls
                        logger.info(f"成功注册平台适配器: {adapter_type}")
                    else:
                        # 遍历模块中的所有类，找到继承自BasePlatform的类
                        from packages.platform.base import BasePlatform
                        found = False
                        for name, cls in module.__dict__.items():
                            if isinstance(cls, type) and issubclass(cls, BasePlatform) and cls != BasePlatform:
                                registered_adapters[adapter_type] = cls
                                logger.info(f"成功注册平台适配器: {adapter_type}，使用类: {name}")
                                found = True
                                break
                        
                        if not found:
                            logger.warning(f"未找到平台适配器类: {adapter_type}")
                        
                except Exception as e:
                    logger.error(f"动态注册平台适配器 {adapter_type} 失败: {e}")
        
        # 更新全局变量
        from packages.platform.register import platform_cls_map
        platform_cls_map.clear()
        platform_cls_map.update(registered_adapters)
        
        logger.info(f"平台适配器动态注册完成，共注册 {len(registered_adapters)} 个适配器")
        self.platform_adapters = registered_adapters
        return registered_adapters
    
    def get_llm_provider(self, provider_type: str) -> Optional[Type]:
        """获取指定类型的LLM提供商
        
        Args:
            provider_type: LLM提供商类型
            
        Returns:
            Optional[Type]: LLM提供商类
        """
        return self.llm_providers.get(provider_type)
    
    def get_platform_adapter(self, adapter_type: str) -> Optional[Type]:
        """获取指定类型的平台适配器
        
        Args:
            adapter_type: 平台适配器类型
            
        Returns:
            Optional[Type]: 平台适配器类
        """
        return self.platform_adapters.get(adapter_type)
    
    def get_all_llm_providers(self) -> Dict[str, Type]:
        """获取所有注册的LLM提供商
        
        Returns:
            Dict[str, Type]: 所有注册的LLM提供商
        """
        return self.llm_providers
    
    def get_all_platform_adapters(self) -> Dict[str, Type]:
        """获取所有注册的平台适配器
        
        Returns:
            Dict[str, Type]: 所有注册的平台适配器
        """
        return self.platform_adapters


# 创建全局动态注册管理器实例
dynamic_register_manager = DynamicRegisterManager()