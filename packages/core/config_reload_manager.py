"""配置热重载管理器

提供配置文件的动态加载、验证和热重载功能
"""

import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from loguru import logger


class ConfigValidationResult(Enum):
    """配置验证结果"""
    VALID = "valid"
    INVALID = "invalid"
    MISSING_FIELDS = "missing_fields"
    TYPE_MISMATCH = "type_mismatch"
    OUT_OF_RANGE = "out_of_range"


@dataclass
class ConfigSchema:
    """配置 Schema 定义"""
    name: str
    fields: Dict[str, Dict[str, Any]]
    """字段定义，每个字段包含类型、默认值、验证规则等"""
    
    # 支持的字段属性
    type: type = str
    default: Any = None
    required: bool = False
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    allowed_values: Optional[List[Any]] = None
    description: str = ""


@dataclass
class ConfigReloadEvent:
    """配置重载事件"""
    config_name: str
    old_config: Optional[Dict[str, Any]]
    new_config: Dict[str, Any]
    validation_result: ConfigValidationResult
    errors: List[str] = field(default_factory=list)


class ConfigReloadManager:
    """配置热重载管理器
    
    负责配置文件的动态加载、验证和热重载
    """
    
    def __init__(
        self,
        config_dir: Path,
        schemas: Optional[Dict[str, ConfigSchema]] = None
    ):
        """初始化配置热重载管理器
        
        Args:
            config_dir: 配置文件目录
            schemas: 配置 Schema 字典
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置缓存
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._schemas: Dict[str, ConfigSchema] = schemas or {}
        
        # 重载回调
        self._reload_callbacks: Dict[str, List[Callable[[ConfigReloadEvent], None]]] = {}
        
        # 重载历史
        self._reload_history: List[ConfigReloadEvent] = []
        self._max_history_size = 50
        
        # 锁
        self._lock = asyncio.Lock()
        
        logger.info(f"配置热重载管理器已初始化，配置目录: {self.config_dir}")
    
    def register_schema(self, schema: ConfigSchema) -> None:
        """注册配置 Schema
        
        Args:
            schema: 配置 Schema
        """
        self._schemas[schema.name] = schema
        logger.debug(f"已注册配置 Schema: {schema.name}")
    
    def register_callback(
        self,
        config_name: str,
        callback: Callable[[ConfigReloadEvent], None]
    ) -> None:
        """注册配置重载回调
        
        Args:
            config_name: 配置名称
            callback: 回调函数
        """
        if config_name not in self._reload_callbacks:
            self._reload_callbacks[config_name] = []
        self._reload_callbacks[config_name].append(callback)
        logger.debug(f"已为配置 {config_name} 注册重载回调")
    
    async def load_config(self, config_name: str) -> Dict[str, Any]:
        """加载配置文件
        
        Args:
            config_name: 配置名称（不含扩展名）
            
        Returns:
            配置字典
        """
        config_file = self._get_config_file(config_name)
        
        if not config_file.exists():
            # 配置文件不存在，使用默认值
            schema = self._schemas.get(config_name)
            if schema:
                default_config = self._get_default_config(schema)
                await self.save_config(config_name, default_config)
                return default_config
            else:
                return {}
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 验证配置
            if config_name in self._schemas:
                validation = await self._validate_config(config_name, config)
                if validation[0] != ConfigValidationResult.VALID:
                    logger.warning(
                        f"配置 {config_name} 验证失败，使用默认值: {validation[1]}"
                    )
                    schema = self._schemas[config_name]
                    config = self._get_default_config(schema)
            
            self._configs[config_name] = config
            logger.debug(f"已加载配置: {config_name}")
            return config
            
        except json.JSONDecodeError as e:
            logger.error(f"配置文件 {config_file} 格式错误: {e}")
            schema = self._schemas.get(config_name)
            if schema:
                return self._get_default_config(schema)
            return {}
        except Exception as e:
            logger.error(f"加载配置 {config_name} 失败: {e}")
            schema = self._schemas.get(config_name)
            if schema:
                return self._get_default_config(schema)
            return {}
    
    async def save_config(self, config_name: str, config: Dict[str, Any]) -> bool:
        """保存配置文件
        
        Args:
            config_name: 配置名称（不含扩展名）
            config: 配置字典
            
        Returns:
            保存是否成功
        """
        # 验证配置
        if config_name in self._schemas:
            validation = await self._validate_config(config_name, config)
            if validation[0] != ConfigValidationResult.VALID:
                logger.error(f"配置 {config_name} 验证失败: {validation[1]}")
                return False
        
        config_file = self._get_config_file(config_name)
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            self._configs[config_name] = config
            logger.debug(f"已保存配置: {config_name}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置 {config_name} 失败: {e}")
            return False
    
    async def reload_config(self, config_name: str) -> bool:
        """热重载配置
        
        Args:
            config_name: 配置名称
            
        Returns:
            重载是否成功
        """
        async with self._lock:
            logger.info(f"正在热重载配置: {config_name}")
            
            # 保存旧配置
            old_config = self._configs.get(config_name)
            
            # 加载新配置
            new_config = await self.load_config(config_name)
            
            # 验证配置
            validation = await self._validate_config(config_name, new_config)
            
            # 创建重载事件
            event = ConfigReloadEvent(
                config_name=config_name,
                old_config=old_config,
                new_config=new_config,
                validation_result=validation[0],
                errors=validation[1] if not isinstance(validation[1], str) else []
            )
            
            # 添加到历史
            self._add_reload_event(event)
            
            # 如果验证失败，回滚到旧配置
            if validation[0] != ConfigValidationResult.VALID and old_config:
                logger.warning(f"配置 {config_name} 验证失败，回滚到旧配置")
                self._configs[config_name] = old_config
                return False
            
            # 触发回调
            if config_name in self._reload_callbacks:
                for callback in self._reload_callbacks[config_name]:
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error(f"配置 {config_name} 重载回调执行失败: {e}")
            
            logger.info(f"配置 {config_name} 热重载成功")
            return True
    
    async def _validate_config(
        self,
        config_name: str,
        config: Dict[str, Any]
    ) -> tuple[ConfigValidationResult, Any]:
        """验证配置
        
        Args:
            config_name: 配置名称
            config: 配置字典
            
        Returns:
            (验证结果, 错误信息)
        """
        if config_name not in self._schemas:
            return ConfigValidationResult.VALID, ""
        
        schema = self._schemas[config_name]
        errors = []
        
        # 检查必填字段
        for field_name, field_schema in schema.fields.items():
            if field_schema.get("required", False) and field_name not in config:
                errors.append(f"缺少必填字段: {field_name}")
        
        # 检查字段类型和范围
        for field_name, field_value in config.items():
            if field_name not in schema.fields:
                continue  # 允许额外的字段
            
            field_schema = schema.fields[field_name]
            expected_type = field_schema.get("type", str)
            
            # 类型检查
            if not isinstance(field_value, expected_type):
                errors.append(
                    f"字段 {field_name} 类型错误: 期望 {expected_type.__name__}, "
                    f"实际 {type(field_value).__name__}"
                )
            
            # 范围检查
            min_value = field_schema.get("min_value")
            if min_value is not None and field_value < min_value:
                errors.append(
                    f"字段 {field_name} 值 {field_value} 小于最小值 {min_value}"
                )
            
            max_value = field_schema.get("max_value")
            if max_value is not None and field_value > max_value:
                errors.append(
                    f"字段 {field_name} 值 {field_value} 大于最大值 {max_value}"
                )
            
            # 允许值检查
            allowed_values = field_schema.get("allowed_values")
            if allowed_values is not None and field_value not in allowed_values:
                errors.append(
                    f"字段 {field_name} 值 {field_value} 不在允许值列表中: {allowed_values}"
                )
        
        if errors:
            return ConfigValidationResult.INVALID, errors
        
        return ConfigValidationResult.VALID, ""
    
    def _get_default_config(self, schema: ConfigSchema) -> Dict[str, Any]:
        """获取默认配置
        
        Args:
            schema: 配置 Schema
            
        Returns:
            默认配置字典
        """
        config = {}
        for field_name, field_schema in schema.fields.items():
            if "default" in field_schema:
                config[field_name] = field_schema["default"]
            elif field_schema.get("required", False):
                config[field_name] = None
        return config
    
    def _get_config_file(self, config_name: str) -> Path:
        """获取配置文件路径
        
        Args:
            config_name: 配置名称
            
        Returns:
            配置文件路径
        """
        return self.config_dir / f"{config_name}.json"
    
    def _add_reload_event(self, event: ConfigReloadEvent) -> None:
        """添加重载事件到历史
        
        Args:
            event: 重载事件
        """
        self._reload_history.append(event)
        
        # 限制历史记录大小
        if len(self._reload_history) > self._max_history_size:
            self._reload_history.pop(0)
    
    def get_config(self, config_name: str) -> Optional[Dict[str, Any]]:
        """获取配置
        
        Args:
            config_name: 配置名称
            
        Returns:
            配置字典，如果不存在则返回 None
        """
        return self._configs.get(config_name)
    
    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """获取所有配置
        
        Returns:
            所有配置字典
        """
        return dict(self._configs)
    
    def get_reload_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取重载历史
        
        Args:
            limit: 返回的最大记录数
            
        Returns:
            重载历史列表
        """
        events = self._reload_history[-limit:] if limit > 0 else self._reload_history
        
        return [
            {
                "config_name": event.config_name,
                "validation_result": event.validation_result.value,
                "has_changes": event.old_config != event.new_config,
                "errors": event.errors
            }
            for event in events
        ]
    
    def clear_reload_history(self) -> None:
        """清空重载历史"""
        self._reload_history.clear()
        logger.debug("已清空配置重载历史")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        total_reloads = len(self._reload_history)
        successful_reloads = sum(
            1 for e in self._reload_history
            if e.validation_result == ConfigValidationResult.VALID
        )
        failed_reloads = total_reloads - successful_reloads
        
        return {
            "total_configs": len(self._configs),
            "total_schemas": len(self._schemas),
            "total_callbacks": sum(len(cb) for cb in self._reload_callbacks.values()),
            "total_reloads": total_reloads,
            "successful_reloads": successful_reloads,
            "failed_reloads": failed_reloads,
            "success_rate": successful_reloads / total_reloads if total_reloads > 0 else 0
        }


# 全局配置热重载管理器实例
config_reload_manager = ConfigReloadManager(
    config_dir=Path(__file__).parent.parent.parent / "data" / "config"
)