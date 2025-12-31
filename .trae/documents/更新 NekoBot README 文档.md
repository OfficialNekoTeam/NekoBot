# 更新 NekoBot README 文档

## 主要更新内容

### 1. 支持的平台更新
- 添加新平台：飞书、KOOK、QQ频道、Slack、企业微信
- 更新平台列表表格

### 2. 支持的 LLM 提供商更新
- 添加新提供商：Claude、DeepSeek、DashScope、Moonshot、ZhipuAI
- 更新"已实现"和"后续准备"的区分

### 3. 新增核心功能
- **Agent 系统**：MCP 协议支持、函数调用、工具管理、Agent 执行引擎
- **知识库系统**：向量数据库、文档解析（PDF、Markdown、文本、URL）、检索增强
- **Pipeline 流水线**：洋葱模型调度器，支持多种 Stage（内容安全、速率限制、RAG 增强、会话摘要等）
- **更多功能**：会话隔离、状态管理、平台统计

### 4. 项目结构更新
- 添加 `packages/agent/` 目录
- 添加 `packages/core/knowledge_base/` 目录
- 更新 `packages/core/pipeline/` 的详细说明
- 添加 `packages/core/vector_db/` 目录

### 5. CLI 命令部分
- 将 CLI 命令从"路线图"移除，添加完整的命令说明
- 说明已实现的命令：reset-password、version、help

### 6. 路线图更新
- 移除已完成的"CLI 命令行工具"
- 移除已完成的"知识库集成"
- 更新为已实现的 Agent 系统、知识库系统等

### 7. 保持不变的部分
- 项目风格和格式
- 快速开始指南
- 开发规范
- 贡献指南
- 常见问题
- 致谢和联系方式

### 8. 删除内容
- API 文档部分（按要求不写）
