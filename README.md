# NekoBot

<div align="center">

**多平台智能聊天机器人框架**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/NekoBotDevs/NekoBot)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-AGPL-3.0-orange.svg)](LICENSE)

一个功能强大、易于扩展的聊天机器人框架，支持多个聊天平台和 LLM 服务商

[功能特性](#功能特性) • [快速开始](#快速开始) • [文档](#文档) • [贡献](#贡献)

</div>

---

## 功能特性

### 核心功能

- **多平台支持**: 集成 12+ 主流聊天平台（QQ、Telegram、Discord、Slack、企业微信等）
- **多 LLM 支持**: 内置 OpenAI、Anthropic、Google Gemini 等 LLM 服务商
- **插件系统**: 完善的插件生态，支持热加载、热重载
- **Web 仪表盘**: 基于 Next.js 的现代化管理界面
- **实时日志**: WebSocket 实时日志推送
- **安全可靠**: JWT 认证、bcrypt 密码加密

### 技术亮点

- **异步架构**: 基于 Quart (异步 Flask)，高性能处理
- **模块化设计**: 清晰的架构，易于扩展和维护
- **配置管理**: 统一的配置管理器（NekoConfigManager）
- **数据持久化**: SQLite + SQLModel，轻量级数据存储

---

## 快速开始

### 环境要求

- Python 3.10+
- uv (推荐) 或 pip

### 安装

1. 克隆仓库
```bash
git clone https://github.com/NekoBotDevs/NekoBot.git
cd NekoBot
```

2. 安装依赖
```bash
# 使用 uv (推荐)
uv pip install -r requirements.txt

# 或使用 pip
pip install -r requirements.txt
```

3. 初始化
```bash
# 使用 CLI 工具初始化
uv run -m nekobot.cli.commands init

# 或直接运行（会自动初始化）
uv run main.py
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

## 项目结构

```
NekoBot/
├── nekobot/                    # 核心框架代码
│   ├── auth/                   # JWT 认证系统
│   ├── config/                 # 配置管理
│   ├── database/               # 数据库模型
│   ├── llm/                    # LLM 服务商集成
│   ├── plugin/                 # 插件系统
│   ├── web/                    # Web 服务和 API
│   ├── cli/                    # CLI 命令行工具
│   ├── core/                   # 核心模块
│   └── utils/                  # 工具函数
│
├── dashboard/                  # Next.js 前端仪表盘
├── data/                       # 数据存储目录
│   ├── plugins/                # 用户插件
│   ├── dist/                   # 前端编译产物
│   ├── config.json             # 配置文件
│   └── nekobot.db             # 数据库
│
├── packages/                   # 官方插件
├── main.py                     # 主入口
├── pyproject.toml             # 项目配置
└── requirements.txt           # 依赖列表
```

---

## CLI 命令

```bash
# 查看版本
nekobot-cli version

# 检查更新
nekobot-cli check

# 重置密码
nekobot-cli reset-passwd

# 初始化项目
nekobot-cli init

# 查看帮助
nekobot-cli --help
```

---

## API 文档

完整的 API 文档请查看：[API-Doc.md](LLM/API-Doc.md)

### 主要 API 端点

- **认证**: `/api/auth/*`
- **插件管理**: `/api/plugins/*`
- **LLM 管理**: `/api/llm/*`
- **配置管理**: `/api/config/*`
- **系统信息**: `/api/system/*`
- **实时日志**: `ws://host:port/ws`

---

## 插件开发

### 插件结构

```
my_plugin/
├── main.py              # 插件主程序
├── metadata.yaml        # 元数据
├── requirements.txt     # 依赖（可选）
└── README.md           # 说明文档（可选）
```

### 最小示例

**metadata.yaml**:
```yaml
name: MyPlugin
version: 1.0.0
description: 我的第一个插件
author: Your Name
repository: https://github.com/yourusername/MyPlugin
```

**main.py**:
```python
from nekobot.plugin.base import PluginBase

class MyPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "MyPlugin"
        self.version = "1.0.0"
    
    async def register(self) -> bool:
        # 插件注册逻辑
        print("MyPlugin 已注册")
        return True
    
    async def unregister(self) -> bool:
        # 插件卸载逻辑
        print("MyPlugin 已卸载")
        return True
```

详细文档: [插件开发指南](LLM/Project.md#插件系统)

---

## 支持的平台

### 已集成平台

- QQ (OneBot V11)
- QQ 官方接口
- Telegram
- Discord
- Slack
- 钉钉 (DingTalk)
- 飞书 (Lark)
- 企业微信 (WeCom)
- 微信 (WechatPadPro)
- 微信公众号
- Satori 协议
- WebChat (网页聊天)

---

## 支持的 LLM

- **OpenAI** (GPT-3.5, GPT-4, GPT-4 Turbo 等)
- **Anthropic** (Claude 系列)
- **Google** (Gemini 系列)
- **自定义服务商** (兼容 OpenAI API 格式)

---

## 配置说明

主配置文件位于 `./data/config.json`

### 主要配置项

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 6285,
    "cors_origins": ["*"]
  },
  "bot": {
    "command_prefix": "/"
  },
  "logging": {
    "level": "INFO"
  }
}
```

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

使用 CLI 工具重置：
```bash
nekobot-cli reset-passwd
```

### 3. 如何添加新的 LLM 服务商？

通过 Web 仪表盘或 API 添加：
```bash
POST /api/llm/providers
{
  "name": "my-llm",
  "provider_type": "openai",
  "api_keys": ["sk-..."],
  "model": "gpt-4"
}
```

### 4. 插件如何热重载？

```bash
POST /api/plugins/<plugin_name>/reload
```

---

## 路线图

- [ ] 更多平台适配器
- [ ] 插件市场
- [ ] 对话历史管理
- [ ] 知识库集成
- [ ] Docker 部署支持
- [ ] 多语言支持

---

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

---

## 致谢

- 参考项目：[AstrBot](https://github.com/AstrBotDevs/AstrBot)
- 所有贡献者

---

## 联系方式

- GitHub Issues: [提交问题](https://github.com/NekoBotDevs/NekoBot/issues)
- 文档: [查看文档](LLM/Project.md)

---

<div align="center">

**如果这个项目对你有帮助，请给个 Star ⭐**

Made with ❤️ by NekoBotTeam

</div>

