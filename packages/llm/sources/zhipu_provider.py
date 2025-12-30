"""智谱 AI LLM 提供商

支持 GLM-4 系列模型
"""

from collections.abc import AsyncGenerator
from typing import Optional

import zhipuai
from zhipuai import ZhipuAI

from loguru import logger

from ..base import BaseLLMProvider
from ..register import register_llm_provider, LLMProviderType
from ..entities import LLMResponse, TokenUsage


@register_llm_provider(
    provider_type_name="zhipu",
    desc="智谱 AI 提供商 (GLM-4 系列)",
    provider_type=LLMProviderType.CHAT_COMPLETION,
    default_config_tmpl={
        "type": "zhipu",
        "enable": False,
        "id": "zhipu",
        "model": "glm-4",
        "api_key": "",
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    provider_display_name="智谱 AI",
)
class ZhipuProvider(BaseLLMProvider):
    """智谱 AI LLM 提供商"""

    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__(provider_config, provider_settings)
        self.api_key = provider_config.get("api_key", "")
        self.max_tokens = provider_config.get("max_tokens", 4096)
        self.temperature = provider_config.get("temperature", 0.7)
        self._current_key_index = 0

        self._client: Optional[ZhipuAI] = None
        self._init_client()

    def _init_client(self) -> None:
        """初始化智谱 AI 客户端"""
        self._client = ZhipuAI(api_key=self.api_key)

    def get_current_key(self) -> str:
        """获取当前 API Key"""
        keys = self.get_keys()
        if keys and self._current_key_index < len(keys):
            return keys[self._current_key_index]
        return ""

    def set_key(self, key: str) -> None:
        """设置 API Key"""
        self.provider_config["api_key"] = [key]
        self.api_key = key
        self._init_client()

    async def initialize(self) -> None:
        """初始化提供商"""
        if not self.api_key:
            raise ValueError("智谱 AI API Key 未配置")

        self._client = self._init_client()
        logger.info("[ZhipuAI] 智谱 AI 提供商已初始化")

    def _build_messages(self, prompt: Optional[str], system_prompt: Optional[str],
                      contexts: Optional[list[dict]]) -> list[dict]:
        """构建消息列表"""
        messages = []

        # 添加系统提示词
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 添加上下文
        if contexts:
            messages.extend(contexts)

        # 添加用户消息
        if prompt:
            messages.append({"role": "user", "content": prompt})

        return messages

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
        """文本对话

        Args:
            prompt: 提示词
            session_id: 会话 ID
            image_urls: 图片 URL 列表（当前版本暂不支持）
            contexts: 上下文
            system_prompt: 系统提示词
            model: 模型名称
            **kwargs: 其他参数

        Returns:
            LLMResponse 对象
        """
        try:
            messages = self._build_messages(prompt, system_prompt, contexts)

            # 调用 API
            response = self._client.chat.completions.create(
                model=model or self.model_name,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            # 检查响应状态
            if not response.choices:
                raise Exception("API 返回的 choices 为空。")

            choice = response.choices[0]

            # 解析文本响应
            completion_text = ""
            if hasattr(choice.message, 'content') and choice.message.content:
                completion_text = choice.message.content

            # 解析使用情况
            usage = None
            if hasattr(response, 'usage') and response.usage:
                usage = TokenUsage(
                    input_other=response.usage.prompt_tokens,
                    output=response.usage.completion_tokens,
                )

            return LLMResponse(
                role="assistant",
                completion_text=completion_text,
                raw_completion=response,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"[ZhipuAI] 文本聊天失败: {e}")
            return LLMResponse(
                role="err",
                completion_text="",
            )

    async def text_chat_stream(
        self,
        prompt: str | None = None,
        session_id: str | None = None,
        image_urls: list[str] | None = None,
        contexts: list[dict] | None = None,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[LLMResponse, None]:
        """流式文本对话

        Args:
            prompt: 提示词
            session_id: 会话 ID
            image_urls: 图片 URL 列表（当前版本暂不支持）
            contexts: 上下文
            system_prompt: 系统提示词
            model: 模型名称
            **kwargs: 其他参数

        Yields:
            LLMResponse 对象
        """
        try:
            messages = self._build_messages(prompt, system_prompt, contexts)

            # 调用流式 API
            response = self._client.chat.completions.create(
                model=model or self.model_name,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True,
            )

            accumulated_text = ""
            usage = TokenUsage()

            for chunk in response:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]

                # 处理内容
                if hasattr(choice.delta, 'content') and choice.delta.content:
                    accumulated_text += choice.delta.content
                    yield LLMResponse(
                        role="assistant",
                        completion_text=choice.delta.content,
                        is_chunk=True,
                        usage=usage,
                    )

                # 处理使用情况
                if hasattr(chunk, 'usage') and chunk.usage:
                    usage = TokenUsage(
                        input_other=chunk.usage.prompt_tokens,
                        output=chunk.usage.completion_tokens,
                    )

                # 检查是否完成
                if hasattr(choice, 'finish_reason') and choice.finish_reason == "stop":
                    break

            # 发送最终结果
            yield LLMResponse(
                role="assistant",
                completion_text=accumulated_text,
                is_chunk=False,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"[ZhipuAI] 流式文本聊天失败: {e}")
            yield LLMResponse(
                role="err",
                completion_text="",
            )

    async def get_models(self) -> list[str]:
        """获取支持的模型列表"""
        try:
            # 智谱 AI 模型列表
            return [
                "glm-4",
                "glm-4-flash",
                "glm-4-plus",
                "glm-4-0520",
                "glm-4-air",
                "glm-4-long",
                "glm-3-turbo",
            ]
        except Exception as e:
            logger.error(f"[ZhipuAI] 获取模型列表失败: {e}")
            return [
                "glm-4",
                "glm-4-flash",
                "glm-4-plus",
                "glm-3-turbo",
            ]

    async def test(self, timeout: float = 45.0):
        """测试提供商连接"""
        try:
            import asyncio
            await asyncio.wait_for(
                self.text_chat(prompt="REPLY `PONG` ONLY"),
                timeout=timeout,
            )
        except Exception as e:
            raise Exception(f"测试连接失败: {e}")

    async def close(self) -> None:
        """关闭提供商"""
        logger.info("[ZhipuAI] 提供商已关闭")