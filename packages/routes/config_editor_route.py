"""配置编辑器 API

提供平台和LLM适配器的配置模板获取、参数验证和配置编辑功能
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

from .route import Route, Response, RouteContext
from ..platform.register import get_all_platforms
from ..llm.register import llm_provider_cls_map
from ..platform.base import BasePlatform

# 配置文件路径
PLATFORMS_SOURCES_PATH = Path(__file__).parent.parent.parent / "data" / "platforms_sources.json"
LLM_PROVIDERS_PATH = Path(__file__).parent.parent.parent / "data" / "llm_providers.json"


class ConfigEditorRoute(Route):
    """配置编辑器路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.platforms_sources_path = PLATFORMS_SOURCES_PATH
        self.llm_providers_path = LLM_PROVIDERS_PATH
        self.routes = [
            # 平台相关
            ("/api/config/platforms/types", "GET", self.get_platform_types),
            ("/api/config/platforms/schema", "GET", self.get_platform_schema),
            ("/api/config/platforms/config", "GET", self.get_platform_config),
            ("/api/config/platforms/config", "POST", self.update_platform_config),
            ("/api/config/platforms/add", "POST", self.add_platform),
            ("/api/config/platforms/delete", "POST", self.delete_platform),
            # LLM相关
            ("/api/config/llm/types", "GET", self.get_llm_types),
            ("/api/config/llm/schema", "GET", self.get_llm_schema),
            ("/api/config/llm/config", "GET", self.get_llm_config),
            ("/api/config/llm/config", "POST", self.update_llm_config),
            ("/api/config/llm/add", "POST", self.add_llm_provider),
            ("/api/config/llm/delete", "POST", self.delete_llm_provider),
            # 配置验证
            ("/api/config/validate", "POST", self.validate_config),
        ]

    async def get_platform_types(self) -> Dict[str, Any]:
        """获取所有已注册的平台类型及其配置模板"""
        try:
            platforms = get_all_platforms()
            platform_types = []
            
            for platform_meta in platforms:
                platform_types.append({
                    "type": platform_meta.name,
                    "display_name": platform_meta.adapter_display_name or platform_meta.name,
                    "description": platform_meta.description,
                    "logo_path": platform_meta.logo_path,
                    "support_streaming_message": platform_meta.support_streaming_message,
                    "default_config": platform_meta.default_config_tmpl,
                })
            
            # 按显示名称排序
            platform_types.sort(key=lambda x: x["display_name"])
            
            return Response().ok(data={"platform_types": platform_types}).to_dict()
        except Exception as e:
            logger.error(f"获取平台类型失败: {e}")
            return Response().error(f"获取平台类型失败: {str(e)}").to_dict()

    async def get_platform_schema(self) -> Dict[str, Any]:
        """获取指定平台类型的配置schema（参数定义和验证规则）"""
        try:
            from quart import request
            platform_type = request.args.get("type")
            
            if not platform_type:
                return Response().error("缺少 type 参数").to_dict()
            
            platforms = get_all_platforms()
            platform_meta = next((p for p in platforms if p.name == platform_type), None)
            
            if not platform_meta:
                return Response().error(f"平台类型 {platform_type} 不存在").to_dict()
            
            # 构建配置schema
            schema = self._build_platform_schema(platform_type, platform_meta.default_config_tmpl)
            
            return Response().ok(data=schema).to_dict()
        except Exception as e:
            logger.error(f"获取平台schema失败: {e}")
            return Response().error(f"获取平台schema失败: {str(e)}").to_dict()

    async def get_platform_config(self) -> Dict[str, Any]:
        """获取指定平台ID的配置"""
        try:
            from quart import request
            platform_id = request.args.get("id")
            
            if not platform_id:
                return Response().error("缺少 id 参数").to_dict()
            
            platforms = self._load_platforms_config()
            
            if platform_id not in platforms:
                return Response().error(f"平台 {platform_id} 不存在").to_dict()
            
            # 获取平台类型
            platform_type = platforms[platform_id].get("type", "unknown")
            platforms_list = get_all_platforms()
            platform_meta = next((p for p in platforms_list if p.name == platform_type), None)
            
            # 合并默认配置和当前配置
            config = platforms[platform_id].copy()
            if platform_meta and platform_meta.default_config_tmpl:
                # 只保留用户配置的字段，避免显示默认值
                pass
            
            return Response().ok(data=config).to_dict()
        except Exception as e:
            logger.error(f"获取平台配置失败: {e}")
            return Response().error(f"获取平台配置失败: {str(e)}").to_dict()

    async def update_platform_config(self) -> Dict[str, Any]:
        """更新平台配置"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()
            
            platform_id = data.get("id")
            if not platform_id:
                return Response().error("缺少平台ID").to_dict()
            
            # 验证配置
            platform_type = data.get("type")
            if not platform_type:
                return Response().error("缺少平台类型").to_dict()
            
            # 验证平台类型是否存在
            platforms_list = get_all_platforms()
            platform_meta = next((p for p in platforms_list if p.name == platform_type), None)
            if not platform_meta:
                return Response().error(f"平台类型 {platform_type} 不存在").to_dict()
            
            # 验证必需字段
            validation_result = self._validate_platform_config(platform_type, data)
            if not validation_result["valid"]:
                return Response().error(f"配置验证失败: {validation_result['errors']}").to_dict()
            
            # 加载现有配置
            platforms = self._load_platforms_config()
            
            # 更新配置
            platforms[platform_id] = data
            
            # 保存配置
            self._save_platforms_config(platforms)
            
            logger.info(f"平台 {platform_id} 配置已更新")
            return Response().ok(message="平台配置更新成功").to_dict()
        except Exception as e:
            logger.error(f"更新平台配置失败: {e}")
            return Response().error(f"更新平台配置失败: {str(e)}").to_dict()

    async def add_platform(self) -> Dict[str, Any]:
        """添加新平台"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()
            
            platform_id = data.get("id")
            platform_type = data.get("type")
            
            if not platform_id or not platform_type:
                return Response().error("缺少平台ID或类型").to_dict()
            
            # 验证平台类型
            platforms_list = get_all_platforms()
            platform_meta = next((p for p in platforms_list if p.name == platform_type), None)
            if not platform_meta:
                return Response().error(f"平台类型 {platform_type} 不存在").to_dict()
            
            # 检查ID是否已存在
            platforms = self._load_platforms_config()
            if platform_id in platforms:
                return Response().error(f"平台ID {platform_id} 已存在").to_dict()
            
            # 创建默认配置
            config = platform_meta.default_config_tmpl.copy()
            config["id"] = platform_id
            config["type"] = platform_type
            
            # 合并用户提供的配置
            for key, value in data.items():
                if key in config:
                    config[key] = value
            
            # 保存配置
            platforms[platform_id] = config
            self._save_platforms_config(platforms)
            
            logger.info(f"平台 {platform_id} 已添加")
            return Response().ok(message="平台添加成功").to_dict()
        except Exception as e:
            logger.error(f"添加平台失败: {e}")
            return Response().error(f"添加平台失败: {str(e)}").to_dict()

    async def delete_platform(self) -> Dict[str, Any]:
        """删除平台"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()
            
            platform_id = data.get("id")
            if not platform_id:
                return Response().error("缺少平台ID").to_dict()
            
            platforms = self._load_platforms_config()
            
            if platform_id not in platforms:
                return Response().error(f"平台 {platform_id} 不存在").to_dict()
            
            del platforms[platform_id]
            self._save_platforms_config(platforms)
            
            logger.info(f"平台 {platform_id} 已删除")
            return Response().ok(message="平台删除成功").to_dict()
        except Exception as e:
            logger.error(f"删除平台失败: {e}")
            return Response().error(f"删除平台失败: {str(e)}").to_dict()

    async def get_llm_types(self) -> Dict[str, Any]:
        """获取所有已注册的LLM类型及其配置模板"""
        try:
            llm_types = []
            
            for provider_key, provider_meta in llm_provider_cls_map.items():
                llm_types.append({
                    "type": provider_key,
                    "display_name": provider_meta.provider_display_name or provider_key,
                    "description": provider_meta.desc,
                    "provider_type": provider_meta.provider_type.value,
                    "default_config": provider_meta.default_config_tmpl,
                })
            
            # 按显示名称排序
            llm_types.sort(key=lambda x: x["display_name"])
            
            return Response().ok(data={"llm_types": llm_types}).to_dict()
        except Exception as e:
            logger.error(f"获取LLM类型失败: {e}")
            return Response().error(f"获取LLM类型失败: {str(e)}").to_dict()

    async def get_llm_schema(self) -> Dict[str, Any]:
        """获取指定LLM类型的配置schema（参数定义和验证规则）"""
        try:
            from quart import request
            llm_type = request.args.get("type")
            
            if not llm_type:
                return Response().error("缺少 type 参数").to_dict()
            
            provider_meta = llm_provider_cls_map.get(llm_type)
            if not provider_meta:
                return Response().error(f"LLM类型 {llm_type} 不存在").to_dict()
            
            # 构建配置schema
            schema = self._build_llm_schema(llm_type, provider_meta.default_config_tmpl)
            
            return Response().ok(data=schema).to_dict()
        except Exception as e:
            logger.error(f"获取LLM schema失败: {e}")
            return Response().error(f"获取LLM schema失败: {str(e)}").to_dict()

    async def get_llm_config(self) -> Dict[str, Any]:
        """获取指定LLM提供商的配置"""
        try:
            from quart import request
            provider_id = request.args.get("id")
            
            if not provider_id:
                return Response().error("缺少 id 参数").to_dict()
            
            providers = self._load_llm_providers_config()
            
            if provider_id not in providers:
                return Response().error(f"LLM提供商 {provider_id} 不存在").to_dict()
            
            return Response().ok(data=providers[provider_id]).to_dict()
        except Exception as e:
            logger.error(f"获取LLM配置失败: {e}")
            return Response().error(f"获取LLM配置失败: {str(e)}").to_dict()

    async def update_llm_config(self) -> Dict[str, Any]:
        """更新LLM提供商配置"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()
            
            provider_id = data.get("id")
            if not provider_id:
                return Response().error("缺少提供商ID").to_dict()
            
            # 验证配置
            llm_type = data.get("type")
            if not llm_type:
                return Response().error("缺少LLM类型").to_dict()
            
            # 验证LLM类型是否存在
            provider_meta = llm_provider_cls_map.get(llm_type)
            if not provider_meta:
                return Response().error(f"LLM类型 {llm_type} 不存在").to_dict()
            
            # 验证必需字段
            validation_result = self._validate_llm_config(llm_type, data)
            if not validation_result["valid"]:
                return Response().error(f"配置验证失败: {validation_result['errors']}").to_dict()
            
            # 加载现有配置
            providers = self._load_llm_providers_config()
            
            # 更新配置
            providers[provider_id] = data
            
            # 保存配置
            self._save_llm_providers_config(providers)
            
            logger.info(f"LLM提供商 {provider_id} 配置已更新")
            return Response().ok(message="LLM提供商配置更新成功").to_dict()
        except Exception as e:
            logger.error(f"更新LLM配置失败: {e}")
            return Response().error(f"更新LLM配置失败: {str(e)}").to_dict()

    async def add_llm_provider(self) -> Dict[str, Any]:
        """添加新LLM提供商"""
        try:
            import uuid
            
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()
            
            llm_type = data.get("type")
            
            if not llm_type:
                return Response().error("缺少LLM类型").to_dict()
            
            # 验证LLM类型
            provider_meta = llm_provider_cls_map.get(llm_type)
            if not provider_meta:
                return Response().error(f"LLM类型 {llm_type} 不存在").to_dict()
            
            # 生成唯一ID
            provider_id = str(uuid.uuid4())
            
            # 创建默认配置
            config = provider_meta.default_config_tmpl.copy()
            config["id"] = provider_id
            config["type"] = llm_type
            
            # 合并用户提供的配置
            for key, value in data.items():
                if key in config:
                    config[key] = value
            
            # 添加时间戳
            from datetime import datetime
            config["created_at"] = datetime.now().isoformat()
            
            # 保存配置
            providers = self._load_llm_providers_config()
            providers[provider_id] = config
            self._save_llm_providers_config(providers)
            
            logger.info(f"LLM提供商 {provider_id} 已添加")
            return Response().ok(data={"id": provider_id}, message="LLM提供商添加成功").to_dict()
        except Exception as e:
            logger.error(f"添加LLM提供商失败: {e}")
            return Response().error(f"添加LLM提供商失败: {str(e)}").to_dict()

    async def delete_llm_provider(self) -> Dict[str, Any]:
        """删除LLM提供商"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()
            
            provider_id = data.get("id")
            if not provider_id:
                return Response().error("缺少提供商ID").to_dict()
            
            providers = self._load_llm_providers_config()
            
            if provider_id not in providers:
                return Response().error(f"LLM提供商 {provider_id} 不存在").to_dict()
            
            del providers[provider_id]
            self._save_llm_providers_config(providers)
            
            logger.info(f"LLM提供商 {provider_id} 已删除")
            return Response().ok(message="LLM提供商删除成功").to_dict()
        except Exception as e:
            logger.error(f"删除LLM提供商失败: {e}")
            return Response().error(f"删除LLM提供商失败: {str(e)}").to_dict()

    async def validate_config(self) -> Dict[str, Any]:
        """验证配置"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()
            
            config_type = data.get("config_type")  # "platform" or "llm"
            config_data = data.get("config")
            
            if not config_type or not config_data:
                return Response().error("缺少配置类型或配置数据").to_dict()
            
            if config_type == "platform":
                platform_type = config_data.get("type")
                result = self._validate_platform_config(platform_type, config_data)
            elif config_type == "llm":
                llm_type = config_data.get("type")
                result = self._validate_llm_config(llm_type, config_data)
            else:
                return Response().error("不支持的配置类型").to_dict()
            
            return Response().ok(data=result).to_dict()
        except Exception as e:
            logger.error(f"验证配置失败: {e}")
            return Response().error(f"验证配置失败: {str(e)}").to_dict()

    def _load_platforms_config(self) -> Dict[str, Any]:
        """加载平台配置"""
        if not self.platforms_sources_path.exists():
            return {}
        
        try:
            with open(self.platforms_sources_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载平台配置文件失败: {e}")
            return {}

    def _save_platforms_config(self, platforms: Dict[str, Any]) -> None:
        """保存平台配置"""
        self.platforms_sources_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.platforms_sources_path, "w", encoding="utf-8") as f:
            json.dump(platforms, f, indent=2, ensure_ascii=False)

    def _load_llm_providers_config(self) -> Dict[str, Any]:
        """加载LLM提供商配置"""
        if not self.llm_providers_path.exists():
            return {}
        
        try:
            with open(self.llm_providers_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载LLM提供商配置文件失败: {e}")
            return {}

    def _save_llm_providers_config(self, providers: Dict[str, Any]) -> None:
        """保存LLM提供商配置"""
        self.llm_providers_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.llm_providers_path, "w", encoding="utf-8") as f:
            json.dump(providers, f, indent=2, ensure_ascii=False)

    def _build_platform_schema(self, platform_type: str, default_config: Dict[str, Any]) -> Dict[str, Any]:
        """构建平台配置schema"""
        schema = {
            "type": platform_type,
            "fields": []
        }
        
        # 根据平台类型定义字段
        field_definitions = self._get_platform_field_definitions(platform_type)
        
        for field_name, field_info in field_definitions.items():
            field = {
                "name": field_name,
                "display_name": field_info.get("display_name", field_name),
                "description": field_info.get("description", ""),
                "type": field_info.get("type", "string"),
                "required": field_info.get("required", False),
                "default": default_config.get(field_name),
                "validation": field_info.get("validation", {}),
            }
            schema["fields"].append(field)
        
        return schema

    def _get_platform_field_definitions(self, platform_type: str) -> Dict[str, Any]:
        """获取平台字段定义"""
        # 基础字段
        base_fields = {
            "type": {
                "display_name": "平台类型",
                "description": "平台适配器类型",
                "type": "string",
                "required": True,
                "readonly": True,
            },
            "enable": {
                "display_name": "启用",
                "description": "是否启用此平台",
                "type": "boolean",
                "required": False,
                "default": False,
            },
            "id": {
                "display_name": "平台ID",
                "description": "平台唯一标识符",
                "type": "string",
                "required": True,
            },
            "name": {
                "display_name": "显示名称",
                "description": "平台显示名称",
                "type": "string",
                "required": False,
            },
        }
        
        # 平台特定字段
        platform_fields = {}
        
        if platform_type == "aiocqhttp":
            platform_fields = {
                "ws_host": {
                    "display_name": "WebSocket主机",
                    "description": "WebSocket服务器监听地址",
                    "type": "string",
                    "required": False,
                    "default": "0.0.0.0",
                    "validation": {
                        "pattern": r"^[\d\.]+$|^[a-zA-Z0-9\.-]+$",
                    },
                },
                "ws_port": {
                    "display_name": "WebSocket端口",
                    "description": "WebSocket服务器监听端口",
                    "type": "integer",
                    "required": False,
                    "default": 6299,
                    "validation": {
                        "min": 1,
                        "max": 65535,
                    },
                },
                "access_token": {
                    "display_name": "访问令牌",
                    "description": "WebSocket连接的访问令牌（可选）",
                    "type": "string",
                    "required": False,
                    "secret": True,
                },
                "command_prefix": {
                    "display_name": "命令前缀",
                    "description": "机器人命令前缀",
                    "type": "string",
                    "required": False,
                    "default": "/",
                },
            }
        elif platform_type == "discord":
            platform_fields = {
                "discord_token": {
                    "display_name": "Discord Token",
                    "description": "Discord机器人Token",
                    "type": "string",
                    "required": True,
                    "secret": True,
                },
                "discord_guild_id_for_debug": {
                    "display_name": "调试服务器ID",
                    "description": "用于调试的Discord服务器ID（可选）",
                    "type": "string",
                    "required": False,
                },
                "discord_command_register": {
                    "display_name": "注册命令",
                    "description": "是否自动注册Discord命令",
                    "type": "boolean",
                    "required": False,
                    "default": True,
                },
                "discord_activity_name": {
                    "display_name": "活动状态",
                    "description": "Discord机器人的活动状态（可选）",
                    "type": "string",
                    "required": False,
                },
                "discord_proxy": {
                    "display_name": "代理",
                    "description": "Discord API代理地址（可选）",
                    "type": "string",
                    "required": False,
                },
            }
        elif platform_type == "telegram":
            platform_fields = {
                "telegram_token": {
                    "display_name": "Telegram Token",
                    "description": "Telegram机器人Token",
                    "type": "string",
                    "required": True,
                    "secret": True,
                },
                "telegram_api_id": {
                    "display_name": "API ID",
                    "description": "Telegram API ID（可选）",
                    "type": "string",
                    "required": False,
                },
                "telegram_api_hash": {
                    "display_name": "API Hash",
                    "description": "Telegram API Hash（可选）",
                    "type": "string",
                    "required": False,
                    "secret": True,
                },
                "telegram_proxy": {
                    "display_name": "代理",
                    "description": "Telegram代理地址（可选）",
                    "type": "string",
                    "required": False,
                },
            }
        elif platform_type == "kook":
            platform_fields = {
                "token": {
                    "display_name": "KOOK Token",
                    "description": "KOOK机器人Token",
                    "type": "string",
                    "required": True,
                    "secret": True,
                },
                "verify_token": {
                    "display_name": "验证令牌",
                    "description": "Webhook验证令牌（可选）",
                    "type": "string",
                    "required": False,
                },
                "encrypt_key": {
                    "display_name": "加密密钥",
                    "description": "Webhook加密密钥（可选）",
                    "type": "string",
                    "required": False,
                    "secret": True,
                },
                "api_base": {
                    "display_name": "API地址",
                    "description": "KOOK API基础地址",
                    "type": "string",
                    "required": False,
                    "default": "https://www.kookapp.cn/api/v3",
                },
            }
        elif platform_type == "lark":
            platform_fields = {
                "app_id": {
                    "display_name": "App ID",
                    "description": "飞书应用ID",
                    "type": "string",
                    "required": True,
                },
                "app_secret": {
                    "display_name": "App Secret",
                    "description": "飞书应用Secret",
                    "type": "string",
                    "required": True,
                    "secret": True,
                },
                "domain": {
                    "display_name": "域名",
                    "description": "飞书API域名",
                    "type": "string",
                    "required": False,
                    "default": "https://open.feishu.cn",
                },
                "connection_mode": {
                    "display_name": "连接模式",
                    "description": "连接模式：socket或webhook",
                    "type": "string",
                    "required": False,
                    "default": "socket",
                    "enum": ["socket", "webhook"],
                },
                "lark_bot_name": {
                    "display_name": "机器人名称",
                    "description": "飞书机器人显示名称",
                    "type": "string",
                    "required": False,
                    "default": "NekoBot",
                },
                "verify_token": {
                    "display_name": "验证令牌",
                    "description": "Webhook验证令牌（可选）",
                    "type": "string",
                    "required": False,
                },
                "encrypt_key": {
                    "display_name": "加密密钥",
                    "description": "Webhook加密密钥（可选）",
                    "type": "string",
                    "required": False,
                    "secret": True,
                },
            }
        elif platform_type == "wecom":
            platform_fields = {
                "corp_id": {
                    "display_name": "企业ID",
                    "description": "微信企业版企业ID",
                    "type": "string",
                    "required": True,
                },
                "corp_secret": {
                    "display_name": "企业Secret",
                    "description": "微信企业版应用Secret",
                    "type": "string",
                    "required": True,
                    "secret": True,
                },
                "agent_id": {
                    "display_name": "Agent ID",
                    "description": "微信企业版应用Agent ID",
                    "type": "string",
                    "required": True,
                },
                "token": {
                    "display_name": "Token",
                    "description": "Webhook验证Token",
                    "type": "string",
                    "required": True,
                },
                "encoding_aes_key": {
                    "display_name": "AES密钥",
                    "description": "消息加密AES密钥（可选）",
                    "type": "string",
                    "required": False,
                    "secret": True,
                },
                "receive_id": {
                    "display_name": "接收ID",
                    "description": "消息接收ID（可选）",
                    "type": "string",
                    "required": False,
                },
                "receive_url": {
                    "display_name": "接收URL",
                    "description": "消息接收URL（可选）",
                    "type": "string",
                    "required": False,
                },
            }
        # 可以继续添加其他平台的字段定义...
        
        return {**base_fields, **platform_fields}

    def _build_llm_schema(self, llm_type: str, default_config: Dict[str, Any]) -> Dict[str, Any]:
        """构建LLM配置schema"""
        schema = {
            "type": llm_type,
            "fields": []
        }
        
        # 基础字段
        base_fields = {
            "type": {
                "display_name": "提供商类型",
                "description": "LLM服务提供商类型",
                "type": "string",
                "required": True,
                "readonly": True,
            },
            "enable": {
                "display_name": "启用",
                "description": "是否启用此提供商",
                "type": "boolean",
                "required": False,
                "default": False,
            },
            "id": {
                "display_name": "提供商ID",
                "description": "提供商唯一标识符",
                "type": "string",
                "required": True,
            },
            "name": {
                "display_name": "显示名称",
                "description": "提供商显示名称",
                "type": "string",
                "required": False,
            },
        }
        
        # LLM特定字段
        llm_fields = {
            "api_key": {
                "display_name": "API密钥",
                "description": "LLM服务API密钥",
                "type": "string",
                "required": True,
                "secret": True,
            },
            "base_url": {
                "display_name": "API地址",
                "description": "LLM服务API基础地址",
                "type": "string",
                "required": False,
            },
            "model": {
                "display_name": "模型",
                "description": "使用的模型名称",
                "type": "string",
                "required": False,
            },
            "max_tokens": {
                "display_name": "最大令牌数",
                "description": "生成的最大令牌数",
                "type": "integer",
                "required": False,
                "default": 4096,
                "validation": {
                    "min": 1,
                    "max": 128000,
                },
            },
            "temperature": {
                "display_name": "温度",
                "description": "生成文本的随机性（0.0-2.0）",
                "type": "number",
                "required": False,
                "default": 0.7,
                "validation": {
                    "min": 0.0,
                    "max": 2.0,
                },
            },
            "timeout": {
                "display_name": "超时时间",
                "description": "请求超时时间（秒）",
                "type": "integer",
                "required": False,
                "default": 120,
                "validation": {
                    "min": 1,
                    "max": 600,
                },
            },
        }
        
        # 根据LLM类型添加特定字段
        if llm_type == "openai":
            llm_fields["base_url"]["default"] = "https://api.openai.com/v1"
            llm_fields["base_url"]["required"] = False
        elif llm_type in ["ollama", "lm_studio"]:
            llm_fields["api_key"]["required"] = False
            llm_fields["base_url"]["required"] = False
            if llm_type == "ollama":
                llm_fields["base_url"]["default"] = "http://localhost:11434"
            elif llm_type == "lm_studio":
                llm_fields["base_url"]["default"] = "http://localhost:1234"
        
        # 合并所有字段
        all_fields = {**base_fields, **llm_fields}
        
        for field_name, field_info in all_fields.items():
            field = {
                "name": field_name,
                "display_name": field_info.get("display_name", field_name),
                "description": field_info.get("description", ""),
                "type": field_info.get("type", "string"),
                "required": field_info.get("required", False),
                "default": field_info.get("default"),
                "validation": field_info.get("validation", {}),
                "secret": field_info.get("secret", False),
                "readonly": field_info.get("readonly", False),
            }
            
            # 添加枚举值（如果有）
            if "enum" in field_info:
                field["enum"] = field_info["enum"]
            
            schema["fields"].append(field)
        
        return schema

    def _validate_platform_config(self, platform_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """验证平台配置"""
        errors = []
        
        field_definitions = self._get_platform_field_definitions(platform_type)
        
        for field_name, field_info in field_definitions.items():
            # 检查必需字段
            if field_info.get("required", False) and field_name not in config:
                errors.append(f"缺少必需字段: {field_info.get('display_name', field_name)}")
                continue
            
            if field_name not in config:
                continue
            
            value = config[field_name]
            
            # 类型验证
            field_type = field_info.get("type")
            if field_type == "integer" and not isinstance(value, int):
                errors.append(f"{field_info.get('display_name', field_name)} 必须是整数")
            elif field_type == "boolean" and not isinstance(value, bool):
                errors.append(f"{field_info.get('display_name', field_name)} 必须是布尔值")
            elif field_type == "number" and not isinstance(value, (int, float)):
                errors.append(f"{field_info.get('display_name', field_name)} 必须是数字")
            
            # 验证规则
            validation = field_info.get("validation", {})
            if validation:
                if "min" in validation and isinstance(value, (int, float)) and value < validation["min"]:
                    errors.append(f"{field_info.get('display_name', field_name)} 不能小于 {validation['min']}")
                if "max" in validation and isinstance(value, (int, float)) and value > validation["max"]:
                    errors.append(f"{field_info.get('display_name', field_name)} 不能大于 {validation['max']}")
                if "pattern" in validation and isinstance(value, str):
                    import re
                    if not re.match(validation["pattern"], value):
                        errors.append(f"{field_info.get('display_name', field_name)} 格式不正确")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def _validate_llm_config(self, llm_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """验证LLM配置"""
        errors = []
        
        # 基础验证
        required_fields = ["type", "api_key"]
        
        # 某些LLM类型不需要api_key
        if llm_type in ["ollama", "lm_studio"]:
            required_fields = ["type"]
        
        for field in required_fields:
            if field not in config or not config[field]:
                errors.append(f"缺少必需字段: {field}")
        
        # 类型验证
        if "max_tokens" in config and not isinstance(config["max_tokens"], int):
            errors.append("max_tokens 必须是整数")
        
        if "temperature" in config:
            temp = config["temperature"]
            if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
                errors.append("temperature 必须是 0.0 到 2.0 之间的数字")
        
        if "timeout" in config and not isinstance(config["timeout"], int):
            errors.append("timeout 必须是整数")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }