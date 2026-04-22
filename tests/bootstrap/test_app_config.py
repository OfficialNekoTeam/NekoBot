from __future__ import annotations

import json
from pathlib import Path

from packages.bootstrap.config import (
    BootstrapConfig,
    load_app_config,
    normalize_app_config,
)
from packages.bootstrap.defaults import INITIAL_CONFIG_TEMPLATE


def test_normalize_app_config_splits_framework_and_platform_data() -> None:
    config = normalize_app_config(
        {
            "framework_config": {"default_provider": "openai"},
            "plugin_configs": {"demo": {"enabled": True}},
            "platforms": [
                {
                    "type": "onebot_v11",
                    "instance_uuid": "bot-a",
                    "enabled": True,
                    "host": "127.0.0.1",
                }
            ],
        }
    )

    assert isinstance(config, BootstrapConfig)
    assert config.framework_config == {"default_provider": "openai"}
    assert config.plugin_configs == {"demo": {"enabled": True}}
    assert config.platforms == [
        {
            "type": "onebot_v11",
            "instance_uuid": "bot-a",
            "enabled": True,
            "host": "127.0.0.1",
        }
    ]


def test_load_app_config_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    config = load_app_config(tmp_path / "missing.json")

    assert config == normalize_app_config(INITIAL_CONFIG_TEMPLATE)


def test_load_app_config_reads_json_file(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    _ = config_path.write_text(
        json.dumps(
            {
                "framework_config": {"default_provider": "gemini"},
                "platforms": [{"type": "onebot_v11", "instance_uuid": "bot-a"}],
            }
        ),
        encoding="utf-8",
    )

    config = load_app_config(config_path)

    # check_config_integrity merges DEFAULT_CONFIG fields in, so use subset check
    assert config.framework_config.get("default_provider") == "gemini"
    assert config.platforms == [{"type": "onebot_v11", "instance_uuid": "bot-a"}]
