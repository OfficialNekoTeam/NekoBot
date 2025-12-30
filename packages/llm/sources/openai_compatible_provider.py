"""OpenAI Compatible LLM 提供商

支持所有兼容 OpenAI API 格式的服务
使用 httpx 进行 HTTP 请求
"""

import httpx
from typing import Any, AsyncGenerator, Optional

from loguru import logger

from ..base import BaseLLMProvider
from ..register import register_llm_provider, LLMProviderType
from ..entities import LLMResponse, TokenUsage


@register_llm_provider(
    provider_type_name="openai_compatible",
    desc="OpenAI Compatible 提供商 (支持所有兼容 OpenAI API 的服务)",
    provider_type=LLMProviderType.CHAT_COMPLETION,
    default_config_tmpl={
        "type": "openai_compatible",
        "enable": False,
        "id": "openai_compatible",
        "model": "gpt-4o-mini",
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    provider_display_name="OpenAI Compatible",
)
class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI Compatible LLM 提供商"""

    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__(provider_config, provider_settings)
        self.api_key = provider_config.get("api_key", "")
        self.base_url = provider_config.get("base_url", "https://api.openai.com/v1")
        self.max_tokens = provider_config.get("max_tokens", 4096)
        self.temperature = provider_config.get("temperature", 0.7)
        self.timeout = provider_config.get("timeout", 120)
        self._client: Optional[httpx.AsyncClient] = None
        self._current_key_index = 0

    def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
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

    async def initialize(self) -> None:
        """初始化提供商"""
        if not self.api_key:
            logger.warning("[OpenAI Compatible] API Key 未配置，可能无法使用")

        self._client = self._get_client()
        logger.info(f"[OpenAI Compatible] 提供商已初始化，Base URL: {self.base_url}")

    async def get_models(self):
        """获取支持的模型列表"""
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()

                if "data" in result:
                    models = sorted(result["data"], key=lambda x: x.get("id", ""))
                    return [m.get("id", "") for m in models]
                return []
        except httpx.HTTPStatusError as e:
            logger.error(f"[OpenAI Compatible] 获取模型列表失败: {e}")
            return [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-3.5-turbo",
            ]
        except Exception as e:
            logger.error(f"[OpenAI Compatible] 获取模型列表失败: {e}")
            return [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-3.5-turbo",
            ]

    async def text_chat(
        self,
        prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        image_urls: Optional[list[str]] = None,
        func_tool: Optional[Any] = None,
        contexts: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
        tool_calls_result: Optional[Any] = None,
        model: Optional[str] = None,
        extra_user_content_parts: Optional[list[Any]] = None,
        **kwargs,
    ) -> LLMResponse:
        """文本对话"""
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

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            payload = {
                "model": model or self.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()

                if "choices" in result and len(result["choices"]) > 0:
                    choice = result["choices"][0]
                    content = choice.get("message", {}).get("content", "")

                    usage = None
                    if "usage" in result:
                        usage_data = result["usage"]
                        usage = TokenUsage(
                            input_other=usage_data.get("prompt_tokens", 0),
                            output=usage_data.get("completion_tokens", 0),
                        )

                    return LLMResponse(
                        role="assistant",
                        completion_text=content,
                        raw_completion=result,
                        usage=usage,
                    )
                else:
                    logger.warning(f"[OpenAI Compatible] 响应格式异常: {result}")
                    return LLMResponse(
                        role="assistant",
                        completion_text="",
                    )

        except httpx.HTTPStatusError as e:
            logger.error(f"[OpenAI Compatible] API 请求失败: {e.response.status_code} - {e.response.text}")
            return LLMResponse(
                role="err",
                completion_text="",
            )
        except Exception as e:
            logger.error(f"[OpenAI Compatible] 文本聊天失败: {e}")
            return LLMResponse(
                role="err",
                completion_text="",
            )

    async def text_chat_stream(
        self,
        prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        image_urls: Optional[list[str]] = None,
        func_tool: Optional[Any] = None,
        contexts: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
        tool_calls_result: Optional[Any] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[LLMResponse, None]:
        """流式文本对话"""
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

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            payload = {
                "model": model or self.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": True,
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break

                            try:
                                import json
                                data = json.loads(data_str)

                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    completion_text = delta.get("content", "")

                                    if completion_text:
                                        yield LLMResponse(
                                            role="assistant",
                                            completion_text=completion_text,
                                            is_chunk=True,
                                        )

                                    if "usage" in data:
                                        usage_data = data["usage"]
                                        yield LLMResponse(
                                            role="assistant",
                                            completion_text="",
                                            is_chunk=True,
                                            usage=TokenUsage(
                                                input_other=usage_data.get("prompt_tokens", 0),
                                                output=usage_data.get("completion_tokens", 0),
                                            ),
                                        )
                            except json.JSONDecodeError:
                                continue

            # 发送结束标记
            yield LLMResponse(
                role="assistant",
                completion_text="",
                is_chunk=True,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"[OpenAI Compatible] API 请求失败: {e.response.status_code} - {e.response.text}")
            yield LLMResponse(
                role="err",
                completion_text="",
            )
        except Exception as e:
            logger.error(f"[OpenAI Compatible] 流式文本聊天失败: {e}")
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
            logger.info("[OpenAI Compatible] 提供商已关闭")
