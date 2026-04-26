from __future__ import annotations

import asyncio
import os
import signal
import sys

from loguru import logger

from packages.bootstrap import BootstrappedRuntime, bootstrap_runtime, load_app_config


def _configure_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
            "<level>[{level}]</level> {message}"
        ),
        level="INFO",
        colorize=True,
    )
    log_dir = os.environ.get("NEKOBOT_LOG_DIR", "data/logs")
    logger.add(
        f"{log_dir}/nekobot_{{time:YYYY-MM-DD}}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} [{level}] {message}",
        level="DEBUG",
        rotation="00:00",
        retention="14 days",
        encoding="utf-8",
    )


async def async_main(
    config_path: str | None = None,
    *,
    run_forever: bool = True,
    enable_webui: bool | None = None,
    host: str | None = None,
    port: int | None = None,
) -> BootstrappedRuntime:
    config = load_app_config(config_path)
    runtime = await bootstrap_runtime(config)

    # 优先级：CLI/env > 配置文件 framework_config.enable_webui > 默认值 True
    fw_cfg = runtime.configuration.framework_config
    final_host = host or fw_cfg.get("web_host") or "0.0.0.0"
    final_port = port or fw_cfg.get("web_port") or 6285
    final_enable_webui = enable_webui if enable_webui is not None else bool(fw_cfg.get("enable_webui", True))

    config_path = config_path or "data/config.json"

    # SIGUSR1 → 重载配置 + Skills（不重启平台）
    def _schedule_reload() -> None:
        asyncio.create_task(runtime.reload_config(config_path))

    try:
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGUSR1, _schedule_reload)
        logger.info("Signal handler registered: SIGUSR1 → config + skills reload")
    except (NotImplementedError, AttributeError):
        logger.debug("SIGUSR1 not supported on this platform, skipping")

    # 监听配置文件变化（可选，watchfiles 已安装时生效）
    await runtime.watch_config(config_path)

    web_task: asyncio.Task[None] | None = None
    if final_enable_webui:
        from packages.routers import create_app
        web_app = create_app(runtime.framework)
        logger.info(f"启动 WebUI Dashboard 端点: http://{final_host}:{final_port}")
        web_task = asyncio.create_task(web_app.run_task(host=final_host, port=final_port))
    else:
        logger.info("WebUI 已禁用，跳过路由注册与端口监听。")

    if run_forever and (runtime.running_platforms or final_enable_webui):
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        # web_task（Hypercorn）退出时也触发 stop（不管谁先关）
        if web_task is not None:
            def _on_web_done(task: asyncio.Task[None]) -> None:
                if not task.cancelled() and (exc := task.exception()) is not None:
                    logger.error("WebUI server stopped unexpectedly: {}", exc)
                stop_event.set()
            web_task.add_done_callback(_on_web_done)

        # 覆盖 Hypercorn 可能装的 SIGINT/SIGTERM handler
        for _sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(_sig, stop_event.set)
            except (NotImplementedError, AttributeError):
                pass

        try:
            await stop_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("收到退出信号，正在关闭...")
            if web_task is not None and not web_task.done():
                web_task.cancel()
                try:
                    await asyncio.wait_for(web_task, timeout=5.0)
                except Exception:
                    pass
            await runtime.stop()

    return runtime


def _resolve_webui_flag(cli_value: bool | None) -> bool | None:
    """解析 WebUI 开关：CLI 参数 > 环境变量 NEKOBOT_WEBUI。
    两者均未指定时返回 None，由调用方回退到配置文件值。
    """
    if cli_value is not None:
        return cli_value
    env = os.environ.get("NEKOBOT_WEBUI", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if env in ("0", "false", "no", "off"):
        return False
    return None  # 未指定，交由配置文件决定


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="NekoBot — 多平台 AI 机器人框架")
    parser.add_argument(
        "--webui",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "启用或禁用 WebUI 管理面板（默认启用）。"
            "也可通过环境变量 NEKOBOT_WEBUI=false 禁用。"
        ),
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="指定配置文件路径（默认 data/config.json）",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("NEKOBOT_HOST"),
        help="WebUI 监听地址（默认 0.0.0.0）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("NEKOBOT_PORT", "0")) or None,
        help="WebUI 监听端口（默认 6285）",
    )
    args = parser.parse_args()
    enable_webui = _resolve_webui_flag(args.webui)

    _configure_logging()
    asyncio.run(async_main(
        config_path=args.config,
        enable_webui=enable_webui,
        host=args.host,
        port=args.port
    ))


if __name__ == "__main__":
    main()
