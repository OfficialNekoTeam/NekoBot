"""平台管理器"""

import asyncio
from typing import Dict, Any, Optional
from loguru import logger

from .base import BasePlatform
from .register import get_platform_adapter, get_all_platforms, platform_cls_map


class PlatformManager:
    """平台管理器，负责管理多个平台适配器"""

    def __init__(self):
        self.platforms: Dict[str, BasePlatform] = {}
        self.event_queue: Optional[asyncio.Queue] = None
        self.platform_settings: Dict[str, Any] = {}

    def set_event_queue(self, event_queue: asyncio.Queue) -> None:
        """设置事件队列"""
        self.event_queue = event_queue

    def set_platform_settings(self, settings: Dict[str, Any]) -> None:
        """设置平台设置"""
        self.platform_settings = settings

    async def load_platforms(self, platforms_config: Dict[str, Dict[str, Any]]) -> None:
        """加载平台适配器

        Args:
            platforms_config: 平台配置字典
        """
        logger.info("开始加载平台适配器...")

        for platform_id, platform_config in platforms_config.items():
            if not platform_config.get("enable", False):
                logger.debug(f"平台 {platform_id} 未启用，跳过")
                continue

            platform_type = platform_config.get("type", platform_id)
            adapter_cls = get_platform_adapter(platform_type)

            if not adapter_cls:
                logger.warning(f"未找到平台适配器: {platform_type}")
                continue

            try:
                platform = adapter_cls(
                    platform_config=platform_config,
                    platform_settings=self.platform_settings,
                    event_queue=self.event_queue,
                )
                self.platforms[platform_id] = platform
                logger.info(
                    f"已加载平台适配器: {platform_id} ({platform_config.get('name', 'Unknown')})"
                )
            except Exception as e:
                logger.error(f"加载平台适配器 {platform_id} 失败: {e}")

        logger.info(f"平台适配器加载完成，共 {len(self.platforms)} 个平台")

    async def start_all(self) -> None:
        """启动所有平台适配器"""
        logger.info("启动所有平台适配器...")
        for platform_id, platform in self.platforms.items():
            try:
                await platform.start()
                logger.info(f"平台 {platform_id} 已启动")
            except Exception as e:
                logger.error(f"启动平台 {platform_id} 失败: {e}")

    async def stop_all(self) -> None:
        """停止所有平台适配器"""
        logger.info("停止所有平台适配器...")
        for platform_id, platform in self.platforms.items():
            try:
                await platform.stop()
                logger.info(f"平台 {platform_id} 已停止")
            except Exception as e:
                logger.error(f"停止平台 {platform_id} 失败: {e}")

    async def send_message(
        self,
        platform_id: str,
        message_type: str,
        target_id: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """通过指定平台发送消息

        Args:
            platform_id: 平台ID
            message_type: 消息类型（private/group）
            target_id: 目标ID
            message: 消息内容
            **kwargs: 其他参数

        Returns:
            发送结果
        """
        platform = self.platforms.get(platform_id)
        if not platform:
            return {"status": "failed", "message": f"平台 {platform_id} 不存在"}

        return await platform.send_message(message_type, target_id, message, **kwargs)

    def get_platform(self, platform_id: str) -> Optional[BasePlatform]:
        """获取平台适配器"""
        return self.platforms.get(platform_id)

    def get_all_platforms(self) -> Dict[str, BasePlatform]:
        """获取所有平台适配器"""
        return self.platforms

    def get_enabled_platforms(self) -> Dict[str, BasePlatform]:
        """获取所有已启用的平台适配器"""
        return {pid: p for pid, p in self.platforms.items() if p.is_enabled()}

    def get_available_platforms(self) -> list[Dict[str, Any]]:
        """获取所有可用的平台类型"""
        return get_all_platforms()

    def get_all_stats(self) -> list[Dict[str, Any]]:
        """获取所有平台的统计信息

        Returns:
            包含所有平台统计信息的列表
        """
        stats = []
        for platform_id, platform in self.platforms.items():
            stats.append(platform.get_stats())
        return stats
