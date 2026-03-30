from __future__ import annotations

import asyncio
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
    logger.add(
        "data/logs/nekobot_{time:YYYY-MM-DD}.log",
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
) -> BootstrappedRuntime:
    config = load_app_config(config_path)
    runtime = await bootstrap_runtime(config)
    if run_forever and runtime.running_platforms:
        try:
            _ = await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
        finally:
            _ = await runtime.stop()

    return runtime


def main() -> None:
    _configure_logging()
    try:
        _ = asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("收到退出信号，正在关闭...")


if __name__ == "__main__":
    main()
