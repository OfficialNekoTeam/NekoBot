from __future__ import annotations

from quart import Blueprint, current_app, request

from ..deps import require_auth

schema_bp = Blueprint("schema", __name__, url_prefix="/api/v1/schema")

# ---------------------------------------------------------------------------
# Provider field schemas
# ---------------------------------------------------------------------------

_COMMON_FIELDS: dict[str, dict] = {
    "enabled": {
        "type": "bool",
        "label": "启用",
        "hint": None,
        "required": False,
        "default": True,
    },
}

PROVIDER_SCHEMAS: dict[str, dict] = {
    "openai_compatible": {
        "label": "OpenAI Compatible",
        "description": "兼容 OpenAI API 格式的自定义提供商（支持中转/本地推理）",
        "fields": {
            "api_key": {
                "type": "password",
                "label": "API Key",
                "hint": "从提供商平台获取",
                "required": True,
                "default": "",
            },
            "base_url": {
                "type": "string",
                "label": "API Base URL",
                "hint": "例：https://api.openai.com/v1",
                "required": True,
                "default": "",
            },
            "default_model": {
                "type": "string",
                "label": "默认模型",
                "hint": "例：gpt-4o、qwen-turbo",
                "required": False,
                "default": "",
            },
            "api_flavor": {
                "type": "select",
                "label": "API 风格",
                "hint": "通常保持 chat_completions",
                "required": False,
                "default": "chat_completions",
                "options": ["chat_completions", "responses"],
                "option_labels": ["Chat Completions", "Responses API"],
            },
            "enable_streaming": {
                "type": "bool",
                "label": "启用流式输出",
                "hint": None,
                "required": False,
                "default": True,
            },
            "timeout_seconds": {
                "type": "int",
                "label": "超时（秒）",
                "hint": None,
                "required": False,
                "default": 60,
                "min": 5,
                "max": 600,
            },
            **_COMMON_FIELDS,
        },
    },
    "openai": {
        "label": "OpenAI",
        "description": "官方 OpenAI API（GPT-4o / o3 等）",
        "fields": {
            "api_key": {
                "type": "password",
                "label": "API Key",
                "hint": "以 sk- 开头",
                "required": True,
                "default": "",
            },
            "default_model": {
                "type": "string",
                "label": "默认模型",
                "hint": "例：gpt-4o",
                "required": False,
                "default": "gpt-4o",
            },
            "organization": {
                "type": "string",
                "label": "组织 ID",
                "hint": "可选",
                "required": False,
                "default": "",
            },
            "project": {
                "type": "string",
                "label": "项目 ID",
                "hint": "可选",
                "required": False,
                "default": "",
            },
            "reasoning_effort": {
                "type": "select",
                "label": "推理深度",
                "hint": "仅 o3/o4 系列有效",
                "required": False,
                "default": "",
                "options": ["", "low", "medium", "high"],
                "option_labels": ["默认", "低", "中", "高"],
            },
            "enable_streaming": {
                "type": "bool",
                "label": "启用流式输出",
                "hint": None,
                "required": False,
                "default": True,
            },
            "timeout_seconds": {
                "type": "int",
                "label": "超时（秒）",
                "hint": None,
                "required": False,
                "default": 60,
                "min": 5,
                "max": 600,
            },
            **_COMMON_FIELDS,
        },
    },
    "anthropic": {
        "label": "Anthropic",
        "description": "官方 Anthropic API（Claude 系列）",
        "fields": {
            "api_key": {
                "type": "password",
                "label": "API Key",
                "hint": "以 sk-ant- 开头",
                "required": True,
                "default": "",
            },
            "default_model": {
                "type": "string",
                "label": "默认模型",
                "hint": "例：claude-opus-4-7",
                "required": False,
                "default": "claude-sonnet-4-6",
            },
            "base_url": {
                "type": "string",
                "label": "自定义 Base URL",
                "hint": "中转时填写，否则留空",
                "required": False,
                "default": "",
            },
            "max_tokens": {
                "type": "int",
                "label": "最大输出 Token",
                "hint": None,
                "required": False,
                "default": 8192,
                "min": 256,
                "max": 65536,
            },
            "enable_streaming": {
                "type": "bool",
                "label": "启用流式输出",
                "hint": None,
                "required": False,
                "default": True,
            },
            "timeout_seconds": {
                "type": "int",
                "label": "超时（秒）",
                "hint": None,
                "required": False,
                "default": 60,
                "min": 5,
                "max": 600,
            },
            **_COMMON_FIELDS,
        },
    },
    "gemini": {
        "label": "Google Gemini",
        "description": "Google Gemini API",
        "fields": {
            "api_key": {
                "type": "password",
                "label": "API Key",
                "hint": "从 Google AI Studio 获取",
                "required": True,
                "default": "",
            },
            "default_model": {
                "type": "string",
                "label": "默认模型",
                "hint": "例：gemini-2.0-flash",
                "required": False,
                "default": "gemini-2.0-flash",
            },
            "max_output_tokens": {
                "type": "int",
                "label": "最大输出 Token",
                "hint": None,
                "required": False,
                "default": 8192,
                "min": 256,
                "max": 65536,
            },
            "enable_streaming": {
                "type": "bool",
                "label": "启用流式输出",
                "hint": None,
                "required": False,
                "default": True,
            },
            "timeout_seconds": {
                "type": "int",
                "label": "超时（秒）",
                "hint": None,
                "required": False,
                "default": 60,
                "min": 5,
                "max": 600,
            },
            **_COMMON_FIELDS,
        },
    },
}


