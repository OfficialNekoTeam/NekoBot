"""命令管理模块

提供命令列表、切换、重命名等功能
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from loguru import logger


@dataclass
class CommandDescriptor:
    """命令描述符"""

    handler_full_name: str = ""
    handler_name: str = ""
    plugin_name: str = ""
    plugin_display_name: str | None = None
    module_path: str = ""
    description: str = ""
    command_type: str = "command"  # "command" | "group" | "sub_command"
    original_command: str | None = None
    effective_command: str | None = None
    aliases: List[str] = field(default_factory=list)
    permission: str = "everyone"
    enabled: bool = True
    is_group: bool = False
    is_sub_command: bool = False
    reserved: bool = False
    sub_commands: List["CommandDescriptor"] = field(default_factory=list)


# 全局命令注册表
_command_registry: Dict[str, CommandDescriptor] = {}


def register_command(
    handler_full_name: str,
    handler_name: str,
    plugin_name: str,
    module_path: str,
    description: str = "",
    aliases: List[str] | None = None,
    permission: str = "everyone",
) -> CommandDescriptor:
    """注册命令

    Args:
        handler_full_name: 处理函数完整名称
        handler_name: 处理函数名称
        plugin_name: 插件名称
        module_path: 模块路径
        description: 描述
        aliases: 别名列表
        permission: 权限

    Returns:
        命令描述符
    """
    descriptor = CommandDescriptor(
        handler_full_name=handler_full_name,
        handler_name=handler_name,
        plugin_name=plugin_name,
        module_path=module_path,
        description=description,
        command_type="command",
        original_command=handler_name,
        effective_command=handler_name,
        aliases=aliases or [],
        permission=permission,
        enabled=True,
    )
    _command_registry[handler_full_name] = descriptor
    logger.info(f"注册命令: {handler_full_name}")
    return descriptor


def unregister_command(handler_full_name: str) -> None:
    """注销命令

    Args:
        handler_full_name: 处理函数完整名称
    """
    if handler_full_name in _command_registry:
        del _command_registry[handler_full_name]
        logger.info(f"注销命令: {handler_full_name}")


def unregister_plugin_commands(plugin_name: str) -> int:
    """注销插件的所有命令

    Args:
        plugin_name: 插件名称

    Returns:
        注销的命令数量
    """
    count = 0
    to_remove = []
    for handler_full_name, descriptor in _command_registry.items():
        if descriptor.plugin_name == plugin_name:
            to_remove.append(handler_full_name)
    for handler_full_name in to_remove:
        del _command_registry[handler_full_name]
        count += 1
    logger.info(f"已注销插件 {plugin_name} 的 {count} 个命令")
    return count


def get_command(handler_full_name: str) -> Optional[CommandDescriptor]:
    """获取命令描述符

    Args:
        handler_full_name: 处理函数完整名称

    Returns:
        命令描述符
    """
    return _command_registry.get(handler_full_name)


def list_commands() -> List[Dict[str, Any]]:
    """列出所有命令

    Returns:
        命令列表
    """
    result = []
    for desc in _command_registry.values():
        result.append(
            {
                "handler_full_name": desc.handler_full_name,
                "handler_name": desc.handler_name,
                "plugin": desc.plugin_name,
                "plugin_display_name": desc.plugin_display_name,
                "module_path": desc.module_path,
                "description": desc.description,
                "type": desc.command_type,
                "original_command": desc.original_command,
                "effective_command": desc.effective_command,
                "aliases": desc.aliases,
                "permission": desc.permission,
                "enabled": desc.enabled,
                "is_group": desc.is_group,
                "reserved": desc.reserved,
                "sub_commands": [],
            }
        )
    return result


def toggle_command(
    handler_full_name: str, enabled: bool
) -> Optional[CommandDescriptor]:
    """切换命令启用状态

    Args:
        handler_full_name: 处理函数完整名称
        enabled: 是否启用

    Returns:
        命令描述符
    """
    descriptor = _command_registry.get(handler_full_name)
    if not descriptor:
        raise ValueError("指定的处理函数不存在或不是命令。")

    descriptor.enabled = enabled
    return descriptor


def rename_command(
    handler_full_name: str,
    new_name: str,
    aliases: List[str] | None = None,
) -> Optional[CommandDescriptor]:
    """重命名命令

    Args:
        handler_full_name: 处理函数完整名称
        new_name: 新名称
        aliases: 别名列表

    Returns:
        命令描述符
    """
    descriptor = _command_registry.get(handler_full_name)
    if not descriptor:
        raise ValueError("指定的处理函数不存在或不是命令。")

    new_name = new_name.strip()
    if not new_name:
        raise ValueError("指令名不能为空。")

    # 检查命令名是否被占用
    for desc in _command_registry.values():
        if desc.handler_full_name != handler_full_name and (
            desc.effective_command == new_name or new_name in desc.aliases
        ):
            raise ValueError(f"指令名 '{new_name}' 已被其他指令占用。")

    # 检查别名是否被占用
    if aliases:
        for alias in aliases:
            alias = alias.strip()
            if not alias:
                continue
            for desc in _command_registry.values():
                if desc.handler_full_name != handler_full_name and (
                    desc.effective_command == alias or alias in desc.aliases
                ):
                    raise ValueError(f"别名 '{alias}' 已被其他指令占用。")

    descriptor.effective_command = new_name
    descriptor.aliases = aliases or []
    return descriptor


def list_command_conflicts() -> List[Dict[str, Any]]:
    """列出所有冲突的命令

    Returns:
        冲突命令列表
    """
    conflicts: Dict[str, List[CommandDescriptor]] = {}
    for desc in _command_registry.values():
        if desc.effective_command and desc.enabled:
            if desc.effective_command not in conflicts:
                conflicts[desc.effective_command] = []
            conflicts[desc.effective_command].append(desc)

    details = [
        {
            "conflict_key": key,
            "handlers": [
                {
                    "handler_full_name": item.handler_full_name,
                    "plugin": item.plugin_name,
                    "current_name": item.effective_command,
                }
                for item in group
            ],
        }
        for key, group in conflicts.items()
        if len(group) > 1
    ]
    return details
