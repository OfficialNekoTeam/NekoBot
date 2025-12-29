# NekoBot

<div align="center">

**多平台智能聊天机器人框架**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/NekoBotTeam/NekoBot)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-AGPL-3.0-orange.svg)](LICENSE)

一个功能强大、易于扩展的聊天机器人框架，支持多个聊天平台和 LLM 服务商

[功能特性](#功能特性) • [快速开始](#快速开始) • [文档](#文档) • [贡献](#贡献)

</div>

---

## 功能特性

### 核心功能

- **多平台支持**: 支持 QQ、Telegram、Discord 等主流聊天平台
- **多 LLM 支持**: 集成 OpenAI、Google Gemini 等 LLM 服务商
- **插件系统**: 完善的插件生态，支持热加载、热重载
- **Web 仪表盘**: 基于 React + Vite 的现代化管理界面
- **实时日志**: WebSocket 实时日志推送
- **安全可靠**: JWT 认证、bcrypt 密码加密

### 技术亮点

- **异步架构**: 基于 Quart (异步 Flask)，高性能处理
- **模块化设计**: 清晰的架构，易于扩展和维护
- **消息流水线**: 可扩展的消息处理管道机制
- **数据持久化**: SQLite 轻量级数据存储

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

## 项目结构

```
NekoBot/
├── dashboard/                  # React+Vite 前端仪表盘
│   ├── src/                    # 源代码
│   │   ├── components/         # UI 组件
│   │   ├── context/            # 上下文管理
│   │   ├── pages/              # 页面组件
│   │   └── utils/              # 工具函数
│   └── package.json            # 前端依赖
│
├── docs/                       # 文档目录
│
├── packages/                   # 核心后端代码
│   └── backend/                # 后端框架
│       ├── auth/               # JWT 认证系统
│       ├── core/               # 核心模块
│       │   └── pipeline/       # 消息处理流水线
│       ├── llm/                # LLM 服务商集成
│       ├── platform/           # 平台适配器
│       │   └── sources/        # 各平台实现
│       ├── plugins/            # 插件系统
│       └── routes/             # API 路由
│
├── data/                       # 数据存储目录（Git 忽略）
│   ├── plugins/                # 用户插件
│   ├── config.json             # 配置文件
│   └── nekobot.db             # 数据库
│
├── main.py                     # 主入口
├── pyproject.toml             # 项目配置
├── docker-compose.yaml        # Docker 部署配置
├── compose.yaml                # Compose 配置
└── LICENSE                     # AGPL-3.0 许可证
```

---

## CLI 命令

当前版本暂未提供完整的 CLI 工具，请通过 Web 仪表盘进行管理。

---

## API 文档

### 主要 API 端点

- **认证**: `/api/auth/*`
- **插件管理**: `/api/plugins/*`
- **LLM 管理**: `/api/llm/*`
- **平台管理**: `/api/platforms/*`
- **配置管理**: `/api/config/*`
- **实时日志**: `ws://host:port/ws`

---

## 插件开发

想要开发插件? 请参考项目[https://github.com/NekoBotTeam/NekoBot_Plugins_Example](https://github.com/NekoBotTeam/NekoBot_Plugins_Example)

---

## 支持的平台

### 已集成平台

- **QQ** (OneBot V11)
- **Discord**
- **Telegram**

---

## 支持的 LLM

- **OpenAI** (GPT-3.5, GPT-4, GPT-4o 等)
- **Google** (Gemini 系列)

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
- [ ] 更多平台适配器
- [ ] CLI 命令行工具
- [ ] 插件市场
- [ ] 知识库集成
- [ ] 多语言支持

---

## 许可证

本项目采用 AGPL-3.0 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

---

## 致谢

- 参考项目：[AstrBot](https://github.com/AstrBotDevs/AstrBot)
- 所有贡献者

---

## 联系方式

- GitHub Issues: [提交问题](https://github.com/NekoBotTeam/NekoBot/issues)

---

<div align="center">

**如果这个项目对你有帮助，请给个 Star ⭐**

Made with ❤️ by NekoBotTeam
</div>
