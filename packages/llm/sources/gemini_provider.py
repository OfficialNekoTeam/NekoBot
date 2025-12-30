"""Google Gemini LLM 提供商

参考 AstrBot 的 Gemini 适配器实现，使用官方 google-genai 库
"""

import base64
from collections.abc import AsyncGenerator
from typing import Any, Optional, cast

from google import genai
from google.genai import types
from google.genai.errors import APIError

from loguru import logger

from ..base import BaseLLMProvider
from ..register import register_llm_provider, LLMProviderType
from ..entities import LLMResponse, TokenUsage


class SuppressNonTextPartsWarning:
    """过滤 Gemini SDK 中的非文本部分警告"""
    def filter(self, record):
        return "there are non-text parts in the response" not in record.getMessage()


import logging
logging.getLogger("google_genai.types").addFilter(SuppressNonTextPartsWarning())


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

    CATEGORY_MAPPING = {
        "harassment": types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        "hate_speech": types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        "sexually_explicit": types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        "dangerous_content": types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
    }

    THRESHOLD_MAPPING = {
        "BLOCK_NONE": types.HarmBlockThreshold.BLOCK_NONE,
        "BLOCK_ONLY_HIGH": types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        "BLOCK_MEDIUM_AND_ABOVE": types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        "BLOCK_LOW_AND_ABOVE": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    }

    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__(provider_config, provider_settings)
        self.api_key = provider_config.get("api_key", "")
        self.max_tokens = provider_config.get("max_tokens", 8192)
        self.temperature = provider_config.get("temperature", 0.7)
        self.timeout = provider_config.get("timeout", 180)
        self.api_base = provider_config.get("api_base", None)
        self._current_key_index = 0

        if self.api_base and self.api_base.endswith("/"):
            self.api_base = self.api_base[:-1]

        self._client: Optional[genai.Client] = None
        self._aio_client: Optional[genai.AsyncClient] = None
        self._init_client()

    def _init_client(self) -> None:
        """初始化Gemini客户端"""
        self._client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                base_url=self.api_base,
                timeout=self.timeout * 1000,  # 毫秒
            ),
        )
        self._aio_client = self._client.aio

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
            raise ValueError("Gemini API Key 未配置")

        logger.info("[Gemini] Gemini 提供商已初始化")

    def _prepare_conversation(self, messages: list[dict]) -> list[types.Content]:
        """准备 Gemini SDK 的 Content 列表"""

        def create_text_part(text: str) -> types.Part:
            content_a = text if text else " "
            if not text:
                logger.warning("文本内容为空，已添加空格占位")
            return types.Part.from_text(text=content_a)

        def process_image_url(image_url_dict: dict) -> types.Part:
            url = image_url_dict["url"]
            mime_type = url.split(":")[1].split(";")[0]
            image_bytes = base64.b64decode(url.split(",", 1)[1])
            return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        def append_or_extend(
            contents: list[types.Content],
            part: list[types.Part],
            content_cls: type[types.Content],
        ) -> None:
            if contents and isinstance(contents[-1], content_cls):
                assert contents[-1].parts is not None
                contents[-1].parts.extend(part)
            else:
                contents.append(content_cls(parts=part))

        gemini_contents: list[types.Content] = []
        for message in messages:
            role, content = message["role"], message.get("content")

            if role == "user":
                if isinstance(content, list):
                    parts = [
                        (
                            types.Part.from_text(text=item["text"] or " ")
                            if item["type"] == "text"
                            else process_image_url(item["image_url"])
                        )
                        for item in content
                    ]
                else:
                    parts = [create_text_part(content)]
                append_or_extend(gemini_contents, parts, types.UserContent)

            elif role == "assistant":
                if content:
                    parts = [types.Part.from_text(text=content)]
                    append_or_extend(gemini_contents, parts, types.ModelContent)
                else:
                    # 处理工具调用或其他情况
                    parts = [types.Part.from_text(text=" ")]
                    append_or_extend(gemini_contents, parts, types.ModelContent)

            elif role == "tool":
                parts = [
                    types.Part.from_function_response(
                        name=message["tool_call_id"],
                        response={
                            "name": message["tool_call_id"],
                            "content": message["content"],
                        },
                    ),
                ]
                append_or_extend(gemini_contents, parts, types.UserContent)

        if gemini_contents and isinstance(gemini_contents[0], types.ModelContent):
            gemini_contents.pop()

        return gemini_contents

    def _extract_usage(
        self, usage_metadata: types.GenerateContentResponseUsageMetadata
    ) -> TokenUsage:
        """Extract usage from candidate"""
        return TokenUsage(
            input_other=usage_metadata.prompt_token_count or 0,
            input_cached=usage_metadata.cached_content_token_count or 0,
            output=usage_metadata.candidates_token_count or 0,
        )

    def _process_content_parts(
        self, candidate: types.Candidate, llm_response: LLMResponse
    ) -> str:
        """处理内容部分并返回文本"""
        if not candidate.content:
            logger.warning(f"收到的 candidate.content 为空: {candidate}")
            return ""

        finish_reason = candidate.finish_reason
        result_parts: list[types.Part] | None = candidate.content.parts

        if finish_reason == types.FinishReason.SAFETY:
            raise Exception("模型生成内容未通过 Gemini 平台的安全检查")

        if finish_reason in {
            types.FinishReason.PROHIBITED_CONTENT,
            types.FinishReason.SPII,
            types.FinishReason.BLOCKLIST,
        }:
            raise Exception("模型生成内容违反 Gemini 平台政策")

        if not result_parts:
            logger.warning(f"收到的 candidate.content.parts 为空: {candidate}")
            return ""

        chain = []
        for part in result_parts:
            if part.text:
                chain.append(part.text)
            elif part.inline_data and part.inline_data.mime_type.startswith("image/"):
                chain.append("[图片]")

        return "".join(chain)

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
                    *[{"type": "image_url", "image_url": {"url": url}} for url in image_urls],
                ]
            messages.append(user_message)
        elif image_urls:
            messages.append({"role": "user", "content": [{"type": "text", "text": "[图片]"}]})

        try:
            conversation = self._prepare_conversation(messages)
            model_name = model or self.model_name

            result = await self._aio_client.models.generate_content(
                model=model_name,
                contents=cast(types.ContentListUnion, conversation),
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                ),
            )

            if not result.candidates:
                logger.error(f"请求失败, 返回的 candidates 为空: {result}")
                raise Exception("请求失败, 返回的 candidates 为空。")

            llm_response = LLMResponse("assistant")
            completion_text = self._process_content_parts(result.candidates[0], llm_response)
            llm_response.completion_text = completion_text
            llm_response.raw_completion = result
            llm_response.id = result.response_id

            if result.usage_metadata:
                llm_response.usage = self._extract_usage(result.usage_metadata)

            return llm_response

        except APIError as e:
            logger.error(f"[Gemini] API 请求失败: {e}")
            return LLMResponse(
                role="err",
                completion_text="",
            )
        except Exception as e:
            logger.error(f"[Gemini] 文本聊天失败: {e}")
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
                    *[{"type": "image_url", "image_url": {"url": url}} for url in image_urls],
                ]
            messages.append(user_message)
        elif image_urls:
            messages.append({"role": "user", "content": [{"type": "text", "text": "[图片]"}]})

        try:
            conversation = self._prepare_conversation(messages)
            model_name = model or self.model_name

            result = await self._aio_client.models.generate_content_stream(
                model=model_name,
                contents=cast(types.ContentListUnion, conversation),
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                ),
            )

            accumulated_text = ""
            final_response = None

            async for chunk in result:
                llm_response = LLMResponse("assistant", is_chunk=True)

                if not chunk.candidates:
                    continue

                if chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if part.text:
                            accumulated_text += part.text
                            llm_response.completion_text = part.text
                            yield llm_response

                if chunk.candidates[0].finish_reason:
                    final_response = LLMResponse("assistant", is_chunk=False)
                    final_response.completion_text = accumulated_text
                    if chunk.usage_metadata:
                        final_response.usage = self._extract_usage(chunk.usage_metadata)
                    break

            if final_response:
                yield final_response

        except APIError as e:
            logger.error(f"[Gemini] API 请求失败: {e}")
            yield LLMResponse(
                role="err",
                completion_text="",
            )
        except Exception as e:
            logger.error(f"[Gemini] 流式文本聊天失败: {e}")
            yield LLMResponse(
                role="err",
                completion_text="",
            )

    async def get_models(self) -> list[str]:
        """获取支持的模型列表"""
        try:
            models = await self._aio_client.models.list()
            return [
                m.name.replace("models/", "")
                for m in models
                if m.supported_actions
                and "generateContent" in m.supported_actions
                and m.name
            ]
        except APIError as e:
            logger.error(f"[Gemini] 获取模型列表失败: {e}")
            return [
                "gemini-2.0-flash-exp",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
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
        logger.info("[Gemini] 提供商已关闭")
