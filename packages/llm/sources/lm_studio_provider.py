"""LM Studio LLM 提供商

支持 LM Studio 本地部署，使用 OpenAI 兼容接口
"""

import httpx
from typing import Any, AsyncGenerator, Optional
from loguru import logger

from ..base import BaseLLMProvider
from ..register import register_llm_provider, LLMProviderType
from ..entities import LLMResponse, TokenUsage


@register_llm_provider(
    provider_type_name="lm_studio",
    provider_type=LLMProviderType.CHAT_COMPLETION,
    desc="LM Studio (本地部署，通过 OpenAI 兼容接口)",
    default_config_tmpl={
        "type": "lm_studio",
        "enable": False,
        "id": "lm_studio",
        "model": "lm-studio",
        "api_key": "",
        "base_url": "http://localhost:1234",
        "max_tokens": 4096,
        "temperature": 0.7,
        "timeout": 120,
    },
)


class LMStudioProvider(BaseLLMProvider):
    """LM Studio LLM 提供商"""

    def __init__(
        self,
        provider_config: dict,
        provider_settings: dict,
    ) -> None:
        super().__init__(provider_config, provider_settings)
        self.api_key = provider_config.get("api_key", "")
        self.base_url = provider_config.get("base_url", "http://localhost:1234")
        self.model_name = provider_config.get("model", "lm-studio")
        self.max_tokens = provider_config.get("max_tokens", 4096)
        self.temperature = provider_config.get("temperature", 0.7)
        self.timeout = provider_config.get("timeout", 120)
        self._client: Optional[httpx.Client] = None

    async def initialize(self) -> None:
        """初始化提供商"""
        logger.info("[LM Studio] 初始化提供商...")
        # LM Studio 本地部署，使用本地服务器连接
        # 不需要 API Key
        logger.info("[LM Studio] 本地部署模式，使用本地服务器连接")
        
        # 创建本地 HTTP 客户端（不验证 SSL，用于本地服务器）
        self._client = httpx.AsyncClient(timeout=self.timeout, verify=False)

    async def get_models(self) -> list[str]:
        """获取支持的模型列表"""
        try:
            # LM Studio 支持本地模型
            # 返回默认的本地模型列表
            response = await self._client.post(
                f"{self.base_url}/v1/models",
                json={}
            )
            response.raise_for_status()
            
            result = response.json()
            if "data" in result:
                models = result["data"]
                logger.debug(f"[LM Studio] 找到 {len(models)} 个模型")
                return sorted([m.get("id", "") for m in models])
            return []
        except Exception as e:
            logger.error(f"[LM Studio] 获取模型列表失败: {e}")
            return [
                "lm-studio",
                "lm-studio-v1",
                "lm-studio-v2",
                "lm-studio-v3",
                "lm-studio-v4",
            ]

    async def _build_messages(
        self,
        prompt: Optional[str],
        system_prompt: Optional[str],
        contexts: Optional[list[dict]],
    ) -> list[dict]:
        """构建消息列表"""
        messages = []
        
        # 添加系统提示词
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 添加上下文
        if contexts:
            for ctx in contexts:
                messages.append(ctx)
        
        # 添加用户消息
        if prompt:
            messages.append({"role": "user", "content": prompt})
        
        return messages

    async def text_chat(
        self,
        prompt: Optional[str],
        session_id: Optional[str],
        image_urls: Optional[list[str]] = None,
        func_tool: Optional[Any] = None,
        contexts: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """文本对话"""
        try:
            model = model or self.model_name
            messages = self._build_messages(prompt, system_prompt, contexts)
            
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
            }
            
            response = await self._client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                content = choice.get("message", {}).get("content", "")
                
                usage_data = choice.get("usage", {})
                usage = TokenUsage(
                    input_other=usage_data.get("prompt_tokens", 0),
                    output=usage_data.get("completion_tokens", 0),
                )
                
                logger.debug(f"[LM Studio] 收到响应，使用 {usage.input_other + usage.output} tokens")
                
                return LLMResponse(
                    role="assistant",
                    completion_text=content,
                    raw_completion=result,
                    usage=usage,
                )
            else:
                logger.warning(f"[LM Studio] 响应格式异常: {result}")
                return LLMResponse(
                    role="assistant",
                    completion_text="",
                    raw_completion=result,
                    usage=TokenUsage(input_other=0, output=0),
                )
        except Exception as e:
            logger.error(f"[LM Studio] 文本对话失败: {e}")
            return LLMResponse(
                role="err",
                completion_text=str(e),
                raw_completion={},
                usage=TokenUsage(input_other=0, output=0),
                )

    async def text_chat_stream(
        self,
        prompt: Optional[str],
        session_id: Optional[str],
        image_urls: Optional[list[str]] = None,
        func_tool: Optional[Any] = None,
        contexts: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[LLMResponse, None]:
        """流式文本对话"""
        try:
            model = model or self.model_name
            messages = self._build_messages(prompt, system_prompt, contexts)
            
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
            }
            
            full_content = ""
            chunk_count = 0
                
            async with self._client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    try:
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            
                            import json
                            data = json.loads(data_str)
                            
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                completion_text = delta.get("content", "")
                                
                                if completion_text:
                                    chunk_count += 1
                                    yield LLMResponse(
                                        role="assistant",
                                        completion_text=completion_text,
                                        is_chunk=True,
                                    )
                                    
                                    if "usage" in data:
                                        usage_data = data["usage"]
                                        yield LLMResponse(
                                            role="assistant",
                                            completion_text=completion_text,
                                            is_chunk=True,
                                            usage=TokenUsage(
                                                input_other=usage_data.get("prompt_tokens", 0),
                                                output=usage_data.get("completion_tokens", 0),
                                            ),
                                        )
                        
                    except json.JSONDecodeError:
                        logger.warning(f"[LM Studio] 解析响应行失败: {line}")
                        continue
                    
                    except Exception as e:
                        logger.error(f"[LM Studio] 流式对话失败: {e}")
                        yield LLMResponse(
                            role="err",
                            completion_text=str(e),
                            is_chunk=True,
                        )
                
                # 发送结束标记
                yield LLMResponse(
                    role="assistant",
                    completion_text="",
                    is_chunk=True,
                )
        except Exception as e:
            logger.error(f"[LM Studio] 流式对话失败: {e}")
            yield LLMResponse(
                role="err",
                completion_text=str(e),
                is_chunk=True,
            )

    async def test(self, timeout: float = 45.0) -> None:
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
            logger.info("[LM Studio] 提供商已关闭")