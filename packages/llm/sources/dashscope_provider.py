"""阿里云 DashScope (通义千问) LLM 提供商

支持通义千问系列模型
"""

from collections.abc import AsyncGenerator
from typing import Optional

import dashscope
from dashscope import Generation
from dashscope.aigc.generation import AioGeneration

from loguru import logger

from ..base import BaseLLMProvider
from ..register import register_llm_provider, LLMProviderType
from ..entities import LLMResponse, TokenUsage


@register_llm_provider(
    provider_type_name="dashscope",
    desc="阿里云 DashScope 提供商 (通义千问 Qwen 系列)",
    provider_type=LLMProviderType.CHAT_COMPLETION,
    default_config_tmpl={
        "type": "dashscope",
        "enable": False,
        "id": "dashscope",
        "model": "qwen-max",
        "api_key": "",
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    provider_display_name="阿里云 DashScope",
)
class DashScopeProvider(BaseLLMProvider):
    """阿里云 DashScope LLM 提供商"""

    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__(provider_config, provider_settings)
        self.api_key = provider_config.get("api_key", "")
        self.max_tokens = provider_config.get("max_tokens", 4096)
        self.temperature = provider_config.get("temperature", 0.7)
        self._current_key_index = 0

        # 设置 API Key
        if self.api_key:
            dashscope.api_key = self.api_key

        self._client = AioGeneration()

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
        dashscope.api_key = key

    async def initialize(self) -> None:
        """初始化提供商"""
        if not self.api_key:
            raise ValueError("DashScope API Key 未配置")

        logger.info("[DashScope] DashScope 提供商已初始化")

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

            # 构建请求参数
            params = {
                "model": model or self.model_name,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            # 调用 API
            response = await self._client.call(**params)

            # 检查响应状态
            if response.status_code != 200:
                raise Exception(f"API 请求失败: {response.code} - {response.message}")

            if not response.output:
                raise Exception("API 返回的 output 为空。")

            # 解析响应
            output = response.output
            if not output.choices:
                raise Exception("API 返回的 choices 为空。")

            choice = output.choices[0]

            # 解析文本响应
            completion_text = ""
            if hasattr(choice.message, 'content') and choice.message.content:
                completion_text = choice.message.content

            # 解析使用情况
            usage = None
            if hasattr(response, 'usage') and response.usage:
                usage = TokenUsage(
                    input_other=response.usage.input_tokens,
                    output=response.usage.output_tokens,
                )

            return LLMResponse(
                role="assistant",
                completion_text=completion_text,
                raw_completion=response,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"[DashScope] 文本聊天失败: {e}")
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

            # 构建请求参数
            params = {
                "model": model or self.model_name,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "stream": True,
            }

            # 调用流式 API
            responses = await self._client.call(**params)

            accumulated_text = ""
            usage = TokenUsage()

            for response in responses:
                if response.status_code != 200:
                    raise Exception(f"API 请求失败: {response.code} - {response.message}")

                if not response.output:
                    continue

                output = response.output
                if not output.choices:
                    continue

                choice = output.choices[0]

                # 处理内容
                if hasattr(choice.message, 'content') and choice.message.content:
                    accumulated_text += choice.message.content
                    yield LLMResponse(
                        role="assistant",
                        completion_text=choice.message.content,
                        is_chunk=True,
                        usage=usage,
                    )

                # 处理使用情况
                if hasattr(response, 'usage') and response.usage:
                    usage = TokenUsage(
                        input_other=response.usage.input_tokens,
                        output=response.usage.output_tokens,
                    )

                # 检查是否完成
                if output.finish_reason == "stop":
                    break

            # 发送最终结果
            yield LLMResponse(
                role="assistant",
                completion_text=accumulated_text,
                is_chunk=False,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"[DashScope] 流式文本聊天失败: {e}")
            yield LLMResponse(
                role="err",
                completion_text="",
            )

    async def get_models(self) -> list[str]:
        """获取支持的模型列表"""
        try:
            # DashScope 模型列表
            return [
                "qwen-max",
                "qwen-plus",
                "qwen-turbo",
                "qwen-max-longcontext",
                "qwen-vl-max",
                "qwen-vl-plus",
                "qwen-audio-turbo",
            ]
        except Exception as e:
            logger.error(f"[DashScope] 获取模型列表失败: {e}")
            return [
                "qwen-max",
                "qwen-plus",
                "qwen-turbo",
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
        logger.info("[DashScope] 提供商已关闭")