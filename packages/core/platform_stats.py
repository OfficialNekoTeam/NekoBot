"""平台统计模块

提供平台消息统计功能
"""

from typing import Dict, Any, List, Optional
from loguru import logger
from datetime import datetime



class PlatformStats:
    """平台统计工具类"""

    @staticmethod
    async def insert_platform_stats(
        platform_id: str,
        platform_type: str,
        count: int = 1,
        timestamp: Optional[str] = None,
        db_manager=None
    ) -> bool:
        """插入平台统计数据

        Args:
            platform_id: 平台ID
            platform_type: 平台类型
            count: 消息数量
            timestamp: 时间戳（默认按小时）
            db_manager: 数据库管理器实例

        Returns:
            是否插入成功
        """
        if db_manager is None:
            from .database import db_manager

        try:
            if timestamp is None:
                timestamp = datetime.now().replace(minute=0, second=0, microsecond=0).isoformat()

            success = db_manager.insert_platform_stats(
                platform_id=platform_id,
                platform_type=platform_type,
                count=count,
                timestamp=timestamp
            )

            if success:
                logger.debug(f"平台统计已记录: {platform_type} ({platform_id}) - {count} 条消息")

            return success

        except Exception as e:
            logger.error(f"插入平台统计失败: {e}")
            return False

    @staticmethod
    async def get_platform_stats(
        platform_id: Optional[str] = None,
        platform_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        db_manager=None
    ) -> List[Dict[str, Any]]:
        """获取平台统计数据

        Args:
            platform_id: 平台ID
            platform_type: 平台类型
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
            db_manager: 数据库管理器实例

        Returns:
            平台统计数据列表
        """
        if db_manager is None:
            from .database import db_manager

        try:
            return db_manager.get_platform_stats(
                platform_id=platform_id,
                platform_type=platform_type,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )
        except Exception as e:
            logger.error(f"获取平台统计失败: {e}")
            return []

    @staticmethod
    async def count_platform_stats(
        platform_id: Optional[str] = None,
        platform_type: Optional[str] = None,
        db_manager=None
    ) -> int:
        """统计平台记录数量

        Args:
            platform_id: 平台ID
            platform_type: 平台类型
            db_manager: 数据库管理器实例

        Returns:
            记录数量
        """
        if db_manager is None:
            from .database import db_manager

        try:
            return db_manager.count_platform_stats(
                platform_id=platform_id,
                platform_type=platform_type
            )
        except Exception as e:
            logger.error(f"统计平台记录失败: {e}")
            return 0

    @staticmethod
    async def get_aggregate_stats(
        platform_type: Optional[str] = None,
        days: int = 7,
        db_manager=None
    ) -> Dict[str, Any]:
        """获取聚合统计数据

        Args:
            platform_type: 平台类型
            days: 最近多少天
            db_manager: 数据库管理器实例

        Returns:
            聚合统计数据
        """
        stats = await PlatformStats.get_platform_stats(
            platform_type=platform_type,
            limit=days * 24,
            db_manager=db_manager
        )

        if not stats:
            return {
                "total_messages": 0,
                "daily_average": 0,
                "peak_hour": None,
                "platform_breakdown": {}
            }

        total_messages = sum(s["count"] for s in stats)
        daily_average = total_messages / days if days > 0 else 0

        hour_counts: Dict[str, int] = {}
        platform_breakdown: Dict[str, int] = {}

        for s in stats:
            hour = s["timestamp"].split("T")[1][:2]
            hour_counts[hour] = hour_counts.get(hour, 0) + s["count"]
            platform_breakdown[s["platform_type"]] = (
                platform_breakdown.get(s["platform_type"], 0) + s["count"]
            )

        peak_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else None

        return {
            "total_messages": total_messages,
            "daily_average": int(daily_average),
            "peak_hour": peak_hour,
            "platform_breakdown": platform_breakdown
        }
