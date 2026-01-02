# NekoBot

<div align="center">

**多平台智能聊天机器人框架**

(目前项目正在处于初始阶段，因此版本号在发布正式版本之前一直为 1.0.0，有问题请及时反馈至Issue)

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/NekoBotTeam/NekoBot)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-AGPL-3.0-orange.svg)](LICENSE)

一个功能强大、易于扩展的聊天机器人框架，支持多个聊天平台和 LLM 服务商

[功能特性](#功能特性) • [快速开始](#快速开始) • [文档](#文档) • [贡献](#贡献)

</div>

---

## 功能特性

### 核心功能

- **多平台支持**: 支持 QQ、Telegram、Discord、飞书、KOOK、QQ频道、Slack、企业微信等主流聊天平台
- **多 LLM 支持**: 集成 OpenAI、Google Gemini、Claude、DeepSeek、DashScope、Moonshot、ZhipuAI 等 LLM 服务商
- **插件系统**: 完善的插件生态，支持热加载、热重载
- **Web 仪表盘**: 基于 React + Vite 的现代化管理界面
- **实时日志**: WebSocket 实时日志推送
- **安全可靠**: JWT 认证、bcrypt 密码加密
- **Agent 系统**: 支持 MCP 协议、函数调用和工具管理
- **知识库系统**: 支持向量数据库、文档解析和检索增强（RAG）
- **消息流水线**: 洋葱模型的消息处理管道，支持多种处理阶段

### 技术亮点

- **异步架构**: 基于 Quart (异步 Flask)，高性能处理
- **模块化设计**: 清晰的架构，易于扩展和维护
- **消息流水线**: 可扩展的消息处理管道机制
- **数据持久化**: SQLite 轻量级数据存储
- **会话隔离**: 支持会话级别的数据隔离
- **状态管理**: 完善的会话状态管理系统

---

## 快速开始

### 环境要求

- Python 3.10+
- uv (推荐) 或 pip

### 安装

1. 克隆仓库
```bash
git clone https://github.com/NekoBotTeam/NekoBot.git
cd NekoBot
```

2. 安装依赖
```bash
# 使用 uv (推荐)
uv pip install -e .

# 或使用 pip
pip install -e .
```

3. 启动
```bash
# 使用 uv
uv run main.py

# 或使用 python
python main.py
```

### 启动

```bash
# 使用 uv
uv run main.py

# 或使用 python
python main.py
```

启动后访问: `http://localhost:6285`

### 默认账户

- **用户名**: `nekobot`
- **密码**: `nekobot`

首次登录后会强制要求修改密码。

---

## 项目统计

- **Python 文件数量**: 14,944 个
- **代码总行数**: 1,616,762 行

## 项目结构

前端项目已移至独立仓库：[NekoBot-Dashboard](https://github.com/NekoBotTeam/NekoBot-Dashboard)，基于 [Breey](https://github.com/codedthemes/berry-free-react-admin-template) 模板开发。

```
NekoBot/
├── packages/                   # 核心后端代码
│   ├── agent/                  # Agent 系统
│   │   ├── mcp/                # MCP 协议支持
│   │   │   ├── client.py       # MCP 客户端
│   │   │   └── server.py       # MCP 服务端
│   │   ├── tools/              # 工具注册和管理
│   │   │   ├── base.py         # 工具基类
│   │   │   ├── function_tool.py # 函数工具
│   │   │   ├── handoff_tool.py # 交接工具
│   │   │   └── registry.py     # 工具注册表
│   │   ├── base.py             # Agent 基类
│   │   ├── base_new.py         # 新版 Agent 基类
│   │   ├── executor.py         # Agent 执行引擎
│   │   ├── hooks.py            # 生命周期钩子
│   │   ├── tool_system.py      # 工具系统
│   │   └── tools.py            # 工具集合
│   │
│   ├── auth/                   # JWT 认证系统
│   │   ├── hash.py             # 密码哈希
│   │   ├── jwt.py              # JWT 令牌
│   │   └── user.py             # 用户模型
│   │
│   ├── config/                 # 配置管理
│   │   └── manager.py          # 配置管理器
│   │
│   ├── conversation/           # 对话管理
│   │   └── manager.py          # 对话管理器
│   │
│   ├── core/                   # 核心模块
│   │   ├── knowledge_base/     # 知识库系统
│   │   │   ├── chunking/       # 文档分块策略
│   │   │   │   ├── base.py     # 分块基类
│   │   │   │   ├── fixed_size.py # 固定大小分块
│   │   │   │   └── recursive.py # 递归分块
│   │   │   ├── parsers/        # 文档解析器
│   │   │   │   ├── base.py     # 解析器基类
│   │   │   │   ├── markdown_parser.py # Markdown 解析
│   │   │   │   ├── pdf_parser.py # PDF 解析
│   │   │   │   ├── text_parser.py # 文本解析
│   │   │   │   └── url_parser.py # URL 解析
│   │   │   ├── retrieval/      # 检索和排序
│   │   │   │   ├── manager.py  # 检索管理器
│   │   │   │   ├── parse_retriever.py # 解析检索
│   │   │   │   ├── rank_fusion.py # 排序融合
│   │   │   │   └── sparse_retriever.py # 稀疏检索
│   │   │   ├── kb_manager.py   # 知识库管理器
│   │   │   └── models.py       # 数据模型
│   │   ├── pipeline/           # 消息处理流水线
│   │   │   ├── scheduler.py    # 洋葱模型调度器
│   │   │   ├── scheduler_new.py # 新版调度器
│   │   │   ├── stage.py        # 阶段基类
│   │   │   ├── context.py      # 上下文管理
│   │   │   ├── content_safety_check_stage.py # 内容安全检查
│   │   │   ├── event_stopper.py # 事件停止器
│   │   │   ├── process_stage.py # 处理阶段
│   │   │   ├── rag_enhance_stage.py # RAG 增强
│   │   │   ├── rate_limit_stage.py # 限流
│   │   │   ├── respond_stage.py # 响应阶段
│   │   │   ├── result_decorate_stage.py # 结果装饰
│   │   │   ├── session_status_check_stage.py # 会话状态检查
│   │   │   ├── session_summary_stage.py # 会话摘要
│   │   │   ├── waking_check_stage.py # 唤醒检查
│   │   │   └── whitelist_check_stage.py # 白名单检查
│   │   ├── vector_db/          # 向量数据库
│   │   │   ├── base.py         # 向量库基类
│   │   │   └── in_memory.py    # 内存向量库
│   │   ├── command_management.py # 命令管理
│   │   ├── config_reload_manager.py # 配置重载管理
│   │   ├── config.py           # 核心配置
│   │   ├── context_manager.py  # 上下文管理器
│   │   ├── database.py         # 数据库管理
│   │   ├── event_bus.py        # 事件总线
│   │   ├── hot_reload_manager.py # 热重载管理
│   │   ├── knowledge_base.py   # 知识库接口
│   │   ├── lifecycle.py        # 生命周期管理
│   │   ├── metrics.py          # 指标统计
│   │   ├── migration.py        # 数据迁移
│   │   ├── platform_server.py  # 平台服务
│   │   ├── platform_stats.py   # 平台统计
│   │   ├── plugin_manager.py   # 插件管理
│   │   ├── prompt_manager.py   # 提示词管理
│   │   ├── server.py           # 服务器
│   │   ├── session_isolation.py # 会话隔离
│   │   ├── session_manager.py  # 会话管理
│   │   ├── version.py          # 版本信息
│   │   └── webui_manager.py    # WebUI 管理
│   │
│   ├── llm/                    # LLM 服务商集成
│   │   ├── sources/            # 各 LLM 提供商实现
│   │   │   ├── claude_provider.py # Claude
│   │   │   ├── dashscope_provider.py # 阿里云通义千问
│   │   │   ├── deepseek_provider.py # DeepSeek
│   │   │   ├── gemini_provider.py # Google Gemini
│   │   │   ├── glm_provider.py # 智谱 GLM
│   │   │   ├── lm_studio_provider.py # LM Studio
│   │   │   ├── moonshot_provider.py # Moonshot
│   │   │   ├── ollama_provider.py # Ollama
│   │   │   ├── openai_compatible_provider.py # OpenAI 兼容
│   │   │   ├── openai_provider.py # OpenAI
│   │   │   └── zhipu_provider.py # 智谱 AI
│   │   ├── base.py             # LLM 基类
│   │   ├── context_manager.py  # 上下文管理
│   │   ├── dynamic_register.py # 动态注册
│   │   ├── embedding_base.py   # 嵌入基类
│   │   ├── entities.py         # 实体定义
│   │   ├── register.py         # LLM 注册
│   │   ├── rerank_base.py      # 重排序基类
│   │   ├── stt_base.py         # 语音转文字基类
│   │   ├── tool_integration.py # 工具集成
│   │   └── tts_base.py         # 文字转语音基类
│   │
│   ├── platform/               # 平台适配器
│   │   ├── sources/            # 各平台实现
│   │   │   ├── aiocqhttp/      # QQ (OneBot V11)
│   │   │   ├── discord/        # Discord
│   │   │   ├── kook/           # KOOK
│   │   │   ├── lark/           # 飞书
│   │   │   ├── qqchannel/      # QQ频道
│   │   │   ├── slack/          # Slack
│   │   │   ├── telegram/       # Telegram
│   │   │   └── wecom/          # 企业微信
│   │   ├── base.py             # 平台基类
│   │   ├── manager.py          # 平台管理器
│   │   ├── metadata.py         # 元数据
│   │   └── register.py         # 平台注册
│   │
│   ├── plugins/                # 插件系统
│   │   ├── filters/            # 权限过滤器
│   │   │   ├── base.py         # 过滤器基类
│   │   │   └── permission_filter.py # 权限过滤器
│   │   ├── base.py             # 插件基类
│   │   ├── dependency_manager.py # 依赖管理
│   │   ├── example_plugin.py   # 示例插件
│   │   ├── hot_reload.py       # 热重载
│   │   ├── metadata.py         # 插件元数据
│   │   └── plugin_data_manager.py # 插件数据管理
│   │
│   ├── pipeline/               # 流水线系统
│   │   └── scheduler_new.py    # 新版调度器
│   │
│   └── routes/                 # API 路由
│       ├── agent_route.py      # Agent 路由
│       ├── auth_route.py       # 认证路由
│       ├── backup_route.py     # 备份路由
│       ├── bot_config.py       # 机器人配置
│       ├── chat_route.py       # 聊天路由
│       ├── command_route.py    # 命令路由
│       ├── config_profile_route.py # 配置档案路由
│       ├── conversation_route.py # 对话路由
│       ├── dynamic_route_manager.py # 动态路由管理
│       ├── hot_reload_route.py # 热重载路由
│       ├── knowledge_base_route.py # 知识库路由
│       ├── llm_route.py        # LLM 路由
│       ├── log_route.py        # 日志路由
│       ├── long_term_memory_route.py # 长期记忆路由
│       ├── mcp_route.py        # MCP 路由
│       └── plugin_route.py      # 插件路由
│
├── .github/                    # GitHub 配置
├── main.py                     # 主入口
├── pyproject.toml             # 项目配置
├── Dockerfile                 # Docker 构建文件
├── docker-compose.yaml        # Docker 部署配置
├── compose.yaml                # Compose 配置
├── .dockerignore              # Docker 忽略文件
├── .gitignore                 # Git 忽略文件
├── .python-version            # Python 版本
├── clean_pycache.py           # 清理缓存脚本
└── LICENSE                     # AGPL-3.0 许可证
```

---

## CLI 命令

NekoBot 提供了命令行工具，用于管理和操作 NekoBot。

### 可用命令

| 命令 | 说明 |
|------|------|
| (默认) | 启动 NekoBot 服务器 |
| `reset-password` | 重置 WebUI 默认账户密码 |
| `version`, `-v` | 显示版本信息 |
| `help`, `-h` | 显示帮助信息 |

### 使用示例

```bash
# 启动 NekoBot 服务器
uv run main.py
python main.py

# 重置密码
uv run main.py reset-password
python main.py reset-password

# 显示版本信息
uv run main.py version
uv run main.py -v

# 显示帮助信息
uv run main.py help
uv run main.py -h
```

### 重置密码

运行重置密码命令后，按照提示输入两次新密码：

```bash
uv run main.py reset-password
```

> ⚠️ **安全提示**
>
> - 输入密码时无任何回显提示，直接输入密码后回车即可
> - NekoBot 首次登录时会强制要求修改默认密码
> - 如因未修改默认密码导致安全问题，开发团队不承担责任

---

## 插件开发

想要开发插件? 请参考项目[https://github.com/NekoBotTeam/NekoBot_Plugins_Example](https://github.com/NekoBotTeam/NekoBot_Plugins_Example)

---

## 支持的平台

### 已集成平台

| 平台 | 协议/类型 | 描述 | 流式消息 |
|------|----------|------|---------|
| **QQ** | OneBot V11 | 通过 aiocqhttp 实现 | 否 |
| **Discord** | Discord Bot API | Discord 机器人 | 否 |
| **Telegram** | Telegram Bot API | Telegram 机器人 | 是 |
| **飞书** | 飞书官方 API | 飞书群聊和私聊 | 否 |
| **KOOK** | 开黑平台 | KOOK 频道和私聊 | 是 |
| **QQ频道** | QQ频道官方 API | QQ 频道 | 是 |
| **Slack** | Slack Bot API | Slack 工作区 | 否 |
| **企业微信** | 企业微信官方 API | 企业微信应用 | 否 |

---

## 支持的 LLM 提供商

NekoBot 目前支持以下 LLM 提供商：

| 提供商 | 描述 | 支持的模型 |
|--------|------|-----------|
| **OpenAI** | OpenAI GPT 系列 | gpt-4o, gpt-4o-mini, gpt-3.5-turbo |
| **Google Gemini** | Google Gemini 系列 | gemini-2.0-flash-exp, gemini-1.5-pro, gemini-1.5-flash |
| **Claude** | Anthropic Claude 系列 | claude-3-5-sonnet-20241022, claude-3-5-haiku-20241022 |
| **DeepSeek** | DeepSeek 系列 | deepseek-chat, deepseek-coder |
| **DashScope** | 阿里云通义千问 | qwen-max, qwen-plus, qwen-turbo |
| **Moonshot** | Moonshot Kimi 系列 | moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k |
| **ZhipuAI** | 智谱 GLM 系列 | glm-4, glm-4-flash, glm-4-plus |
| **OpenAI 兼容** | OpenAI 兼容接口 | 适用于 Ollama、LM Studio 等 |

---

## 开发规范

### 代码格式化

使用 Ruff 进行代码检查：

```bash
ruff check .
```

### 规范要求

- 最大行长：88
- Python 版本：3.10+
- 编码：UTF-8（无 BOM）
- 禁止使用 emoji（除非明确需求）

---

## 贡献指南

我们欢迎任何形式的贡献！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 贡献规范

- 遵循项目代码风格
- 添加必要的测试
- 更新相关文档
- 使用中文编写注释和文档

---

## 常见问题

### 1. 如何修改默认端口？

编辑 `./data/config.json`，修改 `server.port` 字段。

### 2. 忘记密码怎么办？

可通过运行以下命令重置密码：

```bash
# 使用 uv
uv run main.py reset-password

# 或使用 python
python main.py reset-password
```

按照提示输入两次新密码，密码重置成功后即可使用新密码登录。

> ⚠️ **安全警告**
>
> NekoBot 首次登录时会强制要求修改密码。如果用户未修改默认密码而导致的安全问题，开发团队不承担责任。
>
> 重置密码时输入密码时无任何回显提示，直接输入密码后回车即可。

### 3. 如何添加新的 LLM 服务商？

通过 Web 仪表盘添加。

### 4. 插件如何热重载？

通过 Web 仪表盘重新加载插件。

---

## 路线图

- [x] QQ (OneBot V11) 支持
- [x] Discord 支持
- [x] Telegram 支持
- [x] 飞书 支持
- [x] KOOK 支持
- [x] QQ频道 支持
- [x] Slack 支持
- [x] 企业微信 支持
- [x] Agent 系统
- [x] 知识库系统
- [x] Pipeline 流水线
- [x] CLI 命令行工具
- [ ] 更多平台适配器
- [ ] 插件市场
- [ ] 多语言支持

---

## 许可证

本项目采用 AGPL-3.0 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

---

## 致谢

- 参考项目：

    - [AstrBot](https://github.com/AstrBotDevs/AstrBot)
    - [NapNeko/NapCatQQ](https://github.com/NapNeko/NapCatQQ) - 伟大的猫猫框架
- 所有贡献者

---

## 联系方式

- GitHub Issues: [提交问题Issue](https://github.com/NekoBotTeam/NekoBot/issues)

---

<div align="center">

**如果这个项目对你有帮助，请给个 Star ⭐**

Made with ❤️ by NekoBotTeam
</div>
