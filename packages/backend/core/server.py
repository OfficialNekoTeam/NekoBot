"""NekoBot 主服务器

该服务器负责启动和管理多个平台适配器，
同时支持通过插件系统处理自定义命令。
"""

import asyncio
import os
import re
from typing import Dict, Any
from loguru import logger

from .config import load_config
from .plugin_manager import PluginManager
from ..platform import PlatformManager
from .pipeline import (
    PipelineScheduler,
    PipelineContext,
    WhitelistCheckStage,
    ContentSafetyCheckStage,
    RateLimitStage,
    SessionStatusCheckStage,
    WakingCheckStage,
    ProcessStage,
    ResultDecorateStage,
    RespondStage,
)

# 加载全局配置
CONFIG = load_config()

# 初始化插件管理器
plugin_manager = PluginManager()

# 初始化平台管理器
platform_manager = PlatformManager()

# 创建事件队列
event_queue = asyncio.Queue()

# 版本信息
NEKOBOT_VERSION = "1.0.0"
# 获取项目根目录（从 packages/backend/core/server.py 向上三级到项目根目录）
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
)
WEBUI_VERSION_FILE = os.path.join(PROJECT_ROOT, "data", "dist", "version")


def get_webui_version() -> str:
    """获取 WebUI 版本

    Returns:
        WebUI 版本字符串
    """
    try:
        if os.path.exists(WEBUI_VERSION_FILE):
            with open(WEBUI_VERSION_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception as e:
        logger.warning(f"读取 WebUI 版本失败: {e}")
    return "未知"


def get_full_version() -> str:
    """获取完整版本信息

    Returns:
        完整版本信息字符串
    """
    webui_version = get_webui_version()
    return f"NekoBot {NEKOBOT_VERSION} (WebUI {webui_version})"


async def start_server() -> None:
    """启动 NekoBot 服务器"""
    logger.info("正在初始化 NekoBot 服务器...")

    # 1. 设置平台管理器的事件队列
    platform_manager.set_event_queue(event_queue)

    # 2. 加载平台适配器（在插件之前加载，确保插件可以使用平台功能）
    platforms_config = CONFIG.get("platforms", {})
    await platform_manager.load_platforms(platforms_config)
    logger.info(f"已加载 {len(platform_manager.platforms)} 个平台适配器")

    # 3. 启动所有平台（在插件加载之前启动，确保平台已准备好接收事件）
    await platform_manager.start_all()
    logger.info("所有平台适配器已启动")

    # 4. 设置平台服务器引用，供插件使用
    plugin_manager.set_platform_server(platform_manager)
    logger.info("已设置平台服务器引用")

    # 5. 加载插件（在平台启动后加载，确保插件可以使用平台功能）
    await plugin_manager.load_plugins()
    logger.info(f"已加载 {len(plugin_manager.plugins)} 个插件")

    # 6. 自动启用所有插件
    for plugin_name in plugin_manager.plugins:
        await plugin_manager.enable_plugin(plugin_name)
    logger.info("所有插件已启用")

    # 7. 初始化 Pipeline 调度器
    pipeline_scheduler = PipelineScheduler(
        [
            WhitelistCheckStage(),
            ContentSafetyCheckStage(),
            RateLimitStage(),
            SessionStatusCheckStage(),
            WakingCheckStage(),
            ProcessStage(),
            ResultDecorateStage(),
            RespondStage(),
        ]
    )
    logger.info("Pipeline 调度器已初始化")

    # 7. 启动事件处理循环
    event_handler_task = asyncio.create_task(handle_events(pipeline_scheduler))
    logger.info("事件处理循环已启动")

    logger.info("NekoBot 服务器已启动")

    # 不阻塞主线程，返回让 Quart 应用启动
    return


async def handle_events(pipeline_scheduler: PipelineScheduler) -> None:
    """处理平台事件

    Args:
        pipeline_scheduler: Pipeline 调度器
    """
    # 创建 Pipeline 上下文
    ctx = PipelineContext(
        config=CONFIG,
        platform_manager=platform_manager,
        plugin_manager=plugin_manager,
        llm_manager=None,  # 暂时为 None，后续可以添加 LLM 管理器
        event_queue=event_queue,
    )

    while True:
        try:
            event = await event_queue.get()
            await pipeline_scheduler.execute(event, ctx)
        except Exception as e:
            logger.error(f"处理事件失败: {e}")


def format_message(event: Dict[str, Any], simple: bool = True) -> str:
    """格式化消息内容，将 CQ 码转换为简短描述

    Args:
        event: 事件数据
        simple: 是否简化 CQ 码 (True 用于日志显示, False 用于命令解析)
    """
    # 非简化模式下，优先返回 raw_message
    if not simple:
        raw = event.get("raw_message")
        if isinstance(raw, str) and raw:
            return raw

    msg = event.get("message")

    # 优先解析 message 数组 (结构化数据)
    if isinstance(msg, list):
        parts = []
        for seg in msg:
            if not isinstance(seg, dict):
                continue
            t = seg.get("type")
            data = seg.get("data", {}) if isinstance(seg.get("data"), dict) else {}

            if t == "text":
                parts.append(data.get("text", ""))
            elif t == "at":
                parts.append(f"[@{data.get('qq', 'User')}]")
            elif t == "image":
                parts.append("[图片]")
            elif t == "face":
                parts.append("[表情]")
            elif t == "record":
                parts.append("[语音]")
            elif t == "video":
                parts.append("[视频]")
            elif t == "share":
                parts.append(f"[分享: {data.get('title', '链接')}]")
            elif t == "xml":
                parts.append("[XML卡片]")
            elif t == "json":
                parts.append("[JSON卡片]")
            elif t == "reply":
                parts.append(f"[回复: {data.get('id', 'Unknown')}]")
            else:
                parts.append(f"[{t}]")
        return "".join(parts)

    # 如果没有 message 数组，回退到 raw_message
    raw = event.get("raw_message")
    if isinstance(raw, str):
        if simple:
            # 简化 raw_message 中的 CQ 码
            raw = re.sub(r"\[CQ:image,[^\]]+\]", "[图片]", raw)
            raw = re.sub(r"\[CQ:face,[^\]]+\]", "[表情]", raw)
            raw = re.sub(r"\[CQ:record,[^\]]+\]", "[语音]", raw)
            raw = re.sub(r"\[CQ:video,[^\]]+\]", "[视频]", raw)
            raw = re.sub(r"\[CQ:at,qq=(\d+)[^\]]*\]", r"[@\1]", raw)
            # 通用匹配其他 CQ 码
            raw = re.sub(r"\[CQ:([^,]+),[^\]]+\]", r"[\1]", raw)
        return raw

    return ""


if __name__ == "__main__":
    asyncio.run(start_server())
