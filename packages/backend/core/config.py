"""配置加载模块

读取 data/cmd_config.json 并提供全局配置对象
"""

import json
from pathlib import Path
from typing import Dict, Any

# 项目根目录下的 data/cmd_config.json
CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "data" / "cmd_config.json"


def load_config() -> Dict[str, Any]:
    """加载配置文件，如果不存在返回默认配置"""
    if not CONFIG_PATH.exists():
        return {
            "command_prefix": "/",
            "server": {"host": "0.0.0.0", "port": 6285},
            "jwt": {
                "secret_key": "",
                "algorithm": "HS256",
                "access_token_expire_minutes": 30,
            },
            "demo": False,
            "platforms": {
                "aiocqhttp": {
                    "type": "aiocqhttp",
                    "enable": True,
                    "id": "aiocqhttp",
                    "name": "NekoBot",
                    "ws_host": "0.0.0.0",
                    "ws_port": 6299,
                    "command_prefix": "/",
                }
            },
        }
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"加载配置文件失败: {e}")
