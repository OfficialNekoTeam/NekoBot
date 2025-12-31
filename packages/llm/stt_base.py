"""STT（语音转文本）Provider 基类

参考 AstrBot 的 STT Provider 实现
"""

import abc
from typing import Optional



class STTProvider(abc.ABC):
    """语音转文本服务提供商基类"""

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
    async def get_text(self, audio_url: str) -> str:
        """获取音频的文本

        Args:
            audio_url: 音频文件路径或 URL

        Returns:
            识别出的文本
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
        import os

        sample_audio_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "samples",
            "stt_health_check.wav",
        )

        if not os.path.exists(sample_audio_path):
            raise FileNotFoundError(f"测试音频文件不存在: {sample_audio_path}")

        await self.get_text(sample_audio_path)
