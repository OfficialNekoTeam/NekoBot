# Neko 项目优化计划

基于对 AstrBot 的对比分析，建议对 Neko 项目进行以下优化：

## 核心优化项

### 1. 数据库层重构
- 引入 SQLAlchemy + aiosqlite 实现异步数据库操作
- 添加平台统计功能（platform_stats 表）
- 实现数据库迁移管理机制

### 2. Provider 类型扩展
- 添加 STTProvider（语音转文本）
- 添加 TTSProvider（文本转语音）
- 添加 EmbeddingProvider（嵌入向量）
- 添加 RerankProvider（重排序）

### 3. 知识库增强
- 完善检索管理器实现
- 支持 RankFusion 融合检索
- 完善 PDF、Markdown、URL 文档解析
- 支持多种分块策略（固定大小、递归）

### 4. Agent 系统优化
- 优化 Agent 基类设计，支持泛型上下文
- 改进工具执行器，支持异步生成器
- 深化 MCP（Model Context Protocol）集成

### 5. 统计与指标系统
- 添加统一的 Metric 类，支持指标上传
- 实现平台消息统计功能
- 支持安装 ID 跟踪

### 6. CLI 工具增强
- 引入 click 框架实现更强大的 CLI
- 添加 init、conf、plug、run 等子命令
- 支持版本管理

### 7. 平台适配器增强
- 添加 webhook_callback 方法支持统一 Webhook
- 添加 get_client 方法
- 完善 Slack 适配器，支持 Socket Mode 和 Webhook Mode

### 8. 配置系统优化
- 添加配置完整性检查
- 支持从 Schema 生成默认配置
- 支持配置版本管理和自动迁移

## 优化优先级
1. **高优先级**：数据库层重构、Provider 扩展
2. **中优先级**：知识库增强、Agent 系统优化
3. **低优先级**：CLI 增强、配置系统优化

**注意**：不包含 i18n（国际化）优化，该功能在独立仓库中实现。