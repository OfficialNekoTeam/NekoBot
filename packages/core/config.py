"""配置加载模块

读取 data/cmd_config.json 和 data/platforms_sources.json 并提供全局配置对象
"""

import json
from pathlib import Path
from typing import Dict, Any

# 项目根目录下的 data/cmd_config.json
CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "cmd_config.json"

# CORS 配置文件路径（用于 WebUI 跨域设置）
CORS_CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "config.json"

# LLM 提供商配置文件路径
LLM_PROVIDERS_PATH = Path(__file__).parent.parent.parent / "data" / "llm_providers.json"

# 平台源配置文件路径
PLATFORMS_SOURCES_PATH = Path(__file__).parent.parent.parent / "data" / "platforms_sources.json"


def load_cors_config() -> Dict[str, Any]:
    """加载 CORS 配置

    Returns:
        CORS 配置字典，包含 allow_origin 等设置
    """
    default_config = {
        "allow_origin": "*",
        "allow_headers": ["Content-Type", "Authorization"],
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    }

    if not CORS_CONFIG_PATH.exists():
        try:
            with open(CORS_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return default_config

    try:
        with open(CORS_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
            return {**default_config, **config}
    except Exception:
        return default_config


def load_config() -> Dict[str, Any]:
    """加载配置文件，如果不存在返回默认配置"""
    if not CONFIG_PATH.exists():
        config = {
            "command_prefix": "/",
            "server": {"host": "0.0.0.0", "port": 6285},
            "jwt": {
                "secret_key": "",
                "algorithm": "HS256",
                "access_token_expire_minutes": 30,
            },
            "webui_enabled": True,
            "webui_api_enabled": True,
            "demo": False,
            "github_proxy": None,
            "webui_version": None,
            "cors": load_cors_config(),
            # LLM 回复模式: "active" (主动), "passive" (被动), "at" (艾特), "command" (命令)
            "llm_reply_mode": "active",
            # 唤醒前缀配置（参考 AstrBot）
            "wake_prefix": ["/", "."],
            # 私聊是否需要唤醒前缀（参考 AstrBot）
            "private_message_needs_wake_prefix": False,
            # 是否忽略艾特全体成员
            "ignore_at_all": False,
        }
    else:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            raise RuntimeError(f"加载配置文件失败: {e}")

    if "cors" not in config:
        config["cors"] = load_cors_config()

    if "webui_api_enabled" not in config:
        config["webui_api_enabled"] = True

    # 添加唤醒前缀默认配置（如果不存在）
    if "wake_prefix" not in config:
        config["wake_prefix"] = ["/", "."]

    if "private_message_needs_wake_prefix" not in config:
        config["private_message_needs_wake_prefix"] = False

    if "ignore_at_all" not in config:
        config["ignore_at_all"] = False

    # 合并平台源配置
    config["platforms"] = load_platforms_sources()

    # 合并 LLM 提供商配置
    config["llm_providers"] = load_llm_providers()

    return config


def load_llm_providers() -> Dict[str, Any]:
    """加载 LLM 提供商配置"""
    if not LLM_PROVIDERS_PATH.exists():
        return {}
    try:
        with open(LLM_PROVIDERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"加载 LLM 提供商配置失败: {e}")


def load_platforms_sources() -> Dict[str, Any]:
    """加载平台源配置"""
    if not PLATFORMS_SOURCES_PATH.exists():
        return {
            "aiocqhttp": {
                "type": "aiocqhttp",
                "enable": True,
                "id": "aiocqhttp",
                "name": "NekoBot",
                "ws_host": "0.0.0.0",
                "ws_port": 6299,
                "command_prefix": "/",
            }
        }
    try:
        with open(PLATFORMS_SOURCES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"加载平台源配置失败: {e}")
