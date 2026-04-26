# NekoBot

<div align="center">

**多平台智能聊天机器人框架**

(目前项目正在处于初始阶段，因此版本号在发布正式版本之前一直保持大版本为 0.x.x。本项目遵循 [语义化版本 2.0](https://semver.org/lang/zh-CN/) 规范。有问题请及时反馈至 Issue)

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/OfficialNekoTeam/NekoBot)
[![Python](https://img.shields.io/badge/python-3.13+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-AGPL-3.0-orange.svg)](LICENSE)

一个功能强大、易于扩展的聊天机器人框架，支持多个聊天平台和 LLM 服务商

[功能特性](#功能特性) • [快速开始](#快速开始) • [文档](#文档) • [贡献](#贡献)

</div>

---

## 功能特性

### 核心功能

- 🚀 **完全异步架构** - 基于 asyncio，支持高并发消息处理
- 🔌 **模块化插件系统** - 支持热加载、热重载，GitHub 一键安装
- 🤖 **多 LLM 服务商** - 支持 OpenAI、Anthropic、Google Gemini 等，灵活切换
- 💾 **会话管理** - SQLite 持久化，多种隔离模式（全局/范围/平台/用户）
- 🔐 **权限控制** - 细粒度权限引擎，支持角色和作用域分离
- 🛡️ **内容审核** - 输入/输出/最终发送多阶段审核
- 🎯 **事件驱动** - 灵活的事件处理和分发机制
- 📋 **配置驱动** - JSON 配置文件，无需重启即可热更新
- 🔄 **依赖注入** - 框架级依赖注入，易于测试和扩展
- 🧠 **上下文协议支持** - 集成 MCP (Model Context Protocol)

---

## 📚 文档说明

> ⚠️ **注意**: 官方文档目前更新略有滞后，本 README 中的功能说明为最新实现。详细的架构设计、API 文档和扩展指南将在后续持续更新。欢迎提交 Issue 反馈或贡献文档！

---

## 快速开始

### 环境要求

- Python 3.13+
- uv (推荐) 或 pip
- 网络连接（用于 LLM 服务调用）

### 安装

1. 克隆仓库
```bash
git clone https://github.com/OfficialNekoTeam/NekoBot.git
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

### WebUI 管理面板

启动后默认在 `http://0.0.0.0:6285` 提供 Web 管理界面，支持：

- **LLM 提供商管理** - 可视化表单配置 OpenAI / Anthropic / Gemini / OpenAI Compatible
- **插件管理** - 启用/禁用、热重载、配置编辑
- **MCP 服务器** - 管理 Model Context Protocol 工具服务
- **人格管理** - 管理机器人 Prompt 人格
- **系统信息** - 实时状态、日志查看
- **知识库** - 知识库与文档管理

> ⚠️ **端口注意**：WebUI 默认占用 `6285`，OneBot V11 适配器默认占用 `6299`，两者不能使用同一端口。若在配置文件中手动为两者指定了相同端口，启动时将报 `Address already in use` 错误。

### 启动参数

```
usage: main.py [--webui | --no-webui] [--config PATH] [--host HOST] [--port PORT]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--webui` / `--no-webui` | 启用或禁用 WebUI 管理面板 | 启用 |
| `--config PATH` | 指定配置文件路径 | `data/config.json` |
| `--host HOST` | WebUI 监听地址 | `0.0.0.0` |
| `--port PORT` | WebUI 监听端口 | `6285` |

### 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `NEKOBOT_WEBUI` | 控制 WebUI 开关（`0/false/no/off` 禁用，`1/true/yes/on` 启用） | `NEKOBOT_WEBUI=false` |
| `NEKOBOT_HOST` | WebUI 监听地址（同 `--host`） | `NEKOBOT_HOST=127.0.0.1` |
| `NEKOBOT_PORT` | WebUI 监听端口（同 `--port`） | `NEKOBOT_PORT=8080` |
| `NEKOBOT_LOG_DIR` | 日志文件目录 | `NEKOBOT_LOG_DIR=logs` |
| `NEKOBOT_CORS_ORIGINS` | 允许的 CORS 来源，逗号分隔；`*` 表示不限制（仅开发环境） | `NEKOBOT_CORS_ORIGINS=http://localhost:3000` |

**优先级**：命令行参数 > 环境变量 > `config.json` 中的 `framework_config` > 内置默认值

### 配置文件（`framework_config` 节）

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `web_host` | string | WebUI 监听地址 | `"0.0.0.0"` |
| `web_port` | int | WebUI 监听端口 | `6285` |
| `enable_webui` | bool | 是否启用 WebUI | `true` |
| `log_level` | string | 日志级别（`DEBUG/INFO/WARNING/ERROR`） | `"INFO"` |
| `timezone` | string | 时区 | `"Asia/Shanghai"` |
| `api_flavor` | string | LLM API 风格（`chat_completions`） | `"chat_completions"` |

---

## 插件开发

想要开发插件? 请参考项目[https://github.com/OfficialNekoTeam/nekobot_plugin_template](https://github.com/OfficialNekoTeam/nekobot_plugin_template)

---

## 支持的平台

### 已集成平台

| 平台 | 协议/类型 | 描述 | 流式消息 |
|------|----------|------|---------|
| **QQ** | OneBot V11 | 通过 aiocqhttp 实现 | 否 |

---

## 支持的 LLM 提供商

| 提供商 | 支持模型 | 功能 |
|--------|---------|------|
| **OpenAI** | GPT-4, GPT-4 Turbo, GPT-3.5-Turbo | 聊天、函数调用 |
| **Anthropic** | Claude 3 Opus, Claude 3 Sonnet, Claude 3 Haiku | 聊天、函数调用 |
| **Google Gemini** | Gemini Pro, Gemini 1.5 Pro | 聊天、多模态 |
| **OpenAI Compatible** | 自定义 API 端点 | 聊天（支持本地模型）|
| **OpenAI TTS** | tts-1, tts-1-hd | 文本转语音 |
| **OpenAI STT** | Whisper | 语音转文本 |
| **Edge TTS** | - | 免费文本转语音 |

---

## 架构设计

```
┌─ 平台层 ──────────────────────────────┐
│  OneBot v11 Adapter                   │
│  Transport/Parser/Codec               │
└─────────────────┬──────────────────────┘
                  │
┌─────────────────▼──────────────────────┐
│  框架层 (NekoBotFramework)            │
│  - RuntimeRegistry                     │
│  - ContextBuilder                      │
│  - PluginManager                       │
│  - PermissionEngine                    │
│  - ModerationService                   │
│  - ProviderRegistry                    │
└─────────────────┬──────────────────────┘
                  │
┌─────────────────▼──────────────────────┐
│  业务层 (Plugins)                      │
│  - 用户自定义插件                     │
│  - 事件处理                            │
│  - LLM 调用                            │
└────────────────────────────────────────┘
```

## 路线图

- [x] QQ (OneBot V11) 支持
- [x] 多 LLM 服务商集成
- [x] 插件热加载系统
- [x] 权限和会话管理
- [x] WebUI 管理面板（提供商/插件/MCP/人格/日志/知识库）
- [ ] 更多平台适配器 (Telegram, Discord 等)
- [ ] 知识库/RAG 功能
- [ ] 监控和指标系统
- [ ] 插件市场

---

## 许可证

本项目采用 AGPL-3.0 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

---

## 致谢

- 参考项目：
    - [AstrBot](https://github.com/AstrBotDevs/AstrBot) - 部分机制参考
    - [NapNeko/NapCatQQ](https://github.com/NapNeko/NapCatQQ) - 伟大的困困猫框架
- 所有贡献者

---

## 联系方式

- [提交问题Issue](https://github.com/OfficialNekoTeam/NekoBot/issues)
- [更多联系方式请看文档底部](https://docs.nekobot.dev/)

---

<div align="center">

## ⭐ Star 历史
<a href="https://www.star-history.com/?repos=OfficialNekoTeam%2FNekoBot&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=OfficialNekoTeam/NekoBot&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=OfficialNekoTeam/NekoBot&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=OfficialNekoTeam/NekoBot&type=date&legend=top-left" />
 </picture>
</a>

**如果这个项目对你有帮助，请给个 Star ⭐**

Made with ❤️ by OfficialNekoTeam
</div>
