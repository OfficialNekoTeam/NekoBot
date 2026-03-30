"""models.dev 模型能力注册表

从 https://models.dev/api.json 拉取模型信息，缓存到本地文件。
用于查询模型是否支持视觉输入、获取 provider API base_url 等。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

_API_URL = "https://models.dev/api.json"
_CACHE_PATH = Path("data/models_dev_cache.json")
_CACHE_TTL = 86400 * 7  # 7 天


@dataclass(frozen=True)
class ModelsDevModel:
    id: str
    name: str
    provider_id: str
    input_modalities: tuple[str, ...] = ()
    output_modalities: tuple[str, ...] = ()
    attachment: bool = False
    reasoning: bool = False
    tool_call: bool = False
    context_window: int | None = None
    output_limit: int | None = None

    @property
    def supports_vision(self) -> bool:
        return "image" in self.input_modalities

    @property
    def supports_audio(self) -> bool:
        return "audio" in self.input_modalities

    @property
    def supports_pdf(self) -> bool:
        return "pdf" in self.input_modalities


@dataclass(frozen=True)
class ModelsDevProvider:
    id: str
    name: str
    api_url: str | None = None
    models: dict[str, ModelsDevModel] = field(default_factory=dict)


class ModelsDevRegistry:
    """懒加载、本地文件缓存的 models.dev 注册表。"""

    def __init__(self) -> None:
        self._providers: dict[str, ModelsDevProvider] = {}
        self._loaded = False

    async def ensure_loaded(self) -> None:
        if self._loaded:
            return
        data = self._load_cache()
        if data is None:
            data = await self._fetch()
            if data is not None:
                self._save_cache(data)
        if data is not None:
            self._parse(data)
            self._loaded = True
            total = sum(len(p.models) for p in self._providers.values())
            logger.info(
                "models.dev: loaded {} providers, {} models",
                len(self._providers),
                total,
            )
        else:
            logger.warning("models.dev: failed to load, capability checks unavailable")

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------

    def supports_vision(self, provider_id: str, model_id: str) -> bool | None:
        """返回 True/False；数据缺失时返回 None。"""
        model = self._get_model(provider_id, model_id)
        return model.supports_vision if model else None

    def get_provider_api_url(self, provider_id: str) -> str | None:
        provider = self._providers.get(provider_id)
        return provider.api_url if provider else None

    def get_model(self, provider_id: str, model_id: str) -> ModelsDevModel | None:
        return self._get_model(provider_id, model_id)

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _get_model(self, provider_id: str, model_id: str) -> ModelsDevModel | None:
        provider = self._providers.get(provider_id)
        if provider is None:
            return None
        return provider.models.get(model_id)

    def _parse(self, raw: dict[str, Any]) -> None:
        for provider_id, provider_data in raw.items():
            if not isinstance(provider_data, dict):
                continue
            api_url = provider_data.get("api")
            if isinstance(api_url, str) and (
                "docs" in api_url or "platform" in api_url
            ):
                api_url = None  # 过滤掉文档链接，只保留真实 API endpoint
            models: dict[str, ModelsDevModel] = {}
            raw_models = provider_data.get("models", {})
            if isinstance(raw_models, dict):
                for model_id, model_data in raw_models.items():
                    if not isinstance(model_data, dict):
                        continue
                    modalities = model_data.get("modalities", {})
                    _is_mod = isinstance(modalities, dict)
                    inp = modalities.get("input", []) if _is_mod else []
                    out = modalities.get("output", []) if _is_mod else []
                    limit = model_data.get("limit", {})
                    models[model_id] = ModelsDevModel(
                        id=model_id,
                        name=str(model_data.get("name", model_id)),
                        provider_id=provider_id,
                        input_modalities=tuple(inp) if isinstance(inp, list) else (),
                        output_modalities=tuple(out) if isinstance(out, list) else (),
                        attachment=bool(model_data.get("attachment", False)),
                        reasoning=bool(model_data.get("reasoning", False)),
                        tool_call=bool(model_data.get("tool_call", False)),
                        context_window=(
                            limit.get("context") if isinstance(limit, dict) else None
                        ),
                        output_limit=(
                            limit.get("output") if isinstance(limit, dict) else None
                        ),
                    )
            self._providers[provider_id] = ModelsDevProvider(
                id=provider_id,
                name=str(provider_data.get("name", provider_id)),
                api_url=api_url if isinstance(api_url, str) else None,
                models=models,
            )

    async def _fetch(self) -> dict[str, Any] | None:
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.get(_API_URL, timeout=timeout) as resp:
                    if resp.status != 200:
                        logger.warning("models.dev: HTTP {}", resp.status)
                        return None
                    raw = await resp.json(content_type=None)
                    if not isinstance(raw, dict):
                        return None
                    logger.debug("models.dev: fetched from remote")
                    return raw  # type: ignore[return-value]
        except Exception as exc:
            logger.warning("models.dev: fetch failed: {}", exc)
            return None

    def _load_cache(self) -> dict[str, Any] | None:
        if not _CACHE_PATH.exists():
            return None
        try:
            payload = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            cached_at = payload.get("_cached_at", 0)
            if time.time() - cached_at > _CACHE_TTL:
                logger.debug("models.dev: cache expired")
                return None
            data = payload.get("data")
            if isinstance(data, dict):
                logger.debug("models.dev: loaded from cache")
                return data  # type: ignore[return-value]
        except Exception as exc:
            logger.debug("models.dev: cache read failed: {}", exc)
        return None

    def _save_cache(self, data: dict[str, Any]) -> None:
        try:
            _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _CACHE_PATH.write_text(
                json.dumps(
                    {"_cached_at": time.time(), "data": data}, ensure_ascii=False
                ),
                encoding="utf-8",
            )
            logger.debug("models.dev: cache saved to {}", _CACHE_PATH)
        except Exception as exc:
            logger.debug("models.dev: cache write failed: {}", exc)


# 模块级单例
_registry: ModelsDevRegistry | None = None


def get_models_dev_registry() -> ModelsDevRegistry:
    global _registry
    if _registry is None:
        _registry = ModelsDevRegistry()
    return _registry
