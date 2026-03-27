from __future__ import annotations

from dataclasses import dataclass, field

from .types import ValueMap


@dataclass(frozen=True)
class OneBotV11AdapterConfig:
    instance_uuid: str
    host: str = "0.0.0.0"
    port: int = 6299
    path: str = "/ws"
    access_token: str | None = None
    self_id: str | None = None
    command_prefix: str = "/"
    metadata: ValueMap = field(default_factory=dict)


def build_onebot_v11_config(raw_config: dict[str, object]) -> OneBotV11AdapterConfig:
    instance_uuid = raw_config.get("instance_uuid")
    if not isinstance(instance_uuid, str) or not instance_uuid:
        raise ValueError("OneBot v11 config requires 'instance_uuid'")

    host = raw_config.get("host", "0.0.0.0")
    port = raw_config.get("port", 6299)
    path = raw_config.get("path", "/ws")
    access_token = raw_config.get("access_token")
    self_id = raw_config.get("self_id")
    command_prefix = raw_config.get("command_prefix", "/")

    metadata: ValueMap = {
        str(key): value
        for key, value in raw_config.items()
        if key
        not in {
            "type",
            "instance_uuid",
            "host",
            "port",
            "path",
            "access_token",
            "self_id",
            "command_prefix",
            "enabled",
        }
    }

    return OneBotV11AdapterConfig(
        instance_uuid=instance_uuid,
        host=host if isinstance(host, str) else "0.0.0.0",
        port=port if isinstance(port, int) else 6299,
        path=path if isinstance(path, str) else "/ws",
        access_token=access_token if isinstance(access_token, str) else None,
        self_id=self_id if isinstance(self_id, str) else None,
        command_prefix=command_prefix if isinstance(command_prefix, str) else "/",
        metadata=metadata,
    )
