from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from packages.bootstrap import BootstrappedRuntime, bootstrap_runtime, load_app_config


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def async_main(
    config_path: str | Path | None = None,
    *,
    run_forever: bool = True,
) -> BootstrappedRuntime:
    config = load_app_config(config_path)
    runtime = await bootstrap_runtime(config)
    if run_forever and runtime.running_platforms:
        try:
            _ = await asyncio.Event().wait()
        finally:
            _ = await runtime.stop()

    return runtime


def main() -> None:
    _configure_logging()
    _ = asyncio.run(async_main())


if __name__ == "__main__":
    main()
