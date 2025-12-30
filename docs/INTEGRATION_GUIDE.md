# NekoBot 集成指南

本文档详细说明了 NekoBot 的 LLM 提供商和平台适配器的集成方法。

## 目录

- [LLM 提供商集成](#llm-提供商集成)
  - [支持的 LLM 提供商](#支持的-llm-提供商)
  - [添加新的 LLM 提供商](#添加新的-llm-提供商)
  - [LLM 提供商配置](#llm-提供商配置)
  - [API 调用示例](#api-调用示例)
- [平台适配器集成](#平台适配器集成)
  - [支持的平台](#支持的平台)
  - [添加新的平台适配器](#添加新的平台适配器)
  - [平台适配器配置](#平台适配器配置)
  - [Webhook 支持](#webhook-支持)
- [单元测试](#单元测试)
- [故障排除](#故障排除)

---

## LLM 提供商集成

### 支持的 LLM 提供商

NekoBot 目前支持以下 LLM 提供商：

| 提供商 | 类型 | 描述 | 支持的模型 |
|---------|------|------|-----------|
| OpenAI | chat_completion | OpenAI GPT 系列 | gpt-4o, gpt-4o-mini, gpt-3.5-turbo |
| Google Gemini | chat_completion | Google Gemini 系列 | gemini-2.0-flash-exp, gemini-1.5-pro, gemini-1.5-flash |
| GLM (智谱) | chat_completion | 智谱 GLM 系列 | glm-4, glm-4-flash, glm-3-turbo |
| OpenAI 兼容 | chat_completion | OpenAI 兼容接口 | - |
| **Claude** | chat_completion | Anthropic Claude 系列 | claude-3-5-sonnet-20241022, claude-3-5-haiku-20241022 |
| **DeepSeek** | chat_completion | DeepSeek 系列 | deepseek-chat, deepseek-coder |
| **DashScope** | chat_completion | 阿里云通义千问 | qwen-max, qwen-plus, qwen-turbo |
| **Moonshot** | chat_completion | Moonshot Kimi 系列 | moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k |
| **ZhipuAI** | chat_completion | 智谱 GLM-4 系列 | glm-4, glm-4-flash, glm-4-plus |

### 添加新的 LLM 提供商

要添加新的 LLM 提供商，需要创建一个继承自 [`BaseLLMProvider`](../packages/llm/base.py) 的类，并使用 [`@register_llm_provider`](../packages/llm/register.py) 装饰器进行注册。

#### 步骤 1: 创建提供商类

```python
# packages/llm/sources/your_provider.py

from typing import Optional
from loguru import logger

from ..base import BaseLLMProvider
from ..register import register_llm_provider, LLMProviderType
from ..entities import LLMResponse, TokenUsage

@register_llm_provider(
    provider_type_name="your_provider",
    desc="您的提供商描述",
    provider_type=LLMProviderType.CHAT_COMPLETION,
    default_config_tmpl={
        "type": "your_provider",
        "enable": False,
        "id": "your_provider",
        "model": "default-model-name",
        "api_key": "",
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    provider_display_name="Your Provider",
)
class YourProvider(BaseLLMProvider):
    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__(provider_config, provider_settings)
        self.api_key = provider_config.get("api_key", "")
        self.max_tokens = provider_config.get("max_tokens", 4096)
        self.temperature = provider_config.get("temperature", 0.7)
        self._current_key_index = 0

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

    async def get_models(self) -> list[str]:
        """获取支持的模型列表"""
        return ["model-1", "model-2"]

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
        """文本对话"""
        # 实现您的 API 调用逻辑
        pass

    async def text_chat_stream(
        self,
        prompt: str | None = None,
        session_id: str | None = None,
        image_urls: list[str] | None = None,
        contexts: list[dict] | None = None,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs,
    ):
        """流式文本对话（可选）"""
        # 实现您的流式 API 调用逻辑
        async for response in []:
            yield response

    async def test(self, timeout: float = 45.0):
        """测试提供商连接"""
        await self.text_chat(prompt="REPLY `PONG` ONLY")

    async def close(self) -> None:
        """关闭提供商"""
        logger.info("[YourProvider] 提供商已关闭")
```

#### 步骤 2: 在 __init__.py 中导入

在 [`packages/llm/sources/__init__.py`](../packages/llm/sources/__init__.py) 中添加导入：

```python
from . import (
    openai_provider,
    gemini_provider,
    glm_provider,
    openai_compatible_provider,
    claude_provider,      # 新增
    deepseek_provider,     # 新增
    dashscope_provider,    # 新增
    moonshot_provider,     # 新增
    zhipu_provider,       # 新增
    your_provider,         # 您的提供商
)
```

### LLM 提供商配置

在配置文件中添加 LLM 提供商配置：

```yaml
llm_providers:
  - type: claude
    enable: true
    id: my-claude
    model: claude-3-5-sonnet-20241022
    api_key: sk-ant-xxx
    max_tokens: 4096
    temperature: 0.7
    base_url: https://api.anthropic.com
    timeout: 120

  - type: deepseek
    enable: true
    id: my-deepseek
    model: deepseek-chat
    api_key: sk-xxx
    max_tokens: 4096
    temperature: 0.7
    base_url: https://api.deepseek.com

  - type: dashscope
    enable: true
    id: my-dashscope
    model: qwen-max
    api_key: sk-xxx
    max_tokens: 4096
    temperature: 0.7

  - type: moonshot
    enable: true
    id: my-moonshot
    model: moonshot-v1-8k
    api_key: sk-xxx
    max_tokens: 8192
    temperature: 0.7
    base_url: https://api.moonshot.cn/v1

  - type: zhipu
    enable: true
    id: my-zhipu
    model: glm-4
    api_key: xxx
    max_tokens: 4096
    temperature: 0.7
```

### API 调用示例

```python
from packages.llm import llm_provider_cls_map

# 获取提供商类
provider_class = llm_provider_cls_map.get("claude")

# 创建提供商实例
provider = provider_class(provider_config, provider_settings)

# 设置模型
provider.set_model("claude-3-5-sonnet-20241022")

# 调用文本对话
response = await provider.text_chat(
    prompt="你好，请介绍一下自己",
    system_prompt="你是一个友好的AI助手",
    contexts=[]
)

print(response.completion_text)
print(response.usage)  # Token 使用情况

# 流式调用
async for chunk in provider.text_chat_stream(
    prompt="请写一首诗",
    system_prompt="你是一个诗人"
):
    print(chunk.completion_text, end="")
```

---

## 平台适配器集成

### 支持的平台

NekoBot 目前支持以下平台适配器：

| 平台 | 描述 | 支持的消息类型 | 流式消息 |
|------|------|---------------|---------|
| aiocqhttp | OneBot V11 协议 | 私聊/群聊 | 否 |
| Discord | Discord 机器人 | 频道/私聊 | 否 |
| Telegram | Telegram 机器人 | 频道/私聊 | 是 |
| **飞书 (Lark)** | 飞书官方 API | 群聊/私聊 | 否 |
| **KOOK** | 开黑平台 | 频道/私聊 | 是 |
| **QQ频道** | QQ频道官方 API | 频道 | 是 |

### 添加新的平台适配器

要添加新的平台适配器，需要创建一个继承自 [`BasePlatform`](../packages/platform/base.py) 的类，并使用 [`@register_platform_adapter`](../packages/platform/register.py) 装饰器进行注册。

#### 步骤 1: 创建适配器类

```python
# packages/platform/sources/your_platform/your_platform.py

import asyncio
from typing import Any, Optional

from loguru import logger

from ...base import BasePlatform, PlatformStatus
from ...register import register_platform_adapter

@register_platform_adapter(
    "your_platform",
    "您的平台描述",
    default_config_tmpl={
        "type": "your_platform",
        "enable": False,
        "id": "your_platform",
        "name": "Your Bot",
        "token": "",  # 或其他必需的配置
    },
    adapter_display_name="Your Platform",
    support_streaming_message=True,
)
class YourPlatform(BasePlatform):
    def __init__(
        self,
        platform_config: dict,
        platform_settings: dict,
        event_queue: Optional[asyncio.Queue] = None,
    ) -> None:
        super().__init__(platform_config, platform_settings, event_queue)

        self.token = platform_config.get("token", "")
        self._session = None
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """启动平台适配器"""
        logger.info("[YourPlatform] 正在启动适配器...")

        # 初始化客户端
        self._init_client()

        # 连接到平台
        await self._connect()

        self.status = PlatformStatus.RUNNING
        logger.info("[YourPlatform] 适配器已启动")

        # 等待关闭信号
        await self._shutdown_event.wait()

    async def stop(self) -> None:
        """停止平台适配器"""
        logger.info("[YourPlatform] 正在停止适配器...")
        self._shutdown_event.set()

        # 断开连接
        await self._disconnect()

        self.status = PlatformStatus.STOPPED
        logger.info("[YourPlatform] 适配器已停止")

    async def send_message(
        self,
        message_type: str,
        target_id: str,
        message: str,
        **kwargs,
    ) -> dict[str, Any]:
        """发送消息

        Args:
            message_type: 消息类型（private/group）
            target_id: 目标ID
            message: 消息内容
            **kwargs: 其他参数

        Returns:
            发送结果
        """
        # 实现发送消息逻辑
        return {"status": "success", "message": "消息已发送"}

    def _init_client(self) -> None:
        """初始化客户端"""
        # 初始化平台客户端
        pass

    async def _connect(self) -> None:
        """连接到平台"""
        # 实现连接逻辑
        pass

    async def _disconnect(self) -> None:
        """断开连接"""
        # 实现断开连接逻辑
        pass
```

#### 步骤 2: 在 __init__.py 中导入

在 [`packages/platform/sources/__init__.py`](../packages/platform/sources/__init__.py) 中添加导入：

```python
from . import (
    aiocqhttp,
    discord,
    telegram,
    lark,          # 新增
    kook,           # 新增
    qqchannel,      # 新增
    your_platform,    # 您的适配器
)
```

### 平台适配器配置

在配置文件中添加平台适配器配置：

```yaml
platforms:
  - type: lark
    enable: true
    id: my-lark
    name: "NekoBot"
    app_id: cli_xxx
    app_secret: xxx
    domain: https://open.feishu.cn
    connection_mode: socket
    lark_bot_name: "NekoBot"

  - type: kook
    enable: true
    id: my-kook
    name: "NekoBot"
    token: kook_xxx

  - type: qqchannel
    enable: true
    id: my-qqchannel
    name: "NekoBot"
    app_id: 123456
    token: xxx
    sandbox: false
```

### Webhook 支持

NekoBot 支持统一 Webhook 模式。要支持 Webhook：

1. 在配置中启用 `unified_webhook_mode` 和设置 `webhook_uuid`
2. 实现 `webhook_callback(self, request)` 方法

```python
async def webhook_callback(self, request: Any) -> Any:
    """统一 Webhook 回调入口"""
    try:
        # 解析请求数据
        event_data = await request.json()

        # 验证事件（如果需要）
        # 处理事件
        await self.handle_webhook(event_data)

        # 返回成功响应
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"[YourPlatform] Webhook 处理失败: {e}")
        return {"status": "error", "message": str(e)}
```

---

## 单元测试

### 运行 LLM 提供商测试

```bash
# 测试所有 LLM 提供商
pytest tests/test_llm_providers.py -v

# 测试特定的提供商
pytest tests/test_llm_providers.py::TestClaudeProvider -v
pytest tests/test_llm_providers.py::TestDeepSeekProvider -v
pytest tests/test_llm_providers.py::TestDashScopeProvider -v
pytest tests/test_llm_providers.py::TestMoonshotProvider -v
pytest tests/test_llm_providers.py::TestZhipuProvider -v
```

### 运行平台适配器测试

```bash
# 测试所有平台适配器
pytest tests/test_platform_adapters.py -v

# 测试特定的平台
pytest tests/test_platform_adapters.py::TestLarkPlatform -v
pytest tests/test_platform_adapters.py::TestKookPlatform -v
pytest tests/test_platform_adapters.py::TestQQChannelPlatform -v
```

### 测试覆盖率

要查看测试覆盖率：

```bash
pytest --cov=packages.llm --cov-report=html tests/test_llm_providers.py
pytest --cov=packages.platform --cov-report=html tests/test_platform_adapters.py
```

---

## 故障排除

### 常见问题

#### LLM 提供商相关

**问题**: API Key 无效
```
解决方法```: 检查配置文件中的 API Key 是否正确，确保没有多余的空格或换行符。

**问题**: 模型列表为空
```
解决方法```: 检查网络连接是否正常，确认 API 端点是否可访问。

**问题**: 流式输出中断
```
解决方法```: 检查异步上下文是否正确，确保使用 `async for` 迭代。

#### 平台适配器相关

**问题**: 无法连接到平台
```
解决方法```: 检查网络连接，确认代理设置是否正确。

**问题**: 消息发送失败
```
解决方法```: 检查 Token 是否过期，确认目标 ID 格式是否正确。

**问题**: Webhook 事件未收到
```
解决方法```: 确认 Webhook URL 配置正确，检查平台是否正确发送事件。

### 日志调试

启用详细日志以进行调试：

```python
from loguru import logger

logger.debug("调试信息")  # 调试级别
logger.info("一般信息")   # 信息级别
logger.warning("警告信息") # 警告级别
logger.error("错误信息")   # 错误级别
```

---

## 贡献指南

欢迎提交 Pull Request 来添加新的 LLM 提供商或平台适配器！

### 提交前检查清单

- [ ] 代码遵循现有代码风格
- [ ] 添加了完整的文档字符串
- [ ] 实现了所有必需的方法
- [ ] 添加了单元测试
- [ ] 更新了集成文档
- [ ] 测试通过所有测试用例

### 代码风格

- 使用 4 空格缩进
- 类名使用 PascalCase
- 函数名使用 snake_case
- 常量使用 UPPER_CASE
- 添加类型注解

---

## 许可证

本项目的所有代码遵循 [MIT 许可证](../LICENSE)。

---

## 联系方式

如有问题或建议，请通过以下方式联系：

- GitHub Issues: https://github.com/your-repo/issues
- Email: your-email@example.com