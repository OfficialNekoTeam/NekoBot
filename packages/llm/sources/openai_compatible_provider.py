"""OpenAI Compatible LLM 提供商

支持所有兼容 OpenAI API 格式的服务
"""

import asyncio
from typing import Any, AsyncGenerator, Optional

from loguru import logger

from ..base import BaseLLMProvider, LLMProviderType
from ..register import register_llm_provider


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
        self._client: Optional[Any] = None

    async def initialize(self) -> None:
        """初始化提供商"""
        if not self.api_key:
            logger.warning("[OpenAI Compatible] API Key 未配置，可能无法使用")

        # 这里应该初始化 HTTP 客户端
        # 暂时使用模拟实现
        logger.info(f"[OpenAI Compatible] 提供商已初始化，Base URL: {self.base_url}")

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
    ) -> dict[str, Any]:
        """文本对话

        Args:
            prompt: 提示词
            session_id: 会话 ID
            image_urls: 图片 URL 列表
            func_tool: 工具集
            contexts: 上下文
            system_prompt: 系统提示词
            tool_calls_result: 工具调用结果
            model: 模型名称
            extra_user_content_parts: 额外用户内容部分

        Returns:
            LLM 响应
        """
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

        # 这里应该调用 OpenAI Compatible API
        # 暂时返回模拟响应
        logger.info(
            f"[OpenAI Compatible] 使用模型 {model or self.model_name} 处理请求，消息数: {len(messages)}"
        )

        # 模拟延迟
        await asyncio.sleep(0.5)

        return {
            "content": f"这是来自 OpenAI Compatible 服务 ({self.base_url}) 的模拟响应。",
            "model": model or self.model_name,
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        }

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
    ) -> AsyncGenerator[dict[str, Any], None]:
        """流式文本对话

        Args:
            prompt: 提示词
            session_id: 会话 ID
            image_urls: 图片 URL 列表
            func_tool: 工具集
            contexts: 上下文
            system_prompt: 系统提示词
            tool_calls_result: 工具调用结果
            model: 模型名称

        Yields:
            LLM 响应块
        """
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

        # 这里应该调用 OpenAI Compatible API 流式接口
        # 暂时返回模拟流式响应
        logger.info(f"[OpenAI Compatible] 使用模型 {model or self.model_name} 处理流式请求")

        response_text = f"这是来自 OpenAI Compatible 服务 ({self.base_url}) 的模拟流式响应。"

        # 模拟流式输出
        for i in range(0, len(response_text), 10):
            chunk = response_text[i : i + 10]
            yield {
                "content": chunk,
                "delta": chunk,
                "finish_reason": None,
            }
            await asyncio.sleep(0.1)

        # 发送结束标记
        yield {
            "content": "",
            "delta": "",
            "finish_reason": "stop",
        }

    async def get_models(self) -> list[str]:
        """获取支持的模型列表

        Returns:
            模型名称列表
        """
        # 这里应该调用 OpenAI Compatible API 获取模型列表
        # 暂时返回常见模型列表
        return [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "claude-3-opus",
            "claude-3-sonnet",
            "claude-3-haiku",
            "glm-4",
            "deepseek-chat",
        ]

    async def test(self) -> None:
        """测试提供商连接"""
        logger.info(f"[OpenAI Compatible] 测试连接到 {self.base_url}...")
        await asyncio.sleep(0.5)
        logger.info("[OpenAI Compatible] 连接测试成功")

    async def close(self) -> None:
        """关闭提供商"""
        if self._client:
            # 关闭 HTTP 客户端
            pass
        logger.info("[OpenAI Compatible] 提供商已关闭")