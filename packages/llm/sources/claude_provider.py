"""Anthropic Claude LLM 提供商

参考 AstrBot 的 Claude 适配器实现
"""

import base64
import json
from collections.abc import AsyncGenerator
from typing import Any, Optional

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import Message
from anthropic.types.usage import Usage

from loguru import logger

from ..base import BaseLLMProvider
from ..register import register_llm_provider, LLMProviderType
from ..entities import LLMResponse, TokenUsage


class SuppressNonTextPartsWarning:
    """过滤 SDK 中的非文本部分警告"""
    def filter(self, record):
        return "there are non-text parts in the response" not in record.getMessage()


import logging
logging.getLogger("anthropic").addFilter(SuppressNonTextPartsWarning())


@register_llm_provider(
    provider_type_name="claude",
    desc="Anthropic Claude 提供商 (Claude 3.5, Claude 3 等)",
    provider_type=LLMProviderType.CHAT_COMPLETION,
    default_config_tmpl={
        "type": "claude",
        "enable": False,
        "id": "claude",
        "model": "claude-3-5-sonnet-20241022",
        "api_key": "",
        "max_tokens": 4096,
        "temperature": 0.7,
        "base_url": "https://api.anthropic.com",
        "timeout": 120,
    },
    provider_display_name="Anthropic Claude",
)
class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude LLM 提供商"""

    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__(provider_config, provider_settings)
        self.api_key = provider_config.get("api_key", "")
        self.base_url = provider_config.get("base_url", "https://api.anthropic.com")
        self.max_tokens = provider_config.get("max_tokens", 4096)
        self.temperature = provider_config.get("temperature", 0.7)
        self.timeout = provider_config.get("timeout", 120)
        self._current_key_index = 0

        # 思考配置（Claude 3.7+ 支持）
        self.thinking_config = provider_config.get("anth_thinking_config", {})

        self._client: Optional[AsyncAnthropic] = None
        self._init_client()

    def _init_client(self) -> None:
        """初始化 Claude 客户端"""
        self._client = AsyncAnthropic(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

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
            raise ValueError("Claude API Key 未配置")

        logger.info("[Claude] Claude 提供商已初始化")

    def _extract_usage(self, usage: Usage) -> TokenUsage:
        """提取使用情况"""
        return TokenUsage(
            input_other=usage.input_tokens or 0,
            input_cached=usage.cache_read_input_tokens or 0,
            output=usage.output_tokens,
        )

    def _prepare_payload(self, messages: list[dict]):
        """准备 Claude API 的请求 payload

        Args:
            messages: OpenAI 格式的消息列表
        Returns:
            system_prompt: 系统提示内容
            new_messages: 处理后的消息列表，去除系统提示
        """
        system_prompt = ""
        new_messages = []
        for message in messages:
            if message["role"] == "system":
                system_prompt = message["content"] or ""
            elif message["role"] == "assistant":
                blocks = []
                if isinstance(message["content"], str) and message["content"].strip():
                    blocks.append({"type": "text", "text": message["content"]})
                elif isinstance(message["content"], list):
                    for part in message["content"]:
                        blocks.append(part)

                # 处理工具调用
                if "tool_calls" in message and isinstance(message["tool_calls"], list):
                    for tool_call in message["tool_calls"]:
                        blocks.append(
                            {
                                "type": "tool_use",
                                "name": tool_call["function"]["name"],
                                "input": (
                                    json.loads(tool_call["function"]["arguments"])
                                    if isinstance(tool_call["function"]["arguments"], str)
                                    else tool_call["function"]["arguments"]
                                ),
                                "id": tool_call["id"],
                            },
                        )
                new_messages.append({"role": "assistant", "content": blocks})
            elif message["role"] == "tool":
                new_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message["tool_call_id"],
                                "content": message["content"] or "",
                            },
                        ],
                    },
                )
            else:
                new_messages.append(message)

        return system_prompt, new_messages

    async def text_chat(
        self,
        prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        image_urls: Optional[list[str]] = None,
        contexts: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """文本对话"""
        messages = contexts or []

        # 添加系统提示词
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})

        # 添加用户消息
        if prompt:
            user_message = {"role": "user", "content": prompt}
            if image_urls:
                user_message["content"] = [
                    {"type": "text", "text": prompt},
                    *[{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": url}} for url in image_urls],
                ]
            messages.append(user_message)
        elif image_urls:
            messages.append({"role": "user", "content": [{"type": "text", "text": "[图片]"}]})

        try:
            system_prompt, new_messages = self._prepare_payload(messages)
            model_name = model or self.model_name

            # 构建请求参数
            params = {
                "model": model_name,
                "messages": new_messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            # 添加系统提示词
            if system_prompt:
                params["system"] = system_prompt

            # 添加思考配置（如果支持）
            if self.thinking_config.get("budget"):
                params["thinking"] = {
                    "budget_tokens": self.thinking_config.get("budget"),
                    "type": "enabled",
                }

            completion = await self._client.messages.create(**params)

            if len(completion.content) == 0:
                raise Exception("API 返回的 completion 为空。")

            llm_response = LLMResponse(role="assistant")
            completion_text = ""
            reasoning_content = ""

            for content_block in completion.content:
                if content_block.type == "text":
                    completion_text += str(content_block.text)
                if content_block.type == "thinking":
                    reasoning_content = str(content_block.thinking)
                if content_block.type == "tool_use":
                    llm_response.tools_call_args.append(content_block.input)
                    llm_response.tools_call_name.append(content_block.name)
                    llm_response.tools_call_ids.append(content_block.id)

            llm_response.completion_text = completion_text
            llm_response.raw_completion = completion
            llm_response.id = completion.id
            llm_response.usage = self._extract_usage(completion.usage)

            # 处理思考内容
            if reasoning_content:
                llm_response.completion_text = llm_response.completion_text.replace(f"<thinking>{reasoning_content}</thinking>", "")

            return llm_response

        except Exception as e:
            logger.error(f"[Claude] 文本聊天失败: {e}")
            return LLMResponse(
                role="err",
                completion_text="",
            )

    async def text_chat_stream(
        self,
        prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        image_urls: Optional[list[str]] = None,
        contexts: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[LLMResponse, None]:
        """流式文本对话"""
        messages = contexts or []

        # 添加系统提示词
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})

        # 添加用户消息
        if prompt:
            user_message = {"role": "user", "content": prompt}
            if image_urls:
                user_message["content"] = [
                    {"type": "text", "text": prompt},
                    *[{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": url}} for url in image_urls],
                ]
            messages.append(user_message)
        elif image_urls:
            messages.append({"role": "user", "content": [{"type": "text", "text": "[图片]"}]})

        try:
            system_prompt, new_messages = self._prepare_payload(messages)
            model_name = model or self.model_name

            # 构建请求参数
            params = {
                "model": model_name,
                "messages": new_messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            # 添加系统提示词
            if system_prompt:
                params["system"] = system_prompt

            # 添加思考配置（如果支持）
            if self.thinking_config.get("budget"):
                params["thinking"] = {
                    "budget_tokens": self.thinking_config.get("budget"),
                    "type": "enabled",
                }

            # 工具调用缓冲区
            tool_use_buffer = {}
            final_text = ""
            final_tool_calls = []
            response_id = None
            usage = TokenUsage()
            reasoning_content = ""

            async with self._client.messages.stream(**params) as stream:
                async for event in stream:
                    if event.type == "message_start":
                        response_id = event.message.id
                        usage = self._extract_usage(event.message.usage)

                    elif event.type == "content_block_start":
                        if event.content_block.type == "text":
                            yield LLMResponse(
                                role="assistant",
                                completion_text="",
                                is_chunk=True,
                                usage=usage,
                                id=response_id,
                            )
                        elif event.content_block.type == "tool_use":
                            tool_use_buffer[event.index] = {
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": {},
                            }

                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            final_text += event.delta.text
                            yield LLMResponse(
                                role="assistant",
                                completion_text=event.delta.text,
                                is_chunk=True,
                                usage=usage,
                                id=response_id,
                            )
                        elif event.delta.type == "thinking_delta":
                            reasoning = event.delta.thinking
                            if reasoning:
                                reasoning_content += reasoning
                                yield LLMResponse(
                                    role="assistant",
                                    reasoning_content=reasoning,
                                    is_chunk=True,
                                    usage=usage,
                                    id=response_id,
                                )
                        elif event.delta.type == "input_json_delta":
                            if event.index in tool_use_buffer:
                                if "input_json" not in tool_use_buffer[event.index]:
                                    tool_use_buffer[event.index]["input_json"] = ""
                                tool_use_buffer[event.index]["input_json"] += event.delta.partial_json

                    elif event.type == "content_block_stop":
                        if event.index in tool_use_buffer:
                            tool_info = tool_use_buffer[event.index]
                            try:
                                if "input_json" in tool_info:
                                    tool_info["input"] = json.loads(tool_info["input_json"])

                                final_tool_calls.append({
                                    "id": tool_info["id"],
                                    "name": tool_info["name"],
                                    "input": tool_info["input"],
                                })

                                yield LLMResponse(
                                    role="tool",
                                    completion_text="",
                                    tools_call_args=[tool_info["input"]],
                                    tools_call_name=[tool_info["name"]],
                                    tools_call_ids=[tool_info["id"]],
                                    is_chunk=True,
                                    usage=usage,
                                    id=response_id,
                                )
                            except json.JSONDecodeError:
                                logger.warning(f"工具调用参数 JSON 解析失败: {tool_info}")

                            del tool_use_buffer[event.index]

                    elif event.type == "message_delta":
                        if event.usage:
                            if event.usage.input_tokens is not None:
                                usage.input_other = event.usage.input_tokens
                            if event.usage.cache_read_input_tokens is not None:
                                usage.input_cached = event.usage.cache_read_input_tokens
                            if event.usage.output_tokens is not None:
                                usage.output = event.usage.output_tokens

            # 返回最终结果
            final_response = LLMResponse(
                role="assistant",
                completion_text=final_text,
                is_chunk=False,
                usage=usage,
                id=response_id,
            )

            if final_tool_calls:
                final_response.tools_call_args = [call["input"] for call in final_tool_calls]
                final_response.tools_call_name = [call["name"] for call in final_tool_calls]
                final_response.tools_call_ids = [call["id"] for call in final_tool_calls]

            yield final_response

        except Exception as e:
            logger.error(f"[Claude] 流式文本聊天失败: {e}")
            yield LLMResponse(
                role="err",
                completion_text="",
            )

    async def get_models(self) -> list[str]:
        """获取支持的模型列表"""
        try:
            models = await self._client.models.list()
            models_str = []
            for model in sorted(models.data, key=lambda x: x.id):
                models_str.append(model.id)
            return models_str
        except Exception as e:
            logger.error(f"[Claude] 获取模型列表失败: {e}")
            return [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
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
        if self._client:
            await self._client.close()
            logger.info("[Claude] 提供商已关闭")