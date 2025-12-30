"""LLM 提供商单元测试

测试新增的 LLM 提供商功能
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from packages.llm import (
    LLMProviderType,
    LLMResponse,
    TokenUsage,
)
from packages.llm.sources import (
    claude_provider,
    deepseek_provider,
    dashscope_provider,
    moonshot_provider,
    zhipu_provider,
)


class TestClaudeProvider:
    """Claude 提供商测试"""

    @pytest.fixture
    def provider_config(self):
        return {
            "type": "claude",
            "enable": True,
            "id": "test_claude",
            "model": "claude-3-5-sonnet-20241022",
            "api_key": "test_key",
            "max_tokens": 4096,
            "temperature": 0.7,
        }

    @pytest.fixture
    def provider_settings(self):
        return {}

    @pytest.fixture
    def provider(self, provider_config, provider_settings):
        return claude_provider.ClaudeProvider(provider_config, provider_settings)

    def test_initialization(self, provider, provider_config):
        """测试初始化"""
        assert provider.model_name == provider_config["model"]
        assert provider.api_key == provider_config["api_key"]
        assert provider.max_tokens == provider_config["max_tokens"]
        assert provider.temperature == provider_config["temperature"]

    def test_get_current_key(self, provider):
        """测试获取当前 API Key"""
        key = provider.get_current_key()
        assert key == "test_key"

    def test_set_model(self, provider):
        """测试设置模型"""
        provider.set_model("claude-3-5-haiku-20241022")
        assert provider.get_model() == "claude-3-5-haiku-20241022"

    def test_set_key(self, provider):
        """测试设置 API Key"""
        provider.set_key("new_key")
        assert provider.get_current_key() == "new_key"
        assert provider.api_key == "new_key"

    @pytest.mark.asyncio
    async def test_get_models(self, provider):
        """测试获取模型列表"""
        # Mock the client
        with patch.object(provider, '_client') as mock_client:
            mock_models = MagicMock()
            mock_models.data = [
                MagicMock(id="claude-3-5-sonnet-20241022"),
                MagicMock(id="claude-3-5-haiku-20241022"),
            ]
            mock_client.models.list.return_value = mock_models

            models = await provider.get_models()
            assert "claude-3-5-sonnet-20241022" in models
            assert "claude-3-5-haiku-20241022" in models


class TestDeepSeekProvider:
    """DeepSeek 提供商测试"""

    @pytest.fixture
    def provider_config(self):
        return {
            "type": "deepseek",
            "enable": True,
            "id": "test_deepseek",
            "model": "deepseek-chat",
            "api_key": "test_key",
            "max_tokens": 4096,
            "temperature": 0.7,
        }

    @pytest.fixture
    def provider_settings(self):
        return {}

    @pytest.fixture
    def provider(self, provider_config, provider_settings):
        return deepseek_provider.DeepSeekProvider(provider_config, provider_settings)

    def test_initialization(self, provider, provider_config):
        """测试初始化"""
        assert provider.model_name == provider_config["model"]
        assert provider.api_key == provider_config["api_key"]
        assert provider.max_tokens == provider_config["max_tokens"]

    def test_get_current_key(self, provider):
        """测试获取当前 API Key"""
        key = provider.get_current_key()
        assert key == "test_key"

    def test_set_key(self, provider):
        """测试设置 API Key"""
        provider.set_key("new_key")
        assert provider.get_current_key() == "new_key"


class TestDashScopeProvider:
    """DashScope (通义千问) 提供商测试"""

    @pytest.fixture
    def provider_config(self):
        return {
            "type": "dashscope",
            "enable": True,
            "id": "test_dashscope",
            "model": "qwen-max",
            "api_key": "test_key",
            "max_tokens": 4096,
            "temperature": 0.7,
        }

    @pytest.fixture
    def provider_settings(self):
        return {}

    @pytest.fixture
    def provider(self, provider_config, provider_settings):
        return dashscope_provider.DashScopeProvider(provider_config, provider_settings)

    def test_initialization(self, provider, provider_config):
        """测试初始化"""
        assert provider.model_name == provider_config["model"]
        assert provider.api_key == provider_config["api_key"]
        assert provider.max_tokens == provider_config["max_tokens"]

    def test_get_current_key(self, provider):
        """测试获取当前 API Key"""
        key = provider.get_current_key()
        assert key == "test_key"

    @pytest.mark.asyncio
    async def test_get_models(self, provider):
        """测试获取模型列表"""
        models = await provider.get_models()
        assert "qwen-max" in models
        assert "qwen-plus" in models
        assert "qwen-turbo" in models


class TestMoonshotProvider:
    """Moonshot (Kimi) 提供商测试"""

    @pytest.fixture
    def provider_config(self):
        return {
            "type": "moonshot",
            "enable": True,
            "id": "test_moonshot",
            "model": "moonshot-v1-8k",
            "api_key": "test_key",
            "max_tokens": 4096,
            "temperature": 0.7,
        }

    @pytest.fixture
    def provider_settings(self):
        return {}

    @pytest.fixture
    def provider(self, provider_config, provider_settings):
        return moonshot_provider.MoonshotProvider(provider_config, provider_settings)

    def test_initialization(self, provider, provider_config):
        """测试初始化"""
        assert provider.model_name == provider_config["model"]
        assert provider.api_key == provider_config["api_key"]
        assert provider.max_tokens == provider_config["max_tokens"]

    def test_get_current_key(self, provider):
        """测试获取当前 API Key"""
        key = provider.get_current_key()
        assert key == "test_key"


class TestZhipuProvider:
    """智谱 AI 提供商测试"""

    @pytest.fixture
    def provider_config(self):
        return {
            "type": "zhipu",
            "enable": True,
            "id": "test_zhipu",
            "model": "glm-4",
            "api_key": "test_key",
            "max_tokens": 4096,
            "temperature": 0.7,
        }

    @pytest.fixture
    def provider_settings(self):
        return {}

    @pytest.fixture
    def provider(self, provider_config, provider_settings):
        return zhipu_provider.ZhipuProvider(provider_config, provider_settings)

    def test_initialization(self, provider, provider_config):
        """测试初始化"""
        assert provider.model_name == provider_config["model"]
        assert provider.api_key == provider_config["api_key"]
        assert provider.max_tokens == provider_config["max_tokens"]

    def test_get_current_key(self, provider):
        """测试获取当前 API Key"""
        key = provider.get_current_key()
        assert key == "test_key"

    @pytest.mark.asyncio
    async def test_get_models(self, provider):
        """测试获取模型列表"""
        models = await provider.get_models()
        assert "glm-4" in models
        assert "glm-4-flash" in models
        assert "glm-4-plus" in models


class TestLLMResponse:
    """LLM 响应类测试"""

    def test_creation(self):
        """测试创建 LLM 响应"""
        response = LLMResponse(role="assistant", completion_text="Hello, World!")
        assert response.role == "assistant"
        assert response.completion_text == "Hello, World!"

    def test_default_values(self):
        """测试默认值"""
        response = LLMResponse(role="assistant")
        assert response.completion_text == ""
        assert response.is_chunk == False
        assert response.tools_call_args == []
        assert response.tools_call_name == []


class TestTokenUsage:
    """Token 使用情况测试"""

    def test_creation(self):
        """测试创建 Token 使用情况"""
        usage = TokenUsage(input_other=100, input_cached=50, output=200)
        assert usage.input_other == 100
        assert usage.input_cached == 50
        assert usage.output == 200

    def test_properties(self):
        """测试属性计算"""
        usage = TokenUsage(input_other=100, input_cached=50, output=200)
        assert usage.input == 150  # input_other + input_cached
        assert usage.total == 350  # input + output

    def test_addition(self):
        """测试加法运算"""
        usage1 = TokenUsage(input_other=100, input_cached=50, output=200)
        usage2 = TokenUsage(input_other=50, input_cached=30, output=100)
        combined = usage1 + usage2
        assert combined.input_other == 150
        assert combined.input_cached == 80
        assert combined.output == 300