"""TTS（文本转语音）Provider 基类

参考 AstrBot 的 TTS Provider 实现
"""

import abc
from typing import Optional


class TTSProvider(abc.ABC):
    """文本转语音服务提供商基类"""

    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__()
        self.provider_config = provider_config
        self.provider_settings = provider_settings

    def get_current_key(self) -> str:
        """获取当前 API Key"""
        keys = self.provider_config.get("api_key", [""])
        if keys:
            return keys[0]
        return ""

    def get_keys(self) -> list[str]:
        """获取所有 API Key"""
        keys = self.provider_config.get("api_key", [""])
        return keys or [""]

    @abc.abstractmethod
    async def get_audio(self, text: str) -> str:
        """获取文本的音频，返回音频文件路径

        Args:
            text: 要转换的文本

        Returns:
            音频文件路径
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_models(self) -> list[str]:
        """获取支持的模型列表"""
        raise NotImplementedError

    async def test(self) -> None:
        """测试服务提供商是否可用

        Raises:
            Exception: 如果服务提供商不可用
        """
        await self.get_audio("hi")
