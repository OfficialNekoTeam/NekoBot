"""备份和恢复 API

提供数据备份、恢复和备份管理功能
"""

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
from quart import request, send_file

from .route import Route, Response, RouteContext

# 备份目录
BACKUP_DIR = Path(__file__).parent.parent.parent / "data" / "backups"
# 数据库路径
DATABASE_PATH = Path(__file__).parent.parent.parent / "data" / "data.db"
# 配置文件目录
CONFIG_DIR = Path(__file__).parent.parent.parent / "data"
# 备份元数据文件
BACKUP_METADATA_FILE = "backup_metadata.json"

# 需要备份的文件列表
BACKUP_FILES = [
    "cmd_config.json",
    "platforms_sources.json",
    "llm_providers.json",
    "config.json",
    "users.json",
    "data.db",
]


class BackupRoute(Route):
    """备份和恢复路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.backup_dir = BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.routes = [
            ("/api/backups", "GET", self.list_backups),
            ("/api/backups", "POST", self.create_backup),
            ("/api/backups/<backup_id>", "GET", self.get_backup),
            ("/api/backups/<backup_id>", "DELETE", self.delete_backup),
            ("/api/backups/<backup_id>/restore", "POST", self.restore_backup),
            ("/api/backups/<backup_id>/download", "GET", self.download_backup),
            ("/api/backups/settings", "GET", self.get_backup_settings),
            ("/api/backups/settings", "POST", self.update_backup_settings),
        ]

    def _get_backup_path(self, backup_id: str) -> Path:
        """获取备份目录路径"""
        return self.backup_dir / backup_id

    def _get_backup_metadata_path(self, backup_id: str) -> Path:
        """获取备份元数据文件路径"""
        return self._get_backup_path(backup_id) / BACKUP_METADATA_FILE

    def _get_backup_metadata(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """获取备份元数据"""
        metadata_path = self._get_backup_metadata_path(backup_id)
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取备份元数据失败: {e}")
            return None

    def _save_backup_metadata(self, backup_id: str, metadata: Dict[str, Any]) -> bool:
        """保存备份元数据"""
        metadata_path = self._get_backup_metadata_path(backup_id)
        try:
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"保存备份元数据失败: {e}")
            return False

    def _get_backup_size(self, backup_id: str) -> int:
        """获取备份大小（字节）"""
        backup_path = self._get_backup_path(backup_id)
        if not backup_path.exists():
            return 0

        total_size = 0
        for item in backup_path.rglob("*"):
            if item.is_file():
                total_size += item.stat().st_size
        return total_size

    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    def _backup_database(self, backup_path: Path) -> bool:
        """备份数据库"""
        try:
            db_backup_path = backup_path / "data.db"
            if DATABASE_PATH.exists():
                # 使用 SQLite 的备份 API
                source_conn = sqlite3.connect(str(DATABASE_PATH))
                backup_conn = sqlite3.connect(str(db_backup_path))
                
                try:
                    source_conn.backup(backup_conn)
                    return True
                finally:
                    source_conn.close()
                    backup_conn.close()
            return False
        except Exception as e:
            logger.error(f"备份数据库失败: {e}")
            return False

    def _restore_database(self, backup_path: Path) -> bool:
        """恢复数据库"""
        try:
            db_backup_path = backup_path / "data.db"
            if not db_backup_path.exists():
                return False

            # 备份当前数据库
            current_backup_path = self.backup_dir / "current_backup_before_restore"
            current_backup_path.mkdir(parents=True, exist_ok=True)
            if DATABASE_PATH.exists():
                shutil.copy2(DATABASE_PATH, current_backup_path / "data.db")

            # 恢复数据库
            source_conn = sqlite3.connect(str(db_backup_path))
            restore_conn = sqlite3.connect(str(DATABASE_PATH))
            
            try:
                source_conn.backup(restore_conn)
                return True
            finally:
                source_conn.close()
                restore_conn.close()
        except Exception as e:
            logger.error(f"恢复数据库失败: {e}")
            # 尝试恢复之前的备份
            current_backup_path = self.backup_dir / "current_backup_before_restore"
            current_db = current_backup_path / "data.db"
            if current_db.exists():
                shutil.copy2(current_db, DATABASE_PATH)
            return False

    async def list_backups(self) -> Dict[str, Any]:
        """列出所有备份"""
        try:
            backups = []
            
            for backup_dir in sorted(self.backup_dir.iterdir(), reverse=True):
                if not backup_dir.is_dir():
                    continue

                backup_id = backup_dir.name
                metadata = self._get_backup_metadata(backup_id)

                if metadata:
                    backups.append({
                        "id": backup_id,
                        "name": metadata.get("name", backup_id),
                        "description": metadata.get("description", ""),
                        "created_at": metadata.get("created_at", ""),
                        "size": self._format_size(self._get_backup_size(backup_id)),
                        "size_bytes": self._get_backup_size(backup_id),
                        "version": metadata.get("version", ""),
                        "auto_backup": metadata.get("auto_backup", False),
                    })

            return Response().ok(data=backups).to_dict()
        except Exception as e:
            logger.error(f"列出备份失败: {e}")
            return Response().error(f"列出备份失败: {str(e)}").to_dict()

    async def create_backup(self) -> Dict[str, Any]:
        """创建备份"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            name = data.get("name", "")
            description = data.get("description", "")
            auto_backup = data.get("auto_backup", False)

            # 生成备份ID
            backup_id = datetime.now().strftime("backup_%Y%m%d_%H%M%S")
            backup_path = self._get_backup_path(backup_id)
            backup_path.mkdir(parents=True, exist_ok=True)

            # 获取版本信息
            version = ""
            try:
                from ..core.version import get_version_info
                version_info = get_version_info()
                version = version_info.get("version", "")
            except Exception:
                pass

            # 复制文件到备份目录
            for filename in BACKUP_FILES:
                src = CONFIG_DIR / filename
                dst = backup_path / filename
                if src.exists():
                    if filename == "data.db":
                        # 数据库使用特殊备份方法
                        self._backup_database(backup_path)
                    else:
                        shutil.copy2(src, dst)

            # 保存元数据
            now = datetime.utcnow().isoformat()
            metadata = {
                "name": name or backup_id,
                "description": description,
                "created_at": now,
                "version": version,
                "auto_backup": auto_backup,
                "files": BACKUP_FILES,
            }
            self._save_backup_metadata(backup_id, metadata)

            logger.info(f"备份 {backup_id} 创建成功")
            return Response().ok(data={
                "id": backup_id,
                "name": metadata["name"],
                "created_at": now,
                "size": self._format_size(self._get_backup_size(backup_id)),
            }).to_dict()
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return Response().error(f"创建备份失败: {str(e)}").to_dict()

    async def get_backup(self, backup_id: str) -> Dict[str, Any]:
        """获取备份详情"""
        try:
            backup_path = self._get_backup_path(backup_id)
            if not backup_path.exists():
                return Response().error("备份不存在").to_dict()

            metadata = self._get_backup_metadata(backup_id)
            if not metadata:
                return Response().error("备份元数据不存在").to_dict()

            # 获取备份文件列表
            files = []
            for item in backup_path.iterdir():
                if item.is_file() and item.name != BACKUP_METADATA_FILE:
                    files.append({
                        "name": item.name,
                        "size": self._format_size(item.stat().st_size),
                        "size_bytes": item.stat().st_size,
                    })

            return Response().ok(data={
                "id": backup_id,
                "name": metadata.get("name", backup_id),
                "description": metadata.get("description", ""),
                "created_at": metadata.get("created_at", ""),
                "version": metadata.get("version", ""),
                "auto_backup": metadata.get("auto_backup", False),
                "files": files,
                "size": self._format_size(self._get_backup_size(backup_id)),
                "size_bytes": self._get_backup_size(backup_id),
            }).to_dict()
        except Exception as e:
            logger.error(f"获取备份详情失败: {e}")
            return Response().error(f"获取备份详情失败: {str(e)}").to_dict()

    async def delete_backup(self, backup_id: str) -> Dict[str, Any]:
        """删除备份"""
        try:
            backup_path = self._get_backup_path(backup_id)
            if not backup_path.exists():
                return Response().error("备份不存在").to_dict()

            # 删除备份目录
            shutil.rmtree(backup_path)

            logger.info(f"备份 {backup_id} 删除成功")
            return Response().ok(message="备份删除成功").to_dict()
        except Exception as e:
            logger.error(f"删除备份失败: {e}")
            return Response().error(f"删除备份失败: {str(e)}").to_dict()

    async def restore_backup(self, backup_id: str) -> Dict[str, Any]:
        """恢复备份"""
        try:
            backup_path = self._get_backup_path(backup_id)
            if not backup_path.exists():
                return Response().error("备份不存在").to_dict()

            metadata = self._get_backup_metadata(backup_id)
            if not metadata:
                return Response().error("备份元数据不存在").to_dict()

            # 检查版本兼容性
            current_version = ""
            try:
                from ..core.version import get_version_info
                version_info = get_version_info()
                current_version = version_info.get("version", "")
            except Exception:
                pass

            backup_version = metadata.get("version", "")
            if backup_version and backup_version != current_version:
                logger.warning(f"备份版本 ({backup_version}) 与当前版本 ({current_version}) 不同")

            # 恢复数据库
            if not self._restore_database(backup_path):
                return Response().error("恢复数据库失败").to_dict()

            # 恢复配置文件
            for filename in BACKUP_FILES:
                if filename == "data.db":
                    continue  # 数据库已恢复
                
                src = backup_path / filename
                dst = CONFIG_DIR / filename
                if src.exists():
                    shutil.copy2(src, dst)

            logger.info(f"备份 {backup_id} 恢复成功")
            return Response().ok(message="备份恢复成功，请重启应用以生效").to_dict()
        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return Response().error(f"恢复备份失败: {str(e)}").to_dict()

    async def download_backup(self, backup_id: str):
        """下载备份"""
        try:
            backup_path = self._get_backup_path(backup_id)
            if not backup_path.exists():
                return Response().error("备份不存在").to_dict()

            # 创建 ZIP 文件
            import zipfile
            from io import BytesIO

            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for item in backup_path.rglob("*"):
                    if item.is_file():
                        arcname = item.relative_to(backup_path)
                        zipf.write(item, arcname)

            zip_buffer.seek(0)
            
            return await send_file(
                zip_buffer,
                as_attachment=True,
                download_name=f"{backup_id}.zip",
                mimetype='application/zip'
            )
        except Exception as e:
            logger.error(f"下载备份失败: {e}")
            return Response().error(f"下载备份失败: {str(e)}").to_dict()

    async def get_backup_settings(self) -> Dict[str, Any]:
        """获取备份设置"""
        try:
            settings_path = self.backup_dir / "settings.json"
            default_settings = {
                "auto_backup_enabled": False,
                "auto_backup_interval": 7,  # 天
                "max_backups": 10,
                "auto_backup_time": "02:00",
            }

            if settings_path.exists():
                try:
                    with open(settings_path, "r", encoding="utf-8") as f:
                        saved_settings = json.load(f)
                        default_settings.update(saved_settings)
                except Exception as e:
                    logger.error(f"读取备份设置失败: {e}")

            return Response().ok(data=default_settings).to_dict()
        except Exception as e:
            logger.error(f"获取备份设置失败: {e}")
            return Response().error(f"获取备份设置失败: {str(e)}").to_dict()

    async def update_backup_settings(self) -> Dict[str, Any]:
        """更新备份设置"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            settings_path = self.backup_dir / "settings.json"
            
            # 读取现有设置
            default_settings = {
                "auto_backup_enabled": False,
                "auto_backup_interval": 7,
                "max_backups": 10,
                "auto_backup_time": "02:00",
            }

            if settings_path.exists():
                try:
                    with open(settings_path, "r", encoding="utf-8") as f:
                        saved_settings = json.load(f)
                        default_settings.update(saved_settings)
                except Exception:
                    pass

            # 更新设置
            allowed_keys = ["auto_backup_enabled", "auto_backup_interval", "max_backups", "auto_backup_time"]
            for key in allowed_keys:
                if key in data:
                    default_settings[key] = data[key]

            # 保存设置
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(default_settings, f, indent=2, ensure_ascii=False)

            logger.info("备份设置更新成功")
            return Response().ok(message="备份设置更新成功").to_dict()
        except Exception as e:
            logger.error(f"更新备份设置失败: {e}")
            return Response().error(f"更新备份设置失败: {str(e)}").to_dict()