"""数据库管理模块

使用SQLite存储所有数据，包括用户、插件、平台等
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from loguru import logger

# 数据库路径
DATABASE_PATH = Path(__file__).parent.parent.parent / "data" / "data.db"


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, db_path: Optional[Path] = None):
        """初始化数据库管理器

        Args:
            db_path: 数据库文件路径，默认为data/data.db
        """
        self.db_path = db_path or DATABASE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self) -> None:
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 用户表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    hashed_password TEXT NOT NULL,
                    first_login INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 登录尝试记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    failed_attempts INTEGER DEFAULT 0,
                    locked INTEGER DEFAULT 0,
                    lock_time TEXT,
                    first_attempt TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_attempt TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, ip_address)
                )
            """)

            # 令牌黑名单表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_blacklist (
                    token TEXT PRIMARY KEY,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 操作日志表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT NOT NULL,
                    username TEXT NOT NULL,
                    ip_address TEXT,
                    details TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 平台表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS platforms (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    enable INTEGER DEFAULT 1,
                    config TEXT,
                    version INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TEXT
                )
            """)

            # 平台变更历史表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS platforms_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    old_data TEXT,
                    new_data TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    operator TEXT
                )
            """)

            # 插件数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS plugin_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plugin_name TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(plugin_name, key)
                )
            """)

            # 插件配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS plugin_configs (
                    plugin_name TEXT PRIMARY KEY,
                    config TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 迁移记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    applied INTEGER DEFAULT 0,
                    applied_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 工具提示词表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tool_prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL UNIQUE,
                    prompt TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 系统提示词表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    prompt TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 人格表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS personalities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    prompt TEXT NOT NULL,
                    description TEXT,
                    enabled INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 长期记忆表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS long_term_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    platform_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    memory_type TEXT DEFAULT 'general',
                    tags TEXT,
                    importance INTEGER DEFAULT 0,
                    access_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_accessed_at TEXT
                )
            """)

            # 记忆标签表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_name TEXT NOT NULL UNIQUE,
                    color TEXT DEFAULT '#1976D2',
                    description TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 记忆与标签关联表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_tag_relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    FOREIGN KEY (memory_id) REFERENCES long_term_memories(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES memory_tags(id) ON DELETE CASCADE,
                    UNIQUE(memory_id, tag_id)
                )
            """)

            # 统计数据缓存表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stats_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT NOT NULL UNIQUE,
                    data TEXT NOT NULL,
                    cached_at TEXT NOT NULL,
                    ttl INTEGER NOT NULL DEFAULT 300
                )
            """)

            # 创建长期记忆相关索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_user ON long_term_memories(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_platform ON long_term_memories(platform_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON long_term_memories(memory_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_importance ON long_term_memories(importance DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_updated ON long_term_memories(updated_at DESC)")

            conn.commit()
            logger.info("数据库表结构初始化完成")

    # ========== 用户相关操作 ==========

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """获取用户信息

        Args:
            username: 用户名

        Returns:
            用户信息字典，如果不存在则返回None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT username, hashed_password, first_login, created_at, updated_at FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "username": row["username"],
                    "hashed_password": row["hashed_password"],
                    "first_login": bool(row["first_login"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            return None

    def create_user(self, username: str, hashed_password: str, first_login: bool = True) -> bool:
        """创建用户

        Args:
            username: 用户名
            hashed_password: 密码哈希
            first_login: 是否首次登录

        Returns:
            是否创建成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, hashed_password, first_login) VALUES (?, ?, ?)",
                    (username, hashed_password, 1 if first_login else 0)
                )
                conn.commit()
                logger.info(f"用户 {username} 创建成功")
                return True
        except sqlite3.IntegrityError:
            logger.warning(f"用户 {username} 已存在")
            return False
        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            return False

    def update_user_password(self, username: str, hashed_password: str) -> bool:
        """更新用户密码

        Args:
            username: 用户名
            hashed_password: 新密码哈希

        Returns:
            是否更新成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET hashed_password = ?, first_login = 0, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
                    (hashed_password, username)
                )
                conn.commit()
                logger.info(f"用户 {username} 密码更新成功")
                return True
        except Exception as e:
            logger.error(f"更新用户密码失败: {e}")
            return False

    def get_all_users(self) -> List[Dict[str, Any]]:
        """获取所有用户

        Returns:
            用户信息列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, hashed_password, first_login, created_at, updated_at FROM users")
            rows = cursor.fetchall()
            return [
                {
                    "username": row["username"],
                    "hashed_password": row["hashed_password"],
                    "first_login": bool(row["first_login"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]

    # ========== 登录尝试相关操作 ==========

    def get_login_attempts(self, username: str, ip_address: str) -> Optional[Dict[str, Any]]:
        """获取登录尝试记录

        Args:
            username: 用户名
            ip_address: IP地址

        Returns:
            登录尝试记录，如果不存在则返回None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM login_attempts WHERE username = ? AND ip_address = ?",
                (username, ip_address)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "username": row["username"],
                    "ip_address": row["ip_address"],
                    "failed_attempts": row["failed_attempts"],
                    "locked": bool(row["locked"]),
                    "lock_time": row["lock_time"],
                    "first_attempt": row["first_attempt"],
                    "last_attempt": row["last_attempt"],
                }
            return None

    def create_login_attempts(self, username: str, ip_address: str) -> bool:
        """创建登录尝试记录

        Args:
            username: 用户名
            ip_address: IP地址

        Returns:
            是否创建成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO login_attempts (username, ip_address) VALUES (?, ?)",
                    (username, ip_address)
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            logger.error(f"创建登录尝试记录失败: {e}")
            return False

    def increment_login_attempts(self, username: str, ip_address: str) -> bool:
        """增加登录失败次数

        Args:
            username: 用户名
            ip_address: IP地址

        Returns:
            是否更新成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE login_attempts SET failed_attempts = failed_attempts + 1, last_attempt = CURRENT_TIMESTAMP WHERE username = ? AND ip_address = ?",
                    (username, ip_address)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"增加登录失败次数失败: {e}")
            return False

    def lock_login_attempts(self, username: str, ip_address: str) -> bool:
        """锁定登录尝试

        Args:
            username: 用户名
            ip_address: IP地址

        Returns:
            是否锁定成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE login_attempts SET locked = 1, lock_time = CURRENT_TIMESTAMP WHERE username = ? AND ip_address = ?",
                    (username, ip_address)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"锁定登录尝试失败: {e}")
            return False

    def reset_login_attempts(self, username: str, ip_address: str) -> bool:
        """重置登录尝试记录

        Args:
            username: 用户名
            ip_address: IP地址

        Returns:
            是否重置成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM login_attempts WHERE username = ? AND ip_address = ?",
                    (username, ip_address)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"重置登录尝试记录失败: {e}")
            return False

    # ========== 令牌黑名单相关操作 ==========

    def add_token_to_blacklist(self, token: str) -> bool:
        """添加令牌到黑名单

        Args:
            token: JWT令牌

        Returns:
            是否添加成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO token_blacklist (token) VALUES (?)",
                    (token,)
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            logger.error(f"添加令牌到黑名单失败: {e}")
            return False

    def is_token_blacklisted(self, token: str) -> bool:
        """检查令牌是否在黑名单中

        Args:
            token: JWT令牌

        Returns:
            是否在黑名单中
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM token_blacklist WHERE token = ?",
                (token,)
            )
            return cursor.fetchone() is not None

    def remove_token_from_blacklist(self, token: str) -> bool:
        """从黑名单中移除令牌

        Args:
            token: JWT令牌

        Returns:
            是否移除成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM token_blacklist WHERE token = ?",
                    (token,)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"从黑名单中移除令牌失败: {e}")
            return False

    # ========== 操作日志相关操作 ==========

    def add_operation_log(
        self,
        operation: str,
        username: str,
        ip_address: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """添加操作日志

        Args:
            operation: 操作类型
            username: 用户名
            ip_address: IP地址
            details: 详细信息

        Returns:
            是否添加成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO operation_logs (operation, username, ip_address, details) VALUES (?, ?, ?, ?)",
                    (operation, username, ip_address, json.dumps(details) if details else None)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"添加操作日志失败: {e}")
            return False

    def get_operation_logs(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取操作日志

        Args:
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            操作日志列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM operation_logs ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "operation": row["operation"],
                    "username": row["username"],
                    "ip_address": row["ip_address"],
                    "details": json.loads(row["details"]) if row["details"] else None,
                    "timestamp": row["timestamp"],
                }
                for row in rows
            ]

    # ========== 平台相关操作 ==========

    def get_platform(self, platform_id: str) -> Optional[Dict[str, Any]]:
        """获取平台信息

        Args:
            platform_id: 平台ID

        Returns:
            平台信息字典，如果不存在则返回None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM platforms WHERE id = ? AND deleted_at IS NULL",
                (platform_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "type": row["type"],
                    "name": row["name"],
                    "enable": bool(row["enable"]),
                    "config": json.loads(row["config"]) if row["config"] else None,
                    "version": row["version"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            return None

    def create_platform(
        self,
        platform_id: str,
        platform_type: str,
        name: str,
        enable: bool = True,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """创建平台

        Args:
            platform_id: 平台ID
            platform_type: 平台类型
            name: 平台名称
            enable: 是否启用
            config: 平台配置

        Returns:
            是否创建成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO platforms (id, type, name, enable, config) VALUES (?, ?, ?, ?, ?)",
                    (platform_id, platform_type, name, 1 if enable else 0, json.dumps(config) if config else None)
                )
                conn.commit()
                logger.info(f"平台 {name} (ID: {platform_id}) 创建成功")
                return True
        except sqlite3.IntegrityError:
            logger.warning(f"平台 {platform_id} 已存在")
            return False
        except Exception as e:
            logger.error(f"创建平台失败: {e}")
            return False

    def update_platform(
        self,
        platform_id: str,
        name: Optional[str] = None,
        enable: Optional[bool] = None,
        config: Optional[Dict[str, Any]] = None,
        version: Optional[int] = None
    ) -> bool:
        """更新平台

        Args:
            platform_id: 平台ID
            name: 平台名称
            enable: 是否启用
            config: 平台配置
            version: 版本号（乐观锁）

        Returns:
            是否更新成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 获取旧数据
                cursor.execute(
                    "SELECT * FROM platforms WHERE id = ? AND deleted_at IS NULL",
                    (platform_id,)
                )
                old_row = cursor.fetchone()
                if not old_row:
                    return False

                # 检查版本号
                if version is not None:
                    version = old_row["version"]
                elif version != old_row["version"]:
                    return False

                # 构建更新语句
                updates = []
                params = []
                if name is not None:
                    updates.append("name = ?")
                    params.append(name)
                if enable is not None:
                    updates.append("enable = ?")
                    params.append(1 if enable else 0)
                if config is not None:
                    updates.append("config = ?")
                    params.append(json.dumps(config))
                updates.append("version = version + 1")
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(platform_id)

                cursor.execute(
                    f"UPDATE platforms SET {', '.join(updates)} WHERE id = ?",
                    params
                )
                conn.commit()
                logger.info(f"平台 {platform_id} 更新成功")
                return True
        except Exception as e:
            logger.error(f"更新平台失败: {e}")
            return False

    def delete_platform(self, platform_id: str) -> bool:
        """软删除平台

        Args:
            platform_id: 平台ID

        Returns:
            是否删除成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE platforms SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (platform_id,)
                )
                conn.commit()
                logger.info(f"平台 {platform_id} 删除成功")
                return True
        except Exception as e:
            logger.error(f"删除平台失败: {e}")
            return False

    def list_platforms(
        self,
        status: Optional[str] = None,
        platform_type: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """列出平台

        Args:
            status: 状态筛选（enabled/disabled）
            platform_type: 类型筛选
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            平台信息列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM platforms WHERE deleted_at IS NULL"
            params = []

            if status == "enabled":
                query += " AND enable = 1"
            elif status == "disabled":
                query += " AND enable = 0"

            if platform_type:
                query += " AND type = ?"
                params.append(platform_type)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "type": row["type"],
                    "name": row["name"],
                    "enable": bool(row["enable"]),
                    "config": json.loads(row["config"]) if row["config"] else None,
                    "version": row["version"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]

    def count_platforms(
        self,
        status: Optional[str] = None,
        platform_type: Optional[str] = None
    ) -> int:
        """统计平台数量

        Args:
            status: 状态筛选
            platform_type: 类型筛选

        Returns:
            平台数量
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT COUNT(*) FROM platforms WHERE deleted_at IS NULL"
            params = []

            if status == "enabled":
                query += " AND enable = 1"
            elif status == "disabled":
                query += " AND enable = 0"

            if platform_type:
                query += " AND type = ?"
                params.append(platform_type)

            cursor.execute(query, params)
            return cursor.fetchone()[0]

    def add_platform_history(
        self,
        platform_id: str,
        operation: str,
        old_data: Optional[Dict[str, Any]] = None,
        new_data: Optional[Dict[str, Any]] = None,
        operator: Optional[str] = None
    ) -> bool:
        """添加平台变更历史

        Args:
            platform_id: 平台ID
            operation: 操作类型
            old_data: 旧数据
            new_data: 新数据
            operator: 操作人

        Returns:
            是否添加成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO platforms_history (platform_id, operation, old_data, new_data, operator) VALUES (?, ?, ?, ?, ?)",
                    (
                        platform_id,
                        operation,
                        json.dumps(old_data) if old_data else None,
                        json.dumps(new_data) if new_data else None,
                        operator
                    )
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"添加平台变更历史失败: {e}")
            return False

    # ========== 插件数据相关操作 ==========

    def get_plugin_data(self, plugin_name: str, key: str) -> Optional[str]:
        """获取插件数据

        Args:
            plugin_name: 插件名称
            key: 数据键

        Returns:
            数据值，如果不存在则返回None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM plugin_data WHERE plugin_name = ? AND key = ?",
                (plugin_name, key)
            )
            row = cursor.fetchone()
            return row["value"] if row else None

    def set_plugin_data(self, plugin_name: str, key: str, value: str) -> bool:
        """设置插件数据

        Args:
            plugin_name: 插件名称
            key: 数据键
            value: 数据值

        Returns:
            是否设置成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO plugin_data (plugin_name, key, value) VALUES (?, ?, ?)
                    ON CONFLICT(plugin_name, key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP
                    """,
                    (plugin_name, key, value, value)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"设置插件数据失败: {e}")
            return False

    def delete_plugin_data(self, plugin_name: str, key: Optional[str] = None) -> bool:
        """删除插件数据

        Args:
            plugin_name: 插件名称
            key: 数据键，如果为None则删除所有数据

        Returns:
            是否删除成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if key:
                    cursor.execute(
                        "DELETE FROM plugin_data WHERE plugin_name = ? AND key = ?",
                        (plugin_name, key)
                    )
                else:
                    cursor.execute(
                        "DELETE FROM plugin_data WHERE plugin_name = ?",
                        (plugin_name,)
                    )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"删除插件数据失败: {e}")
            return False

    def get_plugin_config(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """获取插件配置

        Args:
            plugin_name: 插件名称

        Returns:
            配置字典，如果不存在则返回None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT config FROM plugin_configs WHERE plugin_name = ?",
                (plugin_name,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row["config"])
            return None

    def set_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """设置插件配置

        Args:
            plugin_name: 插件名称
            config: 配置字典

        Returns:
            是否设置成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO plugin_configs (plugin_name, config) VALUES (?, ?)
                    ON CONFLICT(plugin_name) DO UPDATE SET config = ?, updated_at = CURRENT_TIMESTAMP
                    """,
                    (plugin_name, json.dumps(config), json.dumps(config))
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"设置插件配置失败: {e}")
            return False

    def delete_plugin_config(self, plugin_name: str) -> bool:
        """删除插件配置

        Args:
            plugin_name: 插件名称

        Returns:
            是否删除成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM plugin_configs WHERE plugin_name = ?",
                    (plugin_name,)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"删除插件配置失败: {e}")
            return False

    # ========== 迁移相关操作 ==========

    def get_migration(self, name: str) -> Optional[Dict[str, Any]]:
        """获取迁移记录

        Args:
            name: 迁移名称

        Returns:
            迁移记录，如果不存在则返回None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM migrations WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "applied": bool(row["applied"]),
                    "applied_at": row["applied_at"],
                    "created_at": row["created_at"],
                }
            return None

    def create_migration(self, name: str) -> bool:
        """创建迁移记录

        Args:
            name: 迁移名称

        Returns:
            是否创建成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO migrations (name) VALUES (?)",
                    (name,)
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            logger.error(f"创建迁移记录失败: {e}")
            return False

    def apply_migration(self, name: str) -> bool:
        """应用迁移

        Args:
            name: 迁移名称

        Returns:
            是否应用成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE migrations SET applied = 1, applied_at = CURRENT_TIMESTAMP WHERE name = ?",
                    (name,)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"应用迁移失败: {e}")
            return False

    def get_all_migrations(self) -> List[Dict[str, Any]]:
        """获取所有迁移记录

        Returns:
            迁移记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM migrations ORDER BY id")
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "applied": bool(row["applied"]),
                    "applied_at": row["applied_at"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

    # ========== 工具提示词相关操作 ==========

    def get_tool_prompt(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """获取工具提示词

        Args:
            tool_name: 工具名称

        Returns:
            工具提示词信息，如果不存在则返回None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tool_prompts WHERE tool_name = ?",
                (tool_name,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "tool_name": row["tool_name"],
                    "prompt": row["prompt"],
                    "description": row["description"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            return None

    def create_tool_prompt(self, tool_name: str, prompt: str, description: str = "") -> bool:
        """创建工具提示词

        Args:
            tool_name: 工具名称
            prompt: 提示词内容
            description: 描述

        Returns:
            是否创建成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO tool_prompts (tool_name, prompt, description) VALUES (?, ?, ?)",
                    (tool_name, prompt, description)
                )
                conn.commit()
                logger.info(f"工具提示词 {tool_name} 创建成功")
                return True
        except sqlite3.IntegrityError:
            logger.warning(f"工具提示词 {tool_name} 已存在")
            return False
        except Exception as e:
            logger.error(f"创建工具提示词失败: {e}")
            return False

    def update_tool_prompt(self, tool_name: str, prompt: Optional[str] = None, description: Optional[str] = None) -> bool:
        """更新工具提示词

        Args:
            tool_name: 工具名称
            prompt: 新的提示词内容
            description: 新的描述

        Returns:
            是否更新成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建更新语句
                updates = []
                params = []
                if prompt is not None:
                    updates.append("prompt = ?")
                    params.append(prompt)
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(tool_name)
                
                cursor.execute(
                    f"UPDATE tool_prompts SET {', '.join(updates)} WHERE tool_name = ?",
                    params
                )
                conn.commit()
                logger.info(f"工具提示词 {tool_name} 更新成功")
                return True
        except Exception as e:
            logger.error(f"更新工具提示词失败: {e}")
            return False

    def delete_tool_prompt(self, tool_name: str) -> bool:
        """删除工具提示词

        Args:
            tool_name: 工具名称

        Returns:
            是否删除成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM tool_prompts WHERE tool_name = ?",
                    (tool_name,)
                )
                conn.commit()
                logger.info(f"工具提示词 {tool_name} 删除成功")
                return True
        except Exception as e:
            logger.error(f"删除工具提示词失败: {e}")
            return False

    def get_all_tool_prompts(self) -> List[Dict[str, Any]]:
        """获取所有工具提示词

        Returns:
            工具提示词列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tool_prompts ORDER BY id")
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "tool_name": row["tool_name"],
                    "prompt": row["prompt"],
                    "description": row["description"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]

    # ========== 系统提示词相关操作 ==========

    def get_system_prompt(self, name: str) -> Optional[Dict[str, Any]]:
        """获取系统提示词

        Args:
            name: 提示词名称

        Returns:
            系统提示词信息，如果不存在则返回None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM system_prompts WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "prompt": row["prompt"],
                    "description": row["description"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            return None

    def create_system_prompt(self, name: str, prompt: str, description: str = "") -> bool:
        """创建系统提示词

        Args:
            name: 提示词名称
            prompt: 提示词内容
            description: 描述

        Returns:
            是否创建成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO system_prompts (name, prompt, description) VALUES (?, ?, ?)",
                    (name, prompt, description)
                )
                conn.commit()
                logger.info(f"系统提示词 {name} 创建成功")
                return True
        except sqlite3.IntegrityError:
            logger.warning(f"系统提示词 {name} 已存在")
            return False
        except Exception as e:
            logger.error(f"创建系统提示词失败: {e}")
            return False

    def update_system_prompt(self, name: str, prompt: Optional[str] = None, description: Optional[str] = None) -> bool:
        """更新系统提示词

        Args:
            name: 提示词名称
            prompt: 新的提示词内容
            description: 新的描述

        Returns:
            是否更新成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建更新语句
                updates = []
                params = []
                if prompt is not None:
                    updates.append("prompt = ?")
                    params.append(prompt)
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(name)
                
                cursor.execute(
                    f"UPDATE system_prompts SET {', '.join(updates)} WHERE name = ?",
                    params
                )
                conn.commit()
                logger.info(f"系统提示词 {name} 更新成功")
                return True
        except Exception as e:
            logger.error(f"更新系统提示词失败: {e}")
            return False

    def delete_system_prompt(self, name: str) -> bool:
        """删除系统提示词

        Args:
            name: 提示词名称

        Returns:
            是否删除成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM system_prompts WHERE name = ?",
                    (name,)
                )
                conn.commit()
                logger.info(f"系统提示词 {name} 删除成功")
                return True
        except Exception as e:
            logger.error(f"删除系统提示词失败: {e}")
            return False

    def get_all_system_prompts(self) -> List[Dict[str, Any]]:
        """获取所有系统提示词

        Returns:
            系统提示词列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM system_prompts ORDER BY id")
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "prompt": row["prompt"],
                    "description": row["description"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]

    # ========== 人格相关操作 ==========

    def get_personality(self, name: str) -> Optional[Dict[str, Any]]:
        """获取人格信息

        Args:
            name: 人格名称

        Returns:
            人格信息，如果不存在则返回None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM personalities WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "prompt": row["prompt"],
                    "description": row["description"],
                    "enabled": bool(row["enabled"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            return None

    def create_personality(self, name: str, prompt: str, description: str = "", enabled: bool = True) -> bool:
        """创建人格

        Args:
            name: 人格名称
            prompt: 人格提示词内容
            description: 描述
            enabled: 是否启用

        Returns:
            是否创建成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO personalities (name, prompt, description, enabled) VALUES (?, ?, ?, ?)",
                    (name, prompt, description, 1 if enabled else 0)
                )
                conn.commit()
                logger.info(f"人格 {name} 创建成功")
                return True
        except sqlite3.IntegrityError:
            logger.warning(f"人格 {name} 已存在")
            return False
        except Exception as e:
            logger.error(f"创建人格失败: {e}")
            return False

    def update_personality(self, name: str, prompt: Optional[str] = None, description: Optional[str] = None, enabled: Optional[bool] = None) -> bool:
        """更新人格

        Args:
            name: 人格名称
            prompt: 新的人格提示词内容
            description: 新的描述
            enabled: 是否启用

        Returns:
            是否更新成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建更新语句
                updates = []
                params = []
                if prompt is not None:
                    updates.append("prompt = ?")
                    params.append(prompt)
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                if enabled is not None:
                    updates.append("enabled = ?")
                    params.append(1 if enabled else 0)
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(name)
                
                cursor.execute(
                    f"UPDATE personalities SET {', '.join(updates)} WHERE name = ?",
                    params
                )
                conn.commit()
                logger.info(f"人格 {name} 更新成功")
                return True
        except Exception as e:
            logger.error(f"更新人格失败: {e}")
            return False

    def delete_personality(self, name: str) -> bool:
        """删除人格

        Args:
            name: 人格名称

        Returns:
            是否删除成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM personalities WHERE name = ?",
                    (name,)
                )
                conn.commit()
                logger.info(f"人格 {name} 删除成功")
                return True
        except Exception as e:
            logger.error(f"删除人格失败: {e}")
            return False

    def get_all_personalities(self) -> List[Dict[str, Any]]:
        """获取所有人格

        Returns:
            人格列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM personalities ORDER BY id")
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "prompt": row["prompt"],
                    "description": row["description"],
                    "enabled": bool(row["enabled"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]

    def get_enabled_personalities(self) -> List[Dict[str, Any]]:
        """获取所有启用的人格

        Returns:
            启用的人格列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM personalities WHERE enabled = 1 ORDER BY id")
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "prompt": row["prompt"],
                    "description": row["description"],
                    "enabled": bool(row["enabled"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]

    # ========== 统计数据缓存相关操作 ==========

    def get_stats_cache(self, cache_key: str = "default") -> Dict[str, Any]:
        """获取统计数据缓存

        Args:
            cache_key: 缓存键，默认为 "default"

        Returns:
            缓存字典，包含 data, cached_at, ttl 字段，如果不存在则返回空字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data, cached_at, ttl FROM stats_cache WHERE cache_key = ?",
                (cache_key,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "data": json.loads(row["data"]),
                    "cached_at": row["cached_at"],
                    "ttl": row["ttl"],
                }
            return {}

    def set_stats_cache(self, data: Dict[str, Any], ttl: int = 300, cache_key: str = "default") -> bool:
        """设置统计数据缓存

        Args:
            data: 要缓存的数据
            ttl: 缓存过期时间（秒）
            cache_key: 缓存键，默认为 "default"

        Returns:
            是否设置成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO stats_cache (cache_key, data, cached_at, ttl) VALUES (?, ?, CURRENT_TIMESTAMP, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET data = ?, cached_at = CURRENT_TIMESTAMP, ttl = ?
                    """,
                    (cache_key, json.dumps(data), ttl, json.dumps(data), ttl)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"设置统计数据缓存失败: {e}")
            return False

    # 别名方法，用于向后兼容
    def get_migrations(self) -> List[Dict[str, Any]]:
        """获取所有迁移记录（别名方法）

        Returns:
            迁移记录列表
        """
        return self.get_all_migrations()


# 显式导出的符号
__all__ = [
    "DatabaseManager",
    "db_manager"
]

# 创建全局数据库管理器实例
db_manager = DatabaseManager()