def _infer_field(key: str, value: object) -> dict:
    """Infer a field schema from a config key/value pair."""
    if isinstance(value, bool):
        return {"type": "bool", "label": key, "hint": None, "required": False, "default": value}
    if isinstance(value, int):
        return {"type": "int", "label": key, "hint": None, "required": False, "default": value}
    if isinstance(value, float):
        return {"type": "float", "label": key, "hint": None, "required": False, "default": value}
    if isinstance(value, list):
        return {"type": "list", "label": key, "hint": None, "required": False, "default": value}
    secret_hints = ("key", "token", "secret", "password", "credential")
    if any(h in key.lower() for h in secret_hints):
        return {"type": "password", "label": key, "hint": None, "required": True, "default": ""}
    long_value = isinstance(value, str) and len(value) > 120
    return {
        "type": "text" if long_value else "string",
        "label": key,
        "hint": None,
        "required": False,
        "default": value if not long_value else "",
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@schema_bp.route("/providers", methods=["GET"], strict_slashes=False)
@require_auth
async def list_provider_schemas() -> dict:
    return {"success": True, "data": PROVIDER_SCHEMAS}


@schema_bp.route("/providers/<provider_type>", methods=["GET"])
@require_auth
async def get_provider_schema(provider_type: str) -> tuple[dict, int] | dict:
    schema = PROVIDER_SCHEMAS.get(provider_type)
    if schema is None:
        return {"success": False, "message": f"No schema for provider type {provider_type!r}"}, 404
    return {"success": True, "data": schema}


@schema_bp.route("/plugins/<plugin_name>", methods=["GET"])
@require_auth
async def get_plugin_schema(plugin_name: str) -> tuple[dict, int] | dict:
    fw = current_app.config.get("FRAMEWORK")
    if fw is None:
        return {"success": False, "message": "Framework not available."}, 503

    mgr = getattr(fw, "config_manager", None)
    if mgr is None:
        return {"success": False, "message": "Config manager not available."}, 503

    # Try to load schema.json from plugin directory
    import json
    import os
    plugin_dir = os.path.join("data", "plugins", plugin_name)
    schema_file = os.path.join(plugin_dir, "schema.json")
    if os.path.isfile(schema_file):
        try:
            with open(schema_file, encoding="utf-8") as f:
                schema = json.load(f)
            return {"success": True, "data": schema}
        except Exception:
            pass

    # Fall back: infer from current plugin config values
    config_id = request.args.get("config_id", "default")
    plugin_configs = mgr.get_plugin_configs(config_id)
    current_cfg = plugin_configs.get(plugin_name, {})

    if not current_cfg:
        return {"success": True, "data": {"fields": {}}}

    inferred = {k: _infer_field(k, v) for k, v in current_cfg.items()}
    return {"success": True, "data": {"fields": inferred}}
