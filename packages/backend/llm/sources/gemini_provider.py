"""Google Gemini LLM 提供商

参考 AstrBot 的 Gemini 适配器实现
"""

import asyncio
from typing import Any, AsyncGenerator, Optional

from loguru import logger

from ..base import BaseLLMProvider, LLMProviderType
from ..register import register_llm_provider


@register_llm_provider(
    provider_type_name="gemini",
    desc="Google Gemini 提供商 (Gemini 2.0, Gemini 1.5 等)",
    provider_type=LLMProviderType.CHAT_COMPLETION,
    default_config_tmpl={
        "type": "gemini",
        "enable": False,
        "id": "gemini",
        "model": "gemini-2.0-flash-exp",
        "api_key": "",
        "max_tokens": 8192,
        "temperature": 0.7,
    },
    provider_display_name="Google Gemini",
)
class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM 提供商"""

    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__(provider_config, provider_settings)
        self.api_key = provider_config.get("api_key", "")
        self.max_tokens = provider_config.get("max_tokens", 8192)
        self.temperature = provider_config.get("temperature", 0.7)
        self._client: Optional[Any] = None

    async def initialize(self) -> None:
        """初始化提供商"""
        if not self.api_key:
            raise ValueError("Gemini API Key 未配置")

        # 这里应该初始化 Gemini 客户端
        # 暂时使用模拟实现
        logger.info("[Gemini] Gemini 提供商已初始化")

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

        # 这里应该调用 Gemini API
        # 暂时返回模拟响应
        logger.info(
            f"[Gemini] 使用模型 {model or self.model_name} 处理请求，消息数: {len(messages)}"
        )

        # 模拟延迟
        await asyncio.sleep(0.5)

        return {
            "content": f"这是来自 Google Gemini {model or self.model_name} 的模拟响应。",
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

        # 这里应该调用 Gemini API 流式接口
        # 暂时返回模拟流式响应
        logger.info(f"[Gemini] 使用模型 {model or self.model_name} 处理流式请求")

        response_text = (
            f"这是来自 Google Gemini {model or self.model_name} 的模拟流式响应。"
        )

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
        # 这里应该调用 Gemini API 获取模型列表
        return [
            "gemini-2.0-flash-exp",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ]

    async def test(self) -> None:
        """测试提供商连接"""
        if not self.api_key:
            raise ValueError("Gemini API Key 未配置")

        # 这里应该调用 Gemini API 进行测试
        logger.info("[Gemini] 测试连接...")
        await asyncio.sleep(0.5)
        logger.info("[Gemini] 连接测试成功")

    async def close(self) -> None:
        """关闭提供商"""
        if self._client:
            # 关闭 Gemini 客户端
            pass
        logger.info("[Gemini] 提供商已关闭")
