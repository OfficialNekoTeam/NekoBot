"""DeepSeek LLM 提供商

DeepSeek API 兼容 OpenAI 格式
"""

from collections.abc import AsyncGenerator
from typing import Optional

from loguru import logger

from ..base import BaseLLMProvider
from ..register import register_llm_provider, LLMProviderType
from ..entities import LLMResponse, TokenUsage
from openai import AsyncOpenAI


@register_llm_provider(
    provider_type_name="deepseek",
    desc="DeepSeek 提供商 (DeepSeek-V3, DeepSeek-Coder 等)",
    provider_type=LLMProviderType.CHAT_COMPLETION,
    default_config_tmpl={
        "type": "deepseek",
        "enable": False,
        "id": "deepseek",
        "model": "deepseek-chat",
        "api_key": "",
        "base_url": "https://api.deepseek.com",
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    provider_display_name="DeepSeek",
)
class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek LLM 提供商"""

    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__(provider_config, provider_settings)
        self.api_key = provider_config.get("api_key", "")
        self.base_url = provider_config.get("base_url", "https://api.deepseek.com")
        self.max_tokens = provider_config.get("max_tokens", 4096)
        self.temperature = provider_config.get("temperature", 0.7)
        self.timeout = provider_config.get("timeout", 120)
        self.custom_headers = provider_config.get("custom_headers", {})
        self._client: Optional[AsyncOpenAI] = None
        self._current_key_index = 0

    def _get_client(self) -> AsyncOpenAI:
        """获取或创建 DeepSeek 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                default_headers=self.custom_headers,
                timeout=self.timeout,
            )
        return self._client

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
        self._client = None

    async def initialize(self) -> None:
        """初始化提供商"""
        if not self.api_key:
            raise ValueError("DeepSeek API Key 未配置")

        self._client = self._get_client()
        logger.info("[DeepSeek] DeepSeek 提供商已初始化")

    async def get_models(self):
        """获取支持的模型列表"""
        try:
            models_str = []
            models = await self._client.models.list()
            models = sorted(models.data, key=lambda x: x.id)
            for model in models:
                models_str.append(model.id)
            return models_str
        except Exception as e:
            raise Exception(f"获取模型列表失败：{e}")

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
            image_urls: 图片 URL 列表
            contexts: 上下文
            system_prompt: 系统提示词
            model: 模型名称
            **kwargs: 其他参数

        Returns:
            LLMResponse 对象
        """
        try:
            # 构建消息列表
            messages = []

            # 添加系统提示词
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # 添加上下文
            if contexts:
                messages.extend(contexts)

            # 添加用户消息
            if prompt:
                user_message = {"role": "user", "content": prompt}
                if image_urls:
                    user_message["content"] = [
                        {"type": "text", "text": prompt},
                        *[
                            {"type": "image_url", "image_url": {"url": url}}
                            for url in image_urls
                        ],
                    ]
                messages.append(user_message)
            elif image_urls:
                messages.append({"role": "user", "content": [{"type": "text", "text": "[图片]"}]})

            completion = await self._client.chat.completions.create(
                model=model or self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            # 解析响应
            if not completion.choices:
                raise Exception("API 返回的 completion 为空。")

            choice = completion.choices[0]

            # 解析文本响应
            if choice.message.content:
                completion_text = str(choice.message.content).strip()
            else:
                completion_text = ""

            # 解析使用情况
            usage = None
            if completion.usage:
                usage = TokenUsage(
                    input_other=completion.usage.prompt_tokens,
                    output=completion.usage.completion_tokens,
                )

            return LLMResponse(
                role="assistant",
                completion_text=completion_text,
                raw_completion=completion,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"[DeepSeek] 文本聊天失败: {e}")
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
            image_urls: 图片 URL 列表
            contexts: 上下文
            system_prompt: 系统提示词
            model: 模型名称
            **kwargs: 其他参数

        Yields:
            LLMResponse 对象
        """
        try:
            # 构建消息列表
            messages = []

            # 添加系统提示词
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # 添加上下文
            if contexts:
                messages.extend(contexts)

            # 添加用户消息
            if prompt:
                user_message = {"role": "user", "content": prompt}
                if image_urls:
                    user_message["content"] = [
                        {"type": "text", "text": prompt},
                        *[
                            {"type": "image_url", "image_url": {"url": url}}
                            for url in image_urls
                        ],
                    ]
                messages.append(user_message)
            elif image_urls:
                messages.append({"role": "user", "content": [{"type": "text", "text": "[图片]"}]})

            stream = await self._client.chat.completions.create(
                model=model or self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )

            llm_response = LLMResponse("assistant", is_chunk=True)

            try:
                async for chunk in stream:
                    if not chunk.choices:
                        continue

                    delta = chunk.choices[0].delta

                    # 处理内容
                    completion_text = ""
                    if delta.content:
                        completion_text = delta.content

                    # 处理使用情况
                    if chunk.usage:
                        llm_response.usage = TokenUsage(
                            input_other=chunk.usage.prompt_tokens,
                            output=chunk.usage.completion_tokens,
                        )

                    if completion_text:
                        llm_response.completion_text = completion_text
                        yield llm_response

                # 发送结束标记
                llm_response = LLMResponse(
                    role="assistant",
                    completion_text="",
                    is_chunk=True,
                )
                yield llm_response
            except Exception as e:
                logger.error(f"[DeepSeek] 流式文本聊天失败: {e}")
                yield LLMResponse(
                    role="err",
                    completion_text="",
                )
        except Exception as e:
            logger.error(f"[DeepSeek] 流式文本聊天失败: {e}")
            yield LLMResponse(
                role="err",
                completion_text="",
            )

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
        if self._client and not self._client.is_closed:
            await self._client.close()
            logger.info("[DeepSeek] 提供商已关闭")