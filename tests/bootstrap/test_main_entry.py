from __future__ import annotations

import json
from pathlib import Path

from main import async_main


async def test_async_main_returns_runtime_without_blocking_when_run_forever_is_false(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    _ = config_path.write_text(
        json.dumps(
            {
                "platforms": [],
                "framework_config": {"default_provider": "openai"},
            }
        ),
        encoding="utf-8",
    )

    runtime = await async_main(config_path, run_forever=False)

    assert runtime.configuration.resolve_provider_name() == "openai"
    assert runtime.running_platforms == ()
