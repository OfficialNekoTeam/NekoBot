"""数据库迁移管理模块

参考 AstrBot 的数据库迁移实现
"""

from typing import List, Dict, Any, Optional, Callable
from loguru import logger
from pathlib import Path



class Migration:
    """数据库迁移基类"""

    name: str
    """迁移名称"""

    version: str
    """迁移版本"""

    description: str
    """迁移描述"""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    @property
    def applied_key(self) -> str:
        """获取应用记录键名"""
        return f"migration_{self.name}"

    async def check_applied(self) -> bool:
        """检查是否已应用"""
        from .database import db_manager
        migration_record = db_manager.get_migration(self.name)
        return migration_record is not None and migration_record["applied"]

    async def apply(self) -> None:
        """应用迁移（需要子类实现）"""
        raise NotImplementedError

    async def rollback(self) -> None:
        """回滚迁移（可选）"""
        pass



class MigrationManager:
    """数据库迁移管理器"""

    def __init__(self, db_manager, migrations_dir: Optional[Path] = None):
        """初始化迁移管理器

        Args:
            db_manager: 数据库管理器
            migrations_dir: 迁移文件目录
        """
        self.db_manager = db_manager
        self.migrations_dir = migrations_dir or Path(__file__).parent / "migrations"
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        self._migrations: Dict[str, Migration] = {}

    def register_migration(self, migration: Migration) -> None:
        """注册迁移

        Args:
            migration: 迁移实例
        """
        if migration.name in self._migrations:
            logger.warning(f"迁移 {migration.name} 已存在，将被覆盖")
        self._migrations[migration.name] = migration
        logger.debug(f"注册迁移: {migration.name} ({migration.version})")

    def get_pending_migrations(self) -> List[Migration]:
        """获取待应用的迁移

        Returns:
            待应用的迁移列表（按版本排序）
        """
        pending = []
        for name, migration in self._migrations.items():
            import asyncio
            if not asyncio.run(migration.check_applied()):
                pending.append(migration)

        pending.sort(key=lambda m: m.version)
        return pending

    async def apply_migration(self, name: str) -> bool:
        """应用指定的迁移

        Args:
            name: 迁移名称

        Returns:
            是否应用成功
        """
        migration = self._migrations.get(name)
        if not migration:
            logger.error(f"迁移 {name} 不存在")
            return False

        try:
            logger.info(f"开始应用迁移: {name} ({migration.version})")

            if await migration.check_applied():
                logger.info(f"迁移 {name} 已应用，跳过")
                return True

            await migration.apply()

            self.db_manager.apply_migration(name)
            logger.info(f"迁移 {name} 应用成功")
            return True

        except Exception as e:
            logger.error(f"迁移 {name} 应用失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def apply_all(self) -> Dict[str, bool]:
        """应用所有待处理的迁移

        Returns:
            迁移名称到成功状态的映射
        """
        pending = self.get_pending_migrations()
        if not pending:
            logger.info("没有待应用的迁移")
            return {}

        logger.info(f"发现 {len(pending)} 个待应用的迁移")
        results = {}

        for migration in pending:
            success = await self.apply_migration(migration.name)
            results[migration.name] = success

            if not success:
                logger.error(f"迁移 {migration.name} 失败，停止后续迁移")
                break

        return results

    def list_migrations(self) -> List[Dict[str, Any]]:
        """列出所有迁移

        Returns:
            迁移信息列表
        """
        all_migrations = []
        db_records = {m["name"]: m for m in self.db_manager.get_all_migrations()}

        for name, migration in sorted(self._migrations.items(), key=lambda x: x[1].version):
            record = db_records.get(name)
            all_migrations.append({
                "name": name,
                "version": migration.version,
                "description": migration.description,
                "applied": record["applied"] if record else False,
                "applied_at": record["applied_at"] if record else None,
            })

        return all_migrations

    async def rollback_migration(self, name: str) -> bool:
        """回滚指定的迁移

        Args:
            name: 迁移名称

        Returns:
            是否回滚成功
        """
        migration = self._migrations.get(name)
        if not migration:
            logger.error(f"迁移 {name} 不存在")
            return False

        try:
            logger.info(f"开始回滚迁移: {name}")
            await migration.rollback()
            logger.info(f"迁移 {name} 回滚成功")
            return True
        except Exception as e:
            logger.error(f"迁移 {name} 回滚失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
