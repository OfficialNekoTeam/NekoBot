"""插件元数据系统

提供完整的插件元数据管理，支持 metadata.yaml 和 info() 方法
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict
from loguru import logger
from pathlib import Path


@dataclass
class PluginMetadata:
    """插件元数据
    
    包含插件的所有元信息，包括：
    - 基本信息：名称、作者、版本、描述
    - 仓库信息：GitHub 仓库地址
    - 展示信息：显示名称、Logo 路径
    - 技术信息：类类型、模块路径、根目录名
    - 状态信息：是否激活、是否保留插件
    - 配置信息：插件配置、Schema
    - 处理器信息：注册的 Handler 名称列表
    """

    # 基本信息
    name: Optional[str] = None
    """插件名称（唯一标识符）"""
    
    author: Optional[str] = None
    """插件作者"""
    
    desc: Optional[str] = None
    """插件描述"""
    
    description: Optional[str] = None
    """插件描述（desc 的别名）"""
    
    version: Optional[str] = None
    """插件版本"""
    
    repo: Optional[str] = None
    """插件仓库地址（如 GitHub 仓库）"""
    
    # 展示信息
    display_name: Optional[str] = None
    """用于展示的插件名称（可选，如与 name 不同）"""
    
    logo_path: Optional[str] = None
    """插件 Logo 文件路径"""
    
    # 技术信息
    star_cls_type: Optional[type] = None
    """插件的类对象类型"""
    
    module_path: Optional[str] = None
    """插件的模块路径"""
    
    root_dir_name: Optional[str] = None
    """插件的根目录名称"""
    
    reserved: bool = False
    """是否是 NekoBot 的保留插件"""
    
    # 状态信息
    activated: bool = True
    """是否被激活"""
    
    # 配置信息
    config: Optional[Any] = None
    """插件配置实例"""
    
    conf_schema: Optional[Dict[str, Any]] = None
    """插件配置 JSON Schema"""
    
    # 处理器信息
    star_handler_full_names: List[str] = field(default_factory=list)
    """注册的 Handler 全名列表"""
    
    commands: Dict[str, Any] = field(default_factory=dict)
    """插件命令字典"""
    
    message_handlers: List[Any] = field(default_factory=list)
    """消息处理器列表"""

    def __post_init__(self):
        """初始化后处理"""
        if self.desc is None and self.description is not None:
            self.desc = self.description
        if self.description is None and self.desc is not None:
            self.description = self.desc

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典
        
        Returns:
            插件元数据字典
        """
        return {
            "name": self.name,
            "author": self.author,
            "desc": self.desc,
            "version": self.version,
            "repo": self.repo,
            "display_name": self.display_name,
            "logo_path": self.logo_path,
            "root_dir_name": self.root_dir_name,
            "reserved": self.reserved,
            "activated": self.activated,
            "commands": list(self.commands.keys()),
            "is_official": self.reserved,
        }

    def __str__(self) -> str:
        """字符串表示"""
        if self.name and self.version:
            return f"Plugin {self.name} ({self.version})"
        return f"Plugin {self.name}"

    def __repr__(self) -> str:
        """详细字符串表示"""
        parts = []
        if self.name:
            parts.append(f"name={self.name}")
        if self.version:
            parts.append(f"version={self.version}")
        if self.author:
            parts.append(f"author={self.author}")
        if self.desc:
            parts.append(f"desc={self.desc}")
        return f"PluginMetadata({', '.join(parts)})"


