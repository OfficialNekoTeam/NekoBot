"""LLM/TTL服务提供商API

提供LLM/TTL服务提供商的添加、更新、删除等功能
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any
from loguru import logger

from .route import Route, Response, RouteContext
from ..llm.register import llm_provider_cls_map


LLM_PROVIDERS_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "llm_providers.json"
)

class LlmRoute(Route):
    """LLM/TTL服务提供商路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.providers_path = LLM_PROVIDERS_PATH
        self.providers_path.parent.mkdir(parents=True, exist_ok=True)
        self.routes = [
            ("/api/llm/providers", "GET", self.get_providers),
            ("/api/llm/providers/types", "GET", self.get_provider_types),
            ("/api/llm/providers/add", "POST", self.add_provider),
            ("/api/llm/providers/update", "POST", self.update_provider),
            ("/api/llm/providers/delete", "POST", self.delete_provider),
        ]

    async def get_providers(self) -> Dict[str, Any]:
        """获取所有服务提供商列表"""
        try:
            providers = self._load_providers()
            providers_list = list(providers.values())
            return Response().ok(data={"providers": providers_list}).to_dict()
        except Exception as e:
            logger.error(f"获取服务提供商列表失败: {e}")
            return Response().error(f"获取服务提供商列表失败: {str(e)}").to_dict()

    async def add_provider(self) -> Dict[str, Any]:
        """添加服务提供商"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            is_valid, error_msg = await self.validate_required_fields(
                data, ["name", "type", "api_key"]
            )
            if not is_valid:
                return Response().error(error_msg).to_dict()

            providers = self._load_providers()
            provider_id = str(uuid.uuid4())

            providers[provider_id] = {
                "id": provider_id,
                "name": data["name"],
                "type": data["type"],
                "api_key": data["api_key"],
                "base_url": data.get("base_url", ""),
                "model": data.get("model", ""),
                "enabled": data.get("enabled", True),
                "created_at": self._get_current_timestamp(),
            }

            self._save_providers(providers)
            return (
                Response()
                .ok(data={"id": provider_id}, message="服务提供商添加成功")
                .to_dict()
            )
        except Exception as e:
            logger.error(f"添加服务提供商失败: {e}")
            return Response().error(f"添加服务提供商失败: {str(e)}").to_dict()

    async def update_provider(self) -> Dict[str, Any]:
        """更新服务提供商"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            provider_id = data.get("id")
            if not provider_id:
                return Response().error("缺少服务提供商ID").to_dict()

            providers = self._load_providers()
            if provider_id not in providers:
                return Response().error("服务提供商不存在").to_dict()

            provider = providers[provider_id]
            if "name" in data:
                provider["name"] = data["name"]
            if "type" in data:
                provider["type"] = data["type"]
            if "api_key" in data:
                provider["api_key"] = data["api_key"]
            if "base_url" in data:
                provider["base_url"] = data["base_url"]
            if "model" in data:
                provider["model"] = data["model"]
            if "enabled" in data:
                provider["enabled"] = data["enabled"]

            provider["updated_at"] = self._get_current_timestamp()
            self._save_providers(providers)
            return Response().ok(message="服务提供商更新成功").to_dict()
        except Exception as e:
            logger.error(f"更新服务提供商失败: {e}")
            return Response().error(f"更新服务提供商失败: {str(e)}").to_dict()

    async def delete_provider(self) -> Dict[str, Any]:
        """删除服务提供商"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            provider_id = data.get("id")
            if not provider_id:
                return Response().error("缺少服务提供商ID").to_dict()

            providers = self._load_providers()
            if provider_id not in providers:
                return Response().error("服务提供商不存在").to_dict()

            del providers[provider_id]
            self._save_providers(providers)
            return Response().ok(message="服务提供商删除成功").to_dict()
        except Exception as e:
            logger.error(f"删除服务提供商失败: {e}")
            return Response().error(f"删除服务提供商失败: {str(e)}").to_dict()

    async def get_provider_types(self) -> Dict[str, Any]:
        """获取所有已注册的 LLM 提供商类型"""
        try:
            # 获取所有已注册的提供商类型
            provider_types = []
            for provider_key, provider_meta in llm_provider_cls_map.items():
                provider_types.append({
                    "type": provider_key,
                    "display_name": provider_meta.provider_display_name,
                    "description": provider_meta.desc,
                })
            
            # 按显示名称排序
            provider_types.sort(key=lambda x: x["display_name"])
            
            return Response().ok(data={"provider_types": provider_types}).to_dict()
        except Exception as e:
            logger.error(f"获取 LLM 提供商类型失败: {e}")
            return Response().error(f"获取 LLM 提供商类型失败: {str(e)}").to_dict()

    def _load_providers(self) -> Dict[str, Any]:
        """加载所有服务提供商配置"""
        if not self.providers_path.exists():
            return {}

        try:
            with open(self.providers_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载服务提供商配置文件失败: {e}")
            return {}

    def _save_providers(self, providers: Dict[str, Any]) -> None:
        """保存服务提供商配置"""
        with open(self.providers_path, "w", encoding="utf-8") as f:
            json.dump(providers, f, indent=2, ensure_ascii=False)

    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime

        return datetime.now().isoformat()
