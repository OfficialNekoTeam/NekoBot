# NekoBot 配置编辑器使用指南

## 概述

配置编辑器提供了一个动态的、基于schema的配置编辑系统，用于管理平台适配器和LLM提供商的配置。该系统支持完整的参数编辑，包括host、port、token、api_key等所有必要字段。

## 架构

### 后端架构

**API路由**: `packages/routes/config_editor_route.py`

提供以下功能：
- 平台配置管理（获取、更新、添加、删除）
- LLM提供商配置管理（获取、更新、添加、删除）
- 配置schema获取（自动生成表单所需的字段定义）
- 配置验证（实时验证配置的有效性）

### 前端架构

**核心组件**:
1. **动态配置编辑器** (`ui-component/forms/ConfigEditor.tsx`)
   - 根据schema自动生成表单
   - 支持多种字段类型（字符串、数字、布尔、枚举）
   - 实时表单验证
   - 敏感信息保护（密码/密钥隐藏）

2. **配置编辑器页面** (`views/config-editor/index.tsx`)
   - 提供平台和LLM提供商两个标签页
   - 显示已配置的配置项
   - 编辑对话框集成

3. **类型定义** (`types/config.ts`)
   - 完整的TypeScript类型
   - 平台类型、LLM类型、配置schema等

4. **API客户端** (`api/config.ts`)
   - 封装所有后端API调用

## 使用说明

### 1. 添加平台配置

```typescript
// 1. 获取平台类型schema
const schema = await configAPI.getPlatformSchema('aiocqhttp');

// 2. 使用动态编辑器编辑
<ConfigEditor
  schema={schema}
  config={config}
  onChange={handleChange}
  onSave={handleSave}
  onCancel={handleCancel}
/>
```

### 2. 添加LLM提供商

```typescript
// 1. 获取LLM类型schema
const schema = await configAPI.getLLMSchema('openai');

// 2. 使用动态编辑器编辑
<ConfigEditor
  schema={schema}
  config={config}
  onChange={handleChange}
  onSave={handleSave}
  onCancel={handleCancel}
/>
```

### 3. 配置参数说明

#### 平台参数

**aiocqhttp**:
- `ws_host`: WebSocket监听地址（默认: 0.0.0.0）
- `ws_port`: WebSocket监听端口（默认: 6299）
- `access_token`: 访问令牌（可选）
- `command_prefix`: 命令前缀（默认: /）

**discord**:
- `discord_token`: Discord机器人Token
- `discord_guild_id_for_debug`: 调试服务器ID（可选）
- `discord_command_register`: 是否自动注册命令（默认: true）
- `discord_activity_name`: 活动状态名称（可选）
- `discord_proxy`: 代理地址（可选）

**telegram**:
- `telegram_token`: Telegram机器人Token
- `telegram_api_id`: API ID（可选）
- `telegram_api_hash`: API Hash（可选）
- `telegram_proxy`: 代理地址（可选）

**kook**:
- `token`: KOOK机器人Token
- `verify_token`: Webhook验证令牌（可选）
- `encrypt_key`: Webhook加密密钥（可选）
- `api_base`: API基础地址（默认: https://www.kookapp.cn/api/v3）

**lark**:
- `app_id`: 飞书应用ID
- `app_secret`: 飞书应用Secret
- `domain`: API域名（默认: https://open.feishu.cn）
- `connection_mode`: 连接模式（socket/webhook）
- `lark_bot_name`: 机器人显示名称
- `verify_token`: Webhook验证令牌（可选）
- `encrypt_key`: Webhook加密密钥（可选）

**wecom**:
- `corp_id`: 企业ID
- `corp_secret`: 企业Secret
- `agent_id`: 应用Agent ID
- `token`: Webhook验证Token
- `encoding_aes_key`: 消息加密AES密钥（可选）
- `receive_id`: 接收ID（可选）
- `receive_url`: 接收URL（可选）

#### LLM参数

所有LLM提供商支持以下通用参数：

- `type`: 提供商类型
- `enable`: 是否启用
- `id`: 提供商ID
- `name`: 显示名称
- `api_key`: API密钥（本地部署如Ollama、LM Studio不需要）
- `base_url`: API基础地址
- `model`: 模型名称
- `max_tokens`: 最大令牌数（默认: 4096）
- `temperature`: 温度参数（默认: 0.7，范围: 0.0-2.0）
- `timeout`: 超时时间（默认: 120，单位: 秒）

### 4. 支持的LLM提供商

- OpenAI
- Anthropic
- Azure OpenAI
- Ollama（本地部署）
- LM Studio（本地部署）
- DeepSeek
- Moonshot
- Zhipu
- GLM
- Claude Provider
- Dashscope
- 以及所有通过动态注册的提供商

## API端点

### 平台配置

