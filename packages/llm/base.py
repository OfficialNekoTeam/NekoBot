"""LLM Provider 基类

提供 LLM 服务提供商的抽象接口
"""

import abc

from .register import LLMProviderMetaData, llm_provider_cls_map
from .entities import LLMResponse


class BaseLLMProvider(abc.ABC):
    """LLM 服务提供商基类"""

    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__()
        self.provider_config = provider_config
        self.provider_settings = provider_settings
        self.model_name = provider_config.get("model", "")

    def set_model(self, model_name: str) -> None:
        """设置当前模型名称"""
        self.model_name = model_name

    def get_model(self) -> str:
        """获取当前模型名称"""
        return self.model_name

    def meta(self) -> LLMProviderMetaData:
        """获取服务提供商元数据"""
        provider_type_name = self.provider_config.get("type", "unknown")
        meta_data = llm_provider_cls_map.get(provider_type_name)
        if not meta_data:
            raise ValueError(f"Provider type {provider_type_name} not registered")
        return LLMProviderMetaData(
            id=self.provider_config.get("id", "default"),
            model=self.get_model(),
            type=provider_type_name,
            desc=meta_data.desc,
            provider_type=meta_data.provider_type,
            cls_type=type(self),
            default_config_tmpl=meta_data.default_config_tmpl,
            provider_display_name=meta_data.provider_display_name,
        )

    @abc.abstractmethod
    def get_current_key(self) -> str:
        """获取当前 API Key"""
        raise NotImplementedError

    def get_keys(self) -> list[str]:
        """获取所有 API Key"""
        keys = self.provider_config.get("api_key", [""])
        return keys or [""]

    @abc.abstractmethod
    def set_key(self, key: str) -> None:
        """设置 API Key"""
        raise NotImplementedError

    @abc.abstractmethod
    async def get_models(self) -> list[str]:
        """获取支持的模型列表"""
        raise NotImplementedError

    @abc.abstractmethod
    async def text_chat(
        self,
        prompt: str | None = None,
        session_id: str | None = None,
        image_urls: list[str] | None = None,
        contexts: list[dict] | None = None,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs,
    ) -> LLMResponse:
        """获取 LLM 的文本对话结果

        Args:
            prompt: 提示词
            session_id: 会话 ID
            image_urls: 图片 URL 列表
            contexts: 上下文
            system_prompt: 系统提示词
            model: 模型名称
            **kwargs: 其他参数

        Returns:
            LLMResponse 对象
        """
        raise NotImplementedError

    async def test(self, timeout: float = 45.0) -> None:
        """测试服务提供商是否可用

        Args:
            timeout: 超时时间（秒）

        Raises:
            Exception: 如果服务提供商不可用
        """
        import asyncio

        await asyncio.wait_for(
            self.text_chat(prompt="REPLY `PONG` ONLY"),
            timeout=timeout,
        )
