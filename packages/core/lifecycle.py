"""核心生命周期管理

管理 NekoBot 的启动、停止、重启等生命周期操作
"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Callable
from loguru import logger

from .config import load_config
from .event_bus import EventBus, event_bus
from .plugin_manager import PluginManager
from .platform.manager import PlatformManager
from .pipeline import PipelineScheduler, PipelineContext
from .server import get_full_version, NEKOBOT_VERSION


class NekoBotLifecycle:
    """NekoBot 核心生命周期管理类
    
    负责管理 NekoBot 的启动、停止、重启等操作，
    以及初始化各个组件（PlatformManager、PluginManager、PipelineScheduler 等）
    
    工作流程:
    1. 初始化所有组件
    2. 启动事件总线
    3. 启动平台适配器
    4. 加载插件
    5. 启动流水线调度器
    6. 执行启动完成事件钩子
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        plugin_manager: Optional[PluginManager] = None,
        platform_manager: Optional[PlatformManager] = None,
        event_bus_instance: Optional[EventBus] = None,
    ):
        """初始化生命周期管理器
        
        Args:
            config: 配置字典
            plugin_manager: 插件管理器
            platform_manager: 平台管理器
            event_bus_instance: 事件总线实例
        """
        # 加载配置
        self.config = config or load_config()
        
        # 初始化组件
        self.plugin_manager = plugin_manager
        self.platform_manager = platform_manager
        self.event_bus = event_bus_instance or event_bus
        
        # 流水线调度器（稍后初始化）
        self.pipeline_scheduler: Optional[PipelineScheduler] = None
        
        # 记录启动时间
        self.start_time: Optional[float] = None
        
        # 当前运行任务
        self.running_tasks: List[asyncio.Task] = []
        
        # 启动完成事件钩子
        self._startup_hooks: List[Callable] = []
        
        # 关闭事件钩子
        self._shutdown_hooks: List[Callable] = []
        
        # 是否正在运行
        self._running = False

    def add_startup_hook(self, hook: Callable):
        """添加启动完成事件钩子
        
        Args:
            hook: 钩子函数
        """
        self._startup_hooks.append(hook)
        logger.debug(f"已添加启动钩子: {hook.__name__}")

    def add_shutdown_hook(self, hook: Callable):
        """添加关闭事件钩子
        
        Args:
            hook: 钩子函数
        """
        self._shutdown_hooks.append(hook)
        logger.debug(f"已添加关闭钩子: {hook.__name__}")

    async def initialize(self) -> None:
        """初始化 NekoBot 核心组件
        
        负责初始化各个组件，包括：
        - 事件总线
        - 平台管理器
        - 插件管理器
        - 流水线调度器
        """
        logger.info("正在初始化 NekoBot 核心组件...")
        logger.info(f"NekoBot {NEKOBOT_VERSION} - {get_full_version()}")

        # 1. 启动事件总线
        await self.event_bus.start()
        logger.info("事件总线已启动")

        # 2. 设置平台管理器的事件队列
        if self.platform_manager:
            self.platform_manager.set_event_queue(self.event_bus.event_queue)
            logger.info("已设置平台管理器的事件队列")

        # 3. 加载平台适配器
        if self.platform_manager:
            platforms_config = self.config.get("platforms", {})
            await self.platform_manager.load_platforms(platforms_config)
            logger.info(f"已加载 {len(self.platform_manager.platforms)} 个平台适配器")

        # 4. 启动所有平台
        if self.platform_manager:
            await self.platform_manager.start_all()
            logger.info("所有平台适配器已启动")

        # 5. 设置平台服务器引用供插件使用
        if self.plugin_manager and self.platform_manager:
            self.plugin_manager.set_platform_server(self.platform_manager)
            logger.info("已设置平台服务器引用")

        # 6. 加载插件
        if self.plugin_manager:
            await self.plugin_manager.load_plugins()
            logger.info(f"已加载 {len(self.plugin_manager.plugins)} 个插件")

        # 7. 自动启用所有插件
        if self.plugin_manager:
            for plugin_name in self.plugin_manager.plugins:
                await self.plugin_manager.enable_plugin(plugin_name)
            logger.info("所有插件已启用")

        # 8. 初始化 Pipeline 调度器
        await self._initialize_pipeline()

        # 9. 记录启动时间
        self.start_time = time.time()
        
        logger.info("NekoBot 核心组件初始化完成")

    async def _initialize_pipeline(self) -> None:
        """初始化 Pipeline 调度器"""
        from .pipeline import (
            WhitelistCheckStage,
            ContentSafetyCheckStage,
            RateLimitStage,
            SessionStatusCheckStage,
            WakingCheckStage,
            ProcessStage,
            ResultDecorateStage,
            RespondStage,
        )

        # 创建 Pipeline 上下文
        ctx = PipelineContext(
            config=self.config,
            platform_manager=self.platform_manager,
            plugin_manager=self.plugin_manager,
            llm_manager=None,
            event_queue=self.event_bus.event_queue,
        )

        # 创建调度器
        self.pipeline_scheduler = PipelineScheduler(
            stages=[
                WhitelistCheckStage(),
                ContentSafetyCheckStage(),
                RateLimitStage(),
                SessionStatusCheckStage(),
                WakingCheckStage(),
                ProcessStage(),
                ResultDecorateStage(),
                RespondStage(),
            ],
            context=ctx,
        )
        
        logger.info("Pipeline 调度器已初始化")

    async def start(self) -> None:
        """启动 NekoBot 服务器
        
        开始事件处理循环并执行启动完成事件钩子
        """
        if self._running:
            logger.warning("NekoBot 已在运行中")
            return

        self._running = True
        logger.info("正在启动 NekoBot 服务器...")

        # 1. 初始化核心组件
        await self.initialize()

        # 2. 启动事件处理循环
        event_loop_task = asyncio.create_task(self._event_loop())
        self.running_tasks.append(event_loop_task)
        logger.info("事件处理循环已启动")

        # 3. 执行启动完成事件钩子
        await self._execute_startup_hooks()

        # 4. 打印完成信息
        logger.info("NekoBot 服务器已启动")
        if self.start_time:
            logger.info(f"启动耗时: {time.time() - self.start_time:.2f}秒")

    async def _event_loop(self) -> None:
        """事件处理循环"""
        while self._running:
            try:
                # 从事件队列获取事件
                event_data = await self.event_bus.event_queue.get()
                
                # 使用流水线调度器处理事件
                if self.pipeline_scheduler:
                    await self.pipeline_scheduler.execute(event_data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"事件处理循环出错: {e}")
                import traceback
                logger.error(traceback.format_exc())

    async def stop(self) -> None:
        """停止 NekoBot 服务器
        
        停止所有正在运行的任务并终止各个管理器
        """
        if not self._running:
            logger.warning("NekoBot 未在运行中")
            return

        self._running = False
        logger.info("正在停止 NekoBot 服务器...")

        # 1. 取消所有正在运行的任务
        for task in self.running_tasks:
            if not task.done():
                task.cancel()
        
        # 等待任务结束
        for task in self.running_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"任务 {task.get_name()} 停止时出错: {e}")

        self.running_tasks.clear()

        # 2. 停止插件
        if self.plugin_manager:
            try:
                await self.plugin_manager.unload_all()
                logger.info("所有插件已卸载")
            except Exception as e:
                logger.error(f"停止插件时出错: {e}")

        # 3. 停止平台适配器
        if self.platform_manager:
            try:
                await self.platform_manager.stop_all()
                logger.info("所有平台适配器已停止")
            except Exception as e:
                logger.error(f"停止平台适配器时出错: {e}")

        # 4. 停止事件总线
        try:
            await self.event_bus.stop()
            logger.info("事件总线已停止")
        except Exception as e:
            logger.error(f"停止事件总线时出错: {e}")

        # 5. 执行关闭事件钩子
        await self._execute_shutdown_hooks()

        logger.info("NekoBot 服务器已停止")

    async def restart(self) -> None:
        """重启 NekoBot 服务器
        
        终止各个管理器并重新启动
        """
        logger.info("正在重启 NekoBot 服务器...")

        # 1. 停止当前实例
        await self.stop()

        # 2. 等待一小段时间
        await asyncio.sleep(1)

        # 3. 重新启动
        await self.start()

        logger.info("NekoBot 服务器已重启")

    async def _execute_startup_hooks(self) -> None:
        """执行启动完成事件钩子"""
        for hook in self._startup_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()
                logger.debug(f"执行启动钩子: {hook.__name__}")
            except Exception as e:
                logger.error(f"启动钩子 {hook.__name__} 执行失败: {e}")
                import traceback
                logger.error(traceback.format_exc())

    async def _execute_shutdown_hooks(self) -> None:
        """执行关闭事件钩子"""
        for hook in self._shutdown_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()
                logger.debug(f"执行关闭钩子: {hook.__name__}")
            except Exception as e:
                logger.error(f"关闭钩子 {hook.__name__} 执行失败: {e}")
                import traceback
                logger.error(traceback.format_exc())

    def is_running(self) -> bool:
        """检查 NekoBot 是否正在运行
        
        Returns:
            是否正在运行
        """
        return self._running

    def get_uptime(self) -> float:
        """获取运行时间（秒）
        
        Returns:
            运行时间（秒）
        """
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time


# 创建全局生命周期实例
lifecycle: Optional[NekoBotLifecycle] = None


async def get_lifecycle() -> NekoBotLifecycle:
    """获取或创建全局生命周期实例
    
    Returns:
        生命周期实例
    """
    global lifecycle
    if lifecycle is None:
        lifecycle = NekoBotLifecycle()
    return lifecycle