"""统一的指标管理模块

参考 AstrBot 的 Metric 实现，支持指标上传和安装 ID 跟踪
"""

import os
import socket
import uuid
import aiohttp
from typing import Optional, Dict, Any
from loguru import logger
from pathlib import Path

from .version import NEKOBOT_VERSION



class Metric:
    """指标管理工具类"""

    _iid_cache: Optional[str] = None

    @staticmethod
    def get_installation_id() -> str:
        """获取或创建一个唯一的安装 ID"""
        if Metric._iid_cache is not None:
            return Metric._iid_cache

        config_dir = Path(os.path.expanduser("~")) / ".nekobot"
        id_file = config_dir / ".installation_id"

        if id_file.exists():
            try:
                with open(id_file) as f:
                    Metric._iid_cache = f.read().strip()
                    return Metric._iid_cache
            except Exception:
                pass

        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            installation_id = str(uuid.uuid4())
            with open(id_file, "w") as f:
                f.write(installation_id)
            Metric._iid_cache = installation_id
            return installation_id
        except Exception:
            Metric._iid_cache = "null"
            return "null"

    @staticmethod
    async def upload(**kwargs: Dict[str, Any]) -> None:
        """上传相关非敏感的指标以更好地了解 NekoBot 的使用情况。

        上传的指标不会包含任何有关消息文本、用户信息等敏感信息。

        Args:
            **kwargs: 指标数据
        """
        base_url = "https://tickstats.soulter.top/api/metric/90a6c2a1"
        kwargs["v"] = NEKOBOT_VERSION
        kwargs["os"] = os.sys.platform if hasattr(os, "sys") else "unknown"
        payload = {"metrics_data": kwargs}

        try:
            kwargs["hn"] = socket.gethostname()
        except Exception:
            pass

        try:
            kwargs["iid"] = Metric.get_installation_id()
        except Exception:
            pass

        async with aiohttp.ClientSession(trust_env=True) as session:
            try:
                async with session.post(base_url, json=payload, timeout=3) as response:
                    if response.status != 200:
                        logger.debug(f"指标上传失败: {response.status}")
            except Exception:
                pass

    @staticmethod
    async def record_platform_stats(
        platform_id: str,
        platform_type: str,
        count: int = 1
    ) -> bool:
        """记录平台统计指标

        Args:
            platform_id: 平台ID
            platform_type: 平台类型
            count: 消息数量

        Returns:
            是否记录成功
        """
        try:
            from .platform_stats import PlatformStats
            from .database import db_manager

            success = await PlatformStats.insert_platform_stats(
                platform_id=platform_id,
                platform_type=platform_type,
                count=count,
                db_manager=db_manager
            )

            if success:
                await Metric.upload(
                    adapter_name=platform_id,
                    adapter_type=platform_type,
                    msg_event_tick=count
                )

            return success

        except Exception as e:
            logger.error(f"记录平台统计失败: {e}")
            return False

    @staticmethod
    def get_hostname() -> str:
        """获取主机名"""
        try:
            return socket.gethostname()
        except Exception:
            return "unknown"

    @staticmethod
    def get_system_info() -> Dict[str, str]:
        """获取系统信息

        Returns:
            系统信息字典
        """
        import platform as sys_platform

        return {
            "system": sys_platform.system(),
            "machine": sys_platform.machine(),
            "python_version": sys_platform.python_version(),
            "hostname": Metric.get_hostname(),
            "installation_id": Metric.get_installation_id(),
        }