class MetadataLoader:
    """元数据加载器
    
    负责从 metadata.yaml 或插件的 info() 方法加载元数据
    """

    @staticmethod
    def load_metadata(
        plugin_dir: Path,
        plugin_obj: Optional[Any] = None
    ) -> Optional[PluginMetadata]:
        """加载插件元数据
        
        Args:
            plugin_dir: 插件目录路径
            plugin_obj: 插件对象实例（用于调用 info() 方法）
            
        Returns:
            插件元数据，如果加载失败则返回 None
        """
        # 优先尝试从 metadata.yaml 加载
        metadata_yaml_path = plugin_dir / "metadata.yaml"
        
        if metadata_yaml_path.exists():
            try:
                with open(metadata_yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                
                return MetadataLoader._parse_yaml_metadata(data, plugin_dir)
            except Exception as e:
                logger.warning(f"加载 metadata.yaml 失败: {e}")
        
        # 回退到 info() 方法
        if plugin_obj and hasattr(plugin_obj, "info"):
            try:
                info_data = plugin_obj.info()
                return MetadataLoader._parse_info_metadata(info_data)
            except Exception as e:
                logger.warning(f"调用 info() 方法失败: {e}")
        
        return None

    @staticmethod
    def _parse_yaml_metadata(data: Dict[str, Any], plugin_dir: Path) -> PluginMetadata:
        """解析 metadata.yaml 数据
        
        Args:
            data: YAML 数据字典
            plugin_dir: 插件目录路径
            
        Returns:
            插件元数据
        """
        # 必需字段检查
        required_fields = ["name", "desc", "version", "author"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"metadata.yaml 缺少必需字段: {field}")
        
        # 处理 desc 和 description 兼容性
        if "desc" not in data and "description" in data:
            data["desc"] = data["description"]
        elif "description" not in data and "desc" in data:
            data["description"] = data["desc"]
        
        return PluginMetadata(
            name=data.get("name"),
            author=data.get("author"),
            desc=data.get("desc") or data.get("description"),
            version=data.get("version"),
            repo=data.get("repo"),
            display_name=data.get("display_name"),
            root_dir_name=plugin_dir.name,
            logo_path=str(plugin_dir / "logo.png") if (plugin_dir / "logo.png").exists() else None,
        )

    @staticmethod
    def _parse_info_metadata(info_data: Dict[str, Any]) -> PluginMetadata:
        """解析 info() 方法返回的数据
        
        Args:
            info_data: info() 方法返回的字典
            
        Returns:
            插件元数据
        """
        # 兼容性处理
        return PluginMetadata(
            name=info_data.get("name"),
            author=info_data.get("author"),
            desc=info_data.get("desc") or info_data.get("description"),
            version=info_data.get("version"),
            repo=info_data.get("repo"),
            display_name=info_data.get("display_name"),
        )

    @staticmethod
    def validate_metadata(metadata: PluginMetadata) -> List[str]:
        """验证插件元数据
        
        Args:
            metadata: 插件元数据
            
        Returns:
            错误列表，为空表示验证通过
        """
        errors = []
        
        if not metadata.name:
            errors.append("插件名称不能为空")
        
        if not metadata.author:
            errors.append("插件作者不能为空")
        
        if not metadata.desc:
            errors.append("插件描述不能为空")
        
        if not metadata.version:
            errors.append("插件版本不能为空")
        
        # 验证版本格式（简单检查）
        if metadata.version:
            if not isinstance(metadata.version, str):
                errors.append("插件版本必须是字符串")
        
        return errors

    @staticmethod
    def load_conf_schema(plugin_dir: Path) -> Optional[Dict[str, Any]]:
        """加载插件配置 Schema
        
        Args:
            plugin_dir: 插件目录路径
            
        Returns:
            配置 Schema 字典，如果不存在则返回 None
        """
        schema_path = plugin_dir / "_conf_schema.json"
        
        if schema_path.exists():
            try:
                import json
                with open(schema_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载配置 Schema 失败: {e}")
        
        return None


class MetadataRegistry:
    """元数据注册表
    
    管理所有已加载插件的元数据
    """

    def __init__(self):
        self._metadata_map: Dict[str, PluginMetadata] = {}
        """插件名称到元数据的映射"""

    def register(self, metadata: PluginMetadata) -> None:
        """注册插件元数据
        
        Args:
            metadata: 插件元数据
        """
        if not metadata.name:
            logger.warning("尝试注册没有名称的插件元数据")
            return
        
        self._metadata_map[metadata.name] = metadata
        logger.debug(f"已注册插件元数据: {metadata.name}")

    def unregister(self, plugin_name: str) -> None:
        """注销插件元数据
        
        Args:
            plugin_name: 插件名称
        """
        if plugin_name in self._metadata_map:
            del self._metadata_map[plugin_name]
            logger.debug(f"已注销插件元数据: {plugin_name}")

    def get(self, plugin_name: str) -> Optional[PluginMetadata]:
        """获取插件元数据
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件元数据，如果不存在则返回 None
        """
        return self._metadata_map.get(plugin_name)

    def get_all(self) -> List[PluginMetadata]:
        """获取所有已注册的元数据
        
        Returns:
            元数据列表
        """
        return list(self._metadata_map.values())

    def get_by_module_path(self, module_path: str) -> Optional[PluginMetadata]:
        """通过模块路径获取元数据
        
        Args:
            module_path: 模块路径
            
        Returns:
            插件元数据，如果不存在则返回 None
        """
        for metadata in self._metadata_map.values():
            if metadata.module_path == module_path:
                return metadata
        return None

    def clear(self) -> None:
        """清空所有元数据"""
        self._metadata_map.clear()
        logger.debug("已清空所有插件元数据")