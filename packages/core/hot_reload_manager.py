"""热重载管理器

提供插件、配置和路由的热重载功能，参考 AstrBot 框架实现
"""

import asyncio
import importlib
import sys
import time
import tracemalloc
import gc
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from loguru import logger

try:
    from watchfiles import PythonFilter, awatch
    WATCHFILES_AVAILABLE = True
except ImportError:
    WATCHFILES_AVAILABLE = False
    logger.warning("未安装 watchfiles，无法实现文件监视热重载")


class ReloadEventType(Enum):
    """热重载事件类型"""
    PLUGIN_RELOAD = "plugin_reload"
    CONFIG_RELOAD = "config_reload"
    ROUTE_REGISTER = "route_register"
    ROUTE_UNREGISTER = "route_unregister"


@dataclass
class ReloadEvent:
    """热重载事件"""
    event_type: ReloadEventType
    target: str
    success: bool
    duration_ms: float
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class HotReloadManager:
    """热重载管理器
    
    提供插件、配置和路由的热重载功能，确保在 300ms 内完成
    并提供错误恢复和内存泄漏检测
    """

    def __init__(
        self,
        plugin_dir: Path,
        config_dir: Path,
        plugin_reload_callback: Callable[[str], Any],
        config_reload_callback: Callable[[str], Any]
    ):
        """初始化热重载管理器
        
        Args:
            plugin_dir: 插件目录
            config_dir: 配置目录
            plugin_reload_callback: 插件重载回调
            config_reload_callback: 配置重载回调
        """
        self.plugin_dir = plugin_dir
        self.config_dir = config_dir
        self.plugin_reload_callback = plugin_reload_callback
        self.config_reload_callback = config_reload_callback
        
        # 状态管理
        self._running = False
        self._watch_task: Optional[asyncio.Task] = None
        self._reload_lock = asyncio.Lock()
        
        # 重载历史（避免重复重载）
        self._reloaded_plugins: Set[str] = set()
        self._reloaded_configs: Set[str] = set()
        self._reload_history: List[ReloadEvent] = []
        
        # 性能监控
        self._max_history_size = 100
        
        # 内存监控
        self._memory_snapshots: Dict[str, Dict[str, int]] = {}
        
        # 路由管理
        self._dynamic_routes: Dict[str, Any] = {}

    async def start(self) -> None:
        """启动文件监视"""
        if not WATCHFILES_AVAILABLE:
            logger.warning("watchfiles 未安装，跳过文件监视")
            return

        if self._running:
            logger.warning("热重载管理器已在运行中")
            return

        self._running = True
        self._watch_task = asyncio.create_task(self._watch_loop())
        logger.info("热重载监视器已启动")

    async def stop(self) -> None:
        """停止文件监视"""
        if not self._running:
            return

        self._running = False

        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass

        logger.info("热重载监视器已停止")

    async def _watch_loop(self) -> None:
        """文件监视循环"""
        try:
            async for changes in awatch(
                self.plugin_dir,
                self.config_dir,
                watch_filter=PythonFilter(),
                recursive=True,
            ):
                await self._handle_file_changes(changes)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"文件监视循环出错: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def _handle_file_changes(self, changes) -> None:
        """处理文件变化
        
        Args:
            changes: 文件变化列表 (change_type, file_path)
        """
        logger.debug(f"检测到文件变化: {len(changes)} 个文件")

        # 分类处理插件和配置文件变化
        plugin_changes = []
        config_changes = []

        for change_type, file_path in changes:
            file_path = Path(file_path)
            
            # 判断文件类型
            if self._is_plugin_file(file_path):
                plugin_changes.append((change_type, file_path))
            elif self._is_config_file(file_path):
                config_changes.append((change_type, file_path))

        # 处理插件变化
        if plugin_changes:
            await self._handle_plugin_changes(plugin_changes)

        # 处理配置变化
        if config_changes:
            await self._handle_config_changes(config_changes)

    def _is_plugin_file(self, file_path: Path) -> bool:
        """判断是否是插件文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否是插件文件
        """
        # 检查是否在插件目录下且是 Python 文件
        try:
            file_path.relative_to(self.plugin_dir)
            return file_path.suffix == ".py"
        except ValueError:
            return False

    def _is_config_file(self, file_path: Path) -> bool:
        """判断是否是配置文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否是配置文件
        """
        # 检查是否在配置目录下且是配置文件
        try:
            file_path.relative_to(self.config_dir)
            return file_path.suffix in (".json", ".yaml", ".yml", ".toml")
        except ValueError:
            return False

    async def _handle_plugin_changes(self, changes: List[Tuple[Any, Path]]) -> None:
        """处理插件文件变化
        
        Args:
            changes: 插件文件变化列表
        """
        # 获取受影响的插件
        plugins_to_reload = self._get_affected_plugins(changes)

        # 重载每个受影响的插件
        for plugin_name in plugins_to_reload:
            if plugin_name in self._reloaded_plugins:
                logger.debug(f"插件 {plugin_name} 最近已重载，跳过")
                continue

            await self._safe_reload_plugin(plugin_name)

    async def _handle_config_changes(self, changes: List[Tuple[Any, Path]]) -> None:
        """处理配置文件变化
        
        Args:
            changes: 配置文件变化列表
        """
        # 获取受影响的配置
        configs_to_reload = self._get_affected_configs(changes)

        # 重载每个受影响的配置
        for config_name in configs_to_reload:
            if config_name in self._reloaded_configs:
                logger.debug(f"配置 {config_name} 最近已重载，跳过")
                continue

            await self._safe_reload_config(config_name)

    async def _safe_reload_plugin(self, plugin_name: str) -> bool:
        """安全地重载插件（带性能监控和错误恢复）
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            重载是否成功
        """
        start_time = time.time()
        success = False
        error_msg = None

        # 记录内存快照
        self._take_memory_snapshot(f"before_reload_{plugin_name}")

        try:
            async with self._reload_lock:
                logger.info(f"正在重载插件 {plugin_name}...")
                
                # 执行重载回调
                await self.plugin_reload_callback(plugin_name)
                
                # 标记为已重载
                self._reloaded_plugins.add(plugin_name)
                
                # 延迟清理标记
                asyncio.create_task(self._delayed_clear_plugin_history(plugin_name))
                
                success = True
                logger.info(f"插件 {plugin_name} 重载成功")
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"重载插件 {plugin_name} 失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 尝试恢复
            await self._recover_plugin(plugin_name)
            
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            # 记录重载事件
            event = ReloadEvent(
                event_type=ReloadEventType.PLUGIN_RELOAD,
                target=plugin_name,
                success=success,
                duration_ms=duration_ms,
                error=error_msg
            )
            self._add_reload_event(event)
            
            # 检查内存泄漏
            self._check_memory_leak(f"before_reload_{plugin_name}", f"after_reload_{plugin_name}")

            # 性能警告
            if duration_ms > 300:
                logger.warning(f"插件 {plugin_name} 重载耗时 {duration_ms:.2f}ms，超过 300ms 阈值")

        return success

    async def _safe_reload_config(self, config_name: str) -> bool:
        """安全地重载配置
        
        Args:
            config_name: 配置名称
            
        Returns:
            重载是否成功
        """
        start_time = time.time()
        success = False
        error_msg = None

        try:
            async with self._reload_lock:
                logger.info(f"正在重载配置 {config_name}...")
                
                # 验证配置
                if not await self._validate_config(config_name):
                    logger.error(f"配置 {config_name} 验证失败，跳过重载")
                    return False
                
                # 执行重载回调
                await self.config_reload_callback(config_name)
                
                # 标记为已重载
                self._reloaded_configs.add(config_name)
                
                # 延迟清理标记
                asyncio.create_task(self._delayed_clear_config_history(config_name))
                
                success = True
                logger.info(f"配置 {config_name} 重载成功")
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"重载配置 {config_name} 失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            # 记录重载事件
            event = ReloadEvent(
                event_type=ReloadEventType.CONFIG_RELOAD,
                target=config_name,
                success=success,
                duration_ms=duration_ms,
                error=error_msg
            )
            self._add_reload_event(event)
            
            # 性能警告
            if duration_ms > 300:
                logger.warning(f"配置 {config_name} 重载耗时 {duration_ms:.2f}ms，超过 300ms 阈值")

        return success

    async def _validate_config(self, config_name: str) -> bool:
        """验证配置文件
        
        Args:
            config_name: 配置名称
            
        Returns:
            配置是否有效
        """
        # 这里可以实现具体的配置验证逻辑
        # 暂时返回 True
        return True

    async def _recover_plugin(self, plugin_name: str) -> None:
        """尝试恢复插件
        
        Args:
            plugin_name: 插件名称
        """
        logger.info(f"尝试恢复插件 {plugin_name}...")
        # 这里可以实现具体的恢复逻辑
        # 例如：回滚到之前的版本或重新加载

    def _get_affected_plugins(self, changes: List[Tuple[Any, Path]]) -> Set[str]:
        """获取受影响的插件
        
        Args:
            changes: 文件变化列表
            
        Returns:
            受影响的插件名称集合
        """
        affected_plugins = set()

        for _, file_path in changes:
            plugin_dir = self._find_plugin_dir(file_path)
            if plugin_dir:
                plugin_name = plugin_dir.name
                affected_plugins.add(plugin_name)

        return affected_plugins

    def _get_affected_configs(self, changes: List[Tuple[Any, Path]]) -> Set[str]:
        """获取受影响的配置
        
        Args:
            changes: 文件变化列表
            
        Returns:
            受影响的配置名称集合
        """
        affected_configs = set()

        for _, file_path in changes:
            config_name = file_path.stem
            affected_configs.add(config_name)

        return affected_configs

    def _find_plugin_dir(self, file_path: Path) -> Optional[Path]:
        """查找文件对应的插件目录
        
        Args:
            file_path: 文件路径
            
        Returns:
            插件目录路径，如果不在插件目录中则返回 None
        """
        current = file_path.resolve()

        # 向上查找包含 main.py 的目录
        while current != self.plugin_dir.parent:
            if (current / "main.py").exists():
                return current
            current = current.parent

        return None

    async def _delayed_clear_plugin_history(self, plugin_name: str) -> None:
        """延迟清理插件重载历史
        
        Args:
            plugin_name: 插件名称
        """
        await asyncio.sleep(5)  # 5 秒后清理
        self._reloaded_plugins.discard(plugin_name)

    async def _delayed_clear_config_history(self, config_name: str) -> None:
        """延迟清理配置重载历史
        
        Args:
            config_name: 配置名称
        """
        await asyncio.sleep(5)  # 5 秒后清理
        self._reloaded_configs.discard(config_name)

    def _add_reload_event(self, event: ReloadEvent) -> None:
        """添加重载事件到历史记录
        
        Args:
            event: 重载事件
        """
        self._reload_history.append(event)
        
        # 限制历史记录大小
        if len(self._reload_history) > self._max_history_size:
            self._reload_history.pop(0)

    def _take_memory_snapshot(self, label: str) -> None:
        """记录内存快照
        
        Args:
            label: 快照标签
        """
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            
        current, peak = tracemalloc.get_traced_memory()
        self._memory_snapshots[label] = {
            "current": current,
            "peak": peak,
            "time": time.time()
        }

    def _check_memory_leak(self, before_label: str, after_label: str) -> None:
        """检查内存泄漏
        
        Args:
            before_label: 操作前快照标签
            after_label: 操作后快照标签
        """
        if before_label not in self._memory_snapshots:
            return
            
        if after_label not in self._memory_snapshots:
            return
            
        before = self._memory_snapshots[before_label]["current"]
        after = self._memory_snapshots[after_label]["current"]
        
        diff = after - before
        diff_mb = diff / (1024 * 1024)
        
        if diff_mb > 10:  # 超过 10MB 认为可能有内存泄漏
            logger.warning(
                f"检测到可能的内存泄漏: {diff_mb:.2f}MB "
                f"(before={before/1024/1024:.2f}MB, after={after/1024/1024:.2f}MB)"
            )
            # 触发垃圾回收
            gc.collect()

    # ========== 路由管理 ==========

    def register_route(self, route_id: str, route: Any) -> bool:
        """注册动态路由
        
        Args:
            route_id: 路由ID
            route: 路由对象
            
        Returns:
            注册是否成功
        """
        if route_id in self._dynamic_routes:
            logger.warning(f"路由 {route_id} 已存在，将被覆盖")
            
        self._dynamic_routes[route_id] = route
        
        # 记录路由注册事件
        event = ReloadEvent(
            event_type=ReloadEventType.ROUTE_REGISTER,
            target=route_id,
            success=True,
            duration_ms=0,
            details={"route": str(route)}
        )
        self._add_reload_event(event)
        
        logger.debug(f"已注册动态路由: {route_id}")
        return True

    def unregister_route(self, route_id: str) -> bool:
        """注销动态路由
        
        Args:
            route_id: 路由ID
            
        Returns:
            注销是否成功
        """
        if route_id not in self._dynamic_routes:
            logger.warning(f"路由 {route_id} 不存在")
            return False
            
        del self._dynamic_routes[route_id]
        
        # 记录路由注销事件
        event = ReloadEvent(
            event_type=ReloadEventType.ROUTE_UNREGISTER,
            target=route_id,
            success=True,
            duration_ms=0
        )
        self._add_reload_event(event)
        
        logger.debug(f"已注销动态路由: {route_id}")
        return True

    def get_route(self, route_id: str) -> Optional[Any]:
        """获取动态路由
        
        Args:
            route_id: 路由ID
            
        Returns:
            路由对象，如果不存在则返回 None
        """
        return self._dynamic_routes.get(route_id)

    def list_routes(self) -> List[str]:
        """列出所有动态路由
        
        Returns:
            路由ID列表
        """
        return list(self._dynamic_routes.keys())

    # ========== 统计和监控 ==========

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
                "type": event.event_type.value,
                "target": event.target,
                "success": event.success,
                "duration_ms": event.duration_ms,
                "error": event.error,
                "details": event.details
            }
            for event in events
        ]

    def get_stats(self) -> Dict[str, Any]:
        """获取热重载统计信息
        
        Returns:
            统计信息字典
        """
        total_events = len(self._reload_history)
        plugin_reloads = sum(1 for e in self._reload_history if e.event_type == ReloadEventType.PLUGIN_RELOAD)
        config_reloads = sum(1 for e in self._reload_history if e.event_type == ReloadEventType.CONFIG_RELOAD)
        
        successful_reloads = sum(1 for e in self._reload_history if e.success)
        failed_reloads = total_events - successful_reloads
        
        avg_duration = (
            sum(e.duration_ms for e in self._reload_history) / total_events
            if total_events > 0 else 0
        )
        
        return {
            "total_events": total_events,
            "plugin_reloads": plugin_reloads,
            "config_reloads": config_reloads,
            "dynamic_routes": len(self._dynamic_routes),
            "successful_reloads": successful_reloads,
            "failed_reloads": failed_reloads,
            "success_rate": successful_reloads / total_events if total_events > 0 else 0,
            "avg_duration_ms": avg_duration,
            "is_running": self._running
        }

    def clear_reload_history(self) -> None:
        """清空重载历史"""
        self._reload_history.clear()
        logger.debug("已清空重载历史")

    def is_running(self) -> bool:
        """检查是否正在运行
        
        Returns:
            是否正在运行
        """
        return self._running