from __future__ import annotations

from typing import Any

# NekoBot 默认配置模板
# 该模板用于：
# 1. 自动初始化缺失的 config.json
# 2. 运行时检查配置完整性，自动补全缺失项
# 3. 为各个模块提供回退默认值

# NekoBot 基准配置 (用于完整性检查和自动纠错)
# 该项通常保持精简，仅包含核心结构，避免在用户合并配置时引入多余的占位符。
DEFAULT_CONFIG: dict[str, Any] = {
    "framework_config": {
        "web_host": "0.0.0.0",
        "web_port": 6285,
        "log_level": "INFO",
        "timezone": "Asia/Shanghai",
        "enable_webui": True,
        "api_flavor": "chat_completions",
    },
    "provider_configs": {},
    "platforms": [],
    "conversation_config": {
        "max_history_len": 50,
        "persistence_driver": "sqlite",
        "auto_summary_threshold": 20
    },
    "plugin_configs": {},
    "plugin_bindings": {},
    "permission_config": {
        "admin_users": [],
        "whitelist_groups": []
    },
    "moderation_config": {
        "enable": False,
        "keywords": []
    }
}

# NekoBot 初始模板 (仅在第一次生成 config.json 时使用)
# 包含丰富的注释引导和示例，方便新用户上手。
INITIAL_CONFIG_TEMPLATE: dict[str, Any] = {
    "framework_config": {
        "web_host": "0.0.0.0",
        "web_port": 6285,
        "log_level": "INFO",
        "timezone": "Asia/Shanghai",
        "enable_webui": True,
        "api_flavor": "chat_completions",
    },
    "provider_configs": {
        "openai": {
            "api_key": "YOUR_OPENAI_API_KEY",
            "default_model": "gpt-4o",
        },
        "anthropic": {
            "api_key": "YOUR_ANTHROPIC_API_KEY",
            "default_model": "claude-3-5-sonnet-latest",
        },
        "openai_compatible": {
            "api_key": "YOUR_API_KEY",
            "base_url": "https://api.deepseek.com/v1",
            "default_model": "deepseek-chat",
        }
    },
    "platforms": [
        {
            "type": "onebot_v11",
            "id": "qq_bot_1",
            "enable": True,
            "host": "127.0.0.1",
            "port": 6700,
            "protocol": "ws_reverse"
        }
    ],
    "conversation_config": {
        "max_history_len": 50,
        "persistence_driver": "sqlite",
        "auto_summary_threshold": 20
    },
    "permission_config": {
        "admin_users": ["12345678"],
        "whitelist_groups": []
    }
}