```
GET    /api/config/platforms/types          - 获取所有平台类型
GET    /api/config/platforms/schema?type=xxx  - 获取平台配置schema
GET    /api/config/platforms/config?id=xxx    - 获取平台配置
POST   /api/config/platforms/config          - 更新平台配置
POST   /api/config/platforms/add            - 添加平台
POST   /api/config/platforms/delete          - 删除平台
```

### LLM配置

```
GET    /api/config/llm/types              - 获取所有LLM类型
GET    /api/config/llm/schema?type=xxx       - 获取LLM配置schema
GET    /api/config/llm/config?id=xxx       - 获取LLM提供商配置
POST   /api/config/llm/config              - 更新LLM提供商配置
POST   /api/config/llm/add                - 添加LLM提供商
POST   /api/config/llm/delete              - 删除LLM提供商
```

### 配置验证

```
POST   /api/config/validate                 - 验证配置
```

## 特性

✅ **动态表单生成** - 根据schema自动生成表单，无需手写  
✅ **实时验证** - 表单字段实时验证，提交前提示错误  
✅ **敏感信息保护** - 密码和密钥字段默认隐藏，可切换显示  
✅ **配置模板** - 每种平台/LLM类型都有默认配置模板  
✅ **类型安全** - 完整的TypeScript类型定义  
✅ **统一接口** - 平台和LLM使用相同的API模式

## 文件结构

```
backend/
├── packages/
│   └── routes/
│       └── config_editor_route.py    # 配置编辑器API路由
└── data/
    ├── platforms_sources.json           # 平台配置文件
    └── llm_providers.json           # LLM提供商配置文件

frontend/
├── src/
│   ├── types/
│   │   └── config.ts               # 配置编辑器类型定义
│   ├── ui-component/forms/
│   │   └── ConfigEditor.tsx      # 动态配置编辑器组件
│   ├── views/
│   │   └── config-editor/         # 配置编辑器页面
│   ├── api/
│   │   └── config.ts              # 配置编辑器API客户端
│   └── routes/
│       └── MainRoutes.tsx          # 路由配置
```

## 开发指南

### 添加新的平台适配器

1. 在 `packages/platform/sources/` 创建适配器目录
2. 实现适配器类，继承 `BasePlatform`
3. 使用 `@register_platform_adapter` 装饰器注册
4. 在装饰器中定义 `default_config_tmpl`

示例：

```python
@register_platform_adapter(
    "your_platform",
    "平台描述",
    default_config_tmpl={
        "type": "your_platform",
        "enable": False,
        "id": "your_platform",
        "name": "平台显示名称",
        "host": "0.0.0.0",  # 可选参数
        "port": 12345,           # 可选参数
    },
)
class YourPlatform(BasePlatform):
    def __init__(self, platform_config, platform_settings, event_queue=None):
        super().__init__(platform_config, platform_settings, event_queue)
        self.host = self.get_config("host", "0.0.0.0")
        self.port = self.get_config("port", 12345)
```

### 添加新的LLM提供商

1. 在 `packages/llm/sources/` 创建提供商文件
2. 实现提供商类，继承 `BaseLLMProvider`
3. 使用 `@register_llm_provider` 装饰器注册
4. 在装饰器中定义 `default_config_tmpl`

示例：

```python
@register_llm_provider(
    provider_type_name="your_provider",
    desc="提供商描述",
    default_config_tmpl={
        "type": "your_provider",
        "enable": False,
        "id": "your_provider",
        "model": "model-name",
        "api_key": "",
        "base_url": "https://api.example.com/v1",
    },
)
class YourProvider(BaseLLMProvider):
    def __init__(self, provider_config, provider_settings):
        super().__init__(provider_config, provider_settings)
```

## 常见问题

### Q: 如何修改配置文件的路径？

A: 在 `config_editor_route.py` 中修改 `PLATFORMS_SOURCES_PATH` 和 `LLM_PROVIDERS_PATH` 常量。

### Q: 如何添加新的字段验证？

A: 在 `_build_platform_schema` 或 `_build_llm_schema` 方法中添加字段的 `validation` 规则，包括：
- `min`: 最小值
- `max`: 最大值
- `pattern`: 正则表达式

### Q: 配置编辑器页面无法加载？

A: 检查：
1. 后端路由是否正确注册到 `app.py`
2. API端点是否可访问
3. 浏览器控制台是否有错误信息

### Q: 如何禁用配置编辑器？

A: 在 `MainRoutes.tsx` 中注释掉或删除 `ConfigEditorPage` 的路由配置：
```typescript
// const ConfigEditorPage = Loadable(lazy(() => import('views/config-editor')));
// {
//   path: 'config-editor',
//   element: <ConfigEditorPage />
// }
```

## 与现有页面的关系

- **platforms页面** (`views/platforms/index.tsx`): 用于快速添加/删除/启用平台
- **llm-providers页面** (`views/llm-providers/index.tsx`): 用于快速添加/删除/启用LLM提供商
- **config-editor页面** (`views/config-editor/index.tsx`): 提供详细的参数编辑

这三个页面可以共存，用户可以根据需要选择使用哪个页面进行配置。