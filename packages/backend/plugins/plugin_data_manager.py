"""插件数据管理器

提供插件数据目录管理和配置 schema 支持
"""

import json
import os
from pathlib import Path
from typing import Any, Optional, Dict
from loguru import logger


class PluginDataManager:
    """插件数据管理器

    管理插件的数据目录和配置文件
    """

    def __init__(self, base_data_dir: str = "data"):
        """初始化插件数据管理器

        Args:
            base_data_dir: 基础数据目录路径
        """
        self.base_data_dir = Path(base_data_dir)
        self.base_data_dir.mkdir(parents=True, exist_ok=True)

        # 插件数据目录（新版本）
        self.plugin_data_dir = self.base_data_dir / "plugin_data"
        self.plugin_data_dir.mkdir(parents=True, exist_ok=True)

        # 插件数据目录（旧版本兼容）
        self.plugins_data_dir = self.base_data_dir / "plugins_data"
        self.plugins_data_dir.mkdir(parents=True, exist_ok=True)

    def get_plugin_data_dir(self, plugin_name: str) -> Path:
        """获取插件的数据目录

        Args:
            plugin_name: 插件名称

        Returns:
            插件数据目录路径
        """
        # 优先使用新版本的 plugin_data 目录
        data_dir = self.plugin_data_dir / plugin_name
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    def get_plugin_data_file(self, plugin_name: str, filename: str) -> Path:
        """获取插件的数据文件路径

        Args:
            plugin_name: 插件名称
            filename: 文件名

        Returns:
            数据文件路径
        """
        data_dir = self.get_plugin_data_dir(plugin_name)
        return data_dir / filename

    def get_plugin_config_file(self, plugin_name: str) -> Path:
        """获取插件的配置文件路径

        Args:
            plugin_name: 插件名称

        Returns:
            配置文件路径
        """
        data_dir = self.get_plugin_data_dir(plugin_name)
        return data_dir / "config.json"

    def load_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """加载插件配置

        Args:
            plugin_name: 插件名称

        Returns:
            配置字典
        """
        config_file = self.get_plugin_config_file(plugin_name)
        if not config_file.exists():
            return {}

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载插件 {plugin_name} 配置失败: {e}")
            return {}

    def save_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """保存插件配置

        Args:
            plugin_name: 插件名称
            config: 配置字典

        Returns:
            是否保存成功
        """
        config_file = self.get_plugin_config_file(plugin_name)
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"保存插件 {plugin_name} 配置失败: {e}")
            return False

    def delete_plugin_data(self, plugin_name: str) -> bool:
        """删除插件数据目录

        Args:
            plugin_name: 插件名称

        Returns:
            是否删除成功
        """
        # 删除新版本的数据目录
        new_data_dir = self.plugin_data_dir / plugin_name
        deleted = False

        if new_data_dir.exists():
            try:
                import shutil

                shutil.rmtree(new_data_dir)
                logger.info(f"已删除插件 {plugin_name} 的数据目录 (plugin_data)")
                deleted = True
            except Exception as e:
                logger.warning(f"删除插件数据目录失败 (plugin_data): {e}")

        # 删除旧版本的数据目录（兼容）
        old_data_dir = self.plugins_data_dir / f"{plugin_name}_data.json"
        if old_data_dir.exists():
            try:
                old_data_dir.unlink()
                logger.info(f"已删除插件 {plugin_name} 的数据文件 (plugins_data)")
                deleted = True
            except Exception as e:
                logger.warning(f"删除插件数据文件失败 (plugins_data): {e}")

        return deleted

    def load_conf_schema(self, plugin_path: Path) -> Optional[Dict[str, Any]]:
        """加载插件的配置 schema

        Args:
            plugin_path: 插件目录路径

        Returns:
            配置 schema 字典，如果不存在则返回 None
        """
        schema_file = plugin_path / "_conf_schema.json"
        if not schema_file.exists():
            return None

        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载插件配置 schema 失败: {e}")
            return None

    def get_all_plugin_data_dirs(self) -> list[Path]:
        """获取所有插件数据目录

        Returns:
            插件数据目录列表
        """
        if not self.plugin_data_dir.exists():
            return []

        return [d for d in self.plugin_data_dir.iterdir() if d.is_dir()]

    def get_plugin_data_size(self, plugin_name: str) -> int:
        """获取插件数据目录大小

        Args:
            plugin_name: 插件名称

        Returns:
            数据目录大小（字节）
        """
        data_dir = self.get_plugin_data_dir(plugin_name)
        if not data_dir.exists():
            return 0

        total_size = 0
        for item in data_dir.rglob("*"):
            if item.is_file():
                total_size += item.stat().st_size
            elif item.is_dir():
                for sub_item in item.rglob("*"):
                    if sub_item.is_file():
                        total_size += sub_item.stat().st_size

        return total_size


# 创建全局插件数据管理器实例
plugin_data_manager = PluginDataManager()
