"""会话隔离管理模块

确保不同用户或会话之间的数据与状态完全隔离
"""

from typing import Dict, Optional, Any
from loguru import logger
from .database import BaseDatabase


class SessionIsolationManager:
    """会话隔离管理器"""

    def __init__(self, db: BaseDatabase, config: Dict[str, Any]):
        """初始化会话隔离管理器

        Args:
            db: 数据库实例
            config: 配置字典
        """
        self.db = db
        self.config = config

    def get_isolation_key(self, platform_id: str, user_id: str, group_id: Optional[str] = None, message_type: Optional[str] = None) -> str:
        """获取会话隔离键

        Args:
            platform_id: 平台 ID
            user_id: 用户 ID
            group_id: 群组 ID（可选）
            message_type: 消息类型（group/private）

        Returns:
            隔离键，格式：platform_id:user_id 或 platform_id:group_id
        """
        if message_type == "group" and group_id:
            return f"{platform_id}:group:{group_id}"
        return f"{platform_id}:{user_id}"

    def check_isolation(self, session_id: str, requesting_session_id: str) -> bool:
        """检查会话隔离

        Args:
            session_id: 当前会话 ID
            requesting_session_id: 请求的会话 ID

        Returns:
            True 表示需要隔离，False 表示可以共享
        """
        # 从 session_id 解析平台和用户
        # 格式：platform_id:user_id 或 platform_id:group_id
        parts = session_id.split(":")
        if len(parts) < 2:
            logger.warning(f"无效的会话 ID 格式: {session_id}")
            return True

        platform_part = parts[0]

        # 检查 requesting_session_id 的格式
        requesting_parts = requesting_session_id.split(":")
        if len(requesting_parts) < 2:
            logger.warning(f"无效的请求会话 ID 格式: {requesting_session_id}")
            return True

        requesting_platform_part = requesting_parts[0]

        # 如果平台部分相同，检查是否需要隔离
        if platform_part == requesting_platform_part:
            # 对于相同平台，需要检查用户或群组
            if len(requesting_parts) == 3:
                # 格式：platform_id:group_id
                requesting_group_id = requesting_parts[2]
                if requesting_group_id == parts[1]:
                    # 相同用户和群组的会话可以共享
                    return False
            # 同一用户的会话可以共享
            return True

        # 不同平台，默认隔离
        return True

    def get_session_metadata(self, session_id: str) -> Dict[str, Any]:
        """获取会话的隔离元数据

        Args:
            session_id: 会话 ID

        Returns:
            隔离元数据
        """
        parts = session_id.split(":")
        if len(parts) < 2:
            return {"is_isolated": True, "type": "user", "platform_id": parts[0], "user_id": parts[1]}
        elif len(parts) == 3:
            return {"is_isolated": True, "type": "group", "platform_id": parts[0], "group_id": parts[2]}
        else:
            return {"is_isolated": True, "type": "unknown", "platform_id": "", "user_id": "", "group_id": ""}

    def create_isolation_rule(self, rule: Dict[str, Any]) -> bool:
        """创建会话隔离规则

        Args:
            rule: 规则配置
            {
                "type": "user" | "group" | "custom",
                "target_type": "user" | "group" | "custom_value",
                "allow_access": bool
            }

        Returns:
            是否成功
        """
        try:
            self.db.execute(
                "INSERT INTO session_isolation_rules (type, target_type, target_value, custom_value, allow_access) VALUES (?, ?, ?, ?, ?)",
                (rule["type"], rule.get("target_type", ""), rule.get("target_value", ""), rule.get("custom_value", ""), rule.get("allow_access", True))
            )
            logger.info(f"创建隔离规则: {rule}")
            return True
        except Exception as e:
            logger.error(f"创建隔离规则失败: {e}")
            return False

    def get_isolation_rules(self) -> list[Dict[str, Any]]:
        """获取所有隔离规则"""
        try:
            rows = self.db.execute("SELECT * FROM session_isolation_rules ORDER BY created_at DESC")
            rules = []
            for row in rows:
                rules.append({
                    "type": row["type"],
                    "target_type": row["target_type"],
                    "target_value": row["target_value"],
                    "custom_value": row["custom_value"],
                    "allow_access": row["allow_access"]
                })
            return rules
        except Exception as e:
            logger.error(f"获取隔离规则失败: {e}")
            return []

    def delete_isolation_rule(self, rule_id: int) -> bool:
        """删除隔离规则"""
        try:
            self.db.execute("DELETE FROM session_isolation_rules WHERE id = ?", (rule_id,))
            logger.info(f"删除隔离规则: {rule_id}")
            return True
        except Exception as e:
            logger.error(f"删除隔离规则失败: {e}")
            return False
