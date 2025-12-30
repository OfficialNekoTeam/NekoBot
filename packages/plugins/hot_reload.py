"""插件热重载管理器

支持文件监视和智能重载
"""

import asyncio
import sys
from pathlib import Path
from typing import Set
from loguru import logger

try:
    from watchfiles import PythonFilter, awatch
    WATCHFILES_AVAILABLE = True
except ImportError:
    WATCHFILES_AVAILABLE = False
    logger.warning("未安装 watchfiles，无法实现文件监视热重载")


class HotReloadManager:
    """插件热重载管理器
    
    监视插件文件变化并自动重载变更的插件
    """

    def __init__(self, plugin_dir: Path, reserved_dir: Path, reload_callback):
        """初始化热重载管理器
        
        Args:
            plugin_dir: 用户插件目录
            reserved_dir: 保留插件目录
            reload_callback: 重载回调函数
        """
        self.plugin_dir = plugin_dir
        self.reserved_dir = reserved_dir
        self.reload_callback = reload_callback
        self._watch_task: asyncio.Task | None = None
        self._running = False
        
        # 已重载的插件（避免重复重载）
        self._reloaded_plugins: Set[str] = set()

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
        logger.info("插件热重载监视器已启动")

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
        
        logger.info("插件热重载监视器已停止")

    async def _watch_loop(self) -> None:
        """文件监视循环"""
        try:
            async for changes in awatch(
                self.plugin_dir,
                self.reserved_dir,
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
            changes: 文件变化列表
        """
        logger.debug(f"检测到文件变化: {changes}")
        
        # 获取需要重载的插件
        plugins_to_reload = await self._get_affected_plugins(changes)
        
        # 重载每个受影响的插件
        for plugin_name in plugins_to_reload:
            if plugin_name in self._reloaded_plugins:
                logger.debug(f"插件 {plugin_name} 最近已重载，跳过")
                continue
            
            logger.info(f"检测到插件 {plugin_name} 文件变化，正在重载...")
            
            try:
                await self.reload_callback(plugin_name)
                self._reloaded_plugins.add(plugin_name)
            except Exception as e:
                logger.error(f"重载插件 {plugin_name} 失败: {e}")

    async def _get_affected_plugins(self, changes) -> set:
        """获取受影响的插件
        
        Args:
            changes: 文件变化列表
            
        Returns:
            受影响的插件名称集合
        """
        affected_plugins = set()
        
        for change_type, file_path in changes:
            # 只关心 Python 文件变化
            if not file_path.suffix in (".py",):
                continue
            
            # 确定插件目录
            plugin_dir = self._find_plugin_dir(file_path)
            
            if plugin_dir:
                # 获取插件名称（目录名）
                plugin_name = plugin_dir.name
                
                # 只重载非保留插件
                if plugin_dir.parent != self.reserved_dir:
                    affected_plugins.add(plugin_name)
        
        return affected_plugins

    def _find_plugin_dir(self, file_path: Path) -> Path | None:
        """查找文件对应的插件目录
        
        Args:
            file_path: 文件路径
            
        Returns:
            插件目录路径，如果不在插件目录中则返回 None
        """
        current = file_path.resolve()
        
        # 向上查找包含 main.py 的目录
        while current != self.plugin_dir.parent and current != self.reserved_dir.parent:
            if (current / "main.py").exists():
                return current
            current = current.parent
        
        return None

    def is_running(self) -> bool:
        """检查是否正在运行
        
        Returns:
            是否正在运行
        """
        return self._running

    def clear_reloaded_history(self) -> None:
        """清空重载历史"""
        self._reloaded_plugins.clear()
        logger.debug("已清空插件重载历史")