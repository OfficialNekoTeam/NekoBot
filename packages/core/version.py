"""版本管理模块

提供版本信息的读取、显示和管理功能
"""

import json
from pathlib import Path
from typing import Dict, Any

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 版本信息文件路径
VERSION_FILE = PROJECT_ROOT / "data" / "VERSION"
VERSION_FILE_FALLBACK = PROJECT_ROOT / "nekobot" / "VERSION"

# 默认版本信息
DEFAULT_VERSION = {
    "version": "1.0.0",
    "build_time": "",
    "git_commit": "",
    "git_branch": "",
    "description": "NekoBot - 支持多聊天平台大模型的聊天机器人框架",
}


def get_version_info() -> Dict[str, Any]:
    """获取版本信息

    Returns:
        版本信息字典
    """
    version = DEFAULT_VERSION

    # 尝试从 VERSION 文件读取
    version_file = None
    if VERSION_FILE.exists():
        version_file = VERSION_FILE
    elif VERSION_FILE_FALLBACK.exists():
        version_file = VERSION_FILE_FALLBACK

    if version_file and version_file.exists():
        try:
            import json
            with open(version_file, "r", encoding="utf-8") as f:
                version = json.load(f)
        except Exception:
            pass

    return version


def display_version() -> str:
    """显示版本信息

    Returns:
        格式化的版本信息字符串
    """
    version_info = get_version_info()

    output = f"""
{'=' * 50}
NekoBot
{'=' * 50}
版本: {version_info.get('version', 'unknown')}
构建时间: {version_info.get('build_time', 'N/A')}
Git 提交: {version_info.get('git_commit', 'N/A')[:8] if version_info.get('git_commit') else 'N/A'}
分支: {version_info.get('git_branch', 'N/A')}
{'=' * 50}
{version_info.get('description', '')}
{'=' * 50}
"""

    return output.strip()


def write_version_file(version: str = None, build_time: str = None,
                        git_commit: str = None, git_branch: str = None) -> None:
    """写入版本信息到文件

    Args:
        version: 版本号
        build_time: 构建时间
        git_commit: Git 提交哈希
        git_branch: Git 分支

    Returns:
        None
    """
    version_data = DEFAULT_VERSION.copy()

    if version is not None:
        version_data["version"] = version
    if build_time is not None:
        version_data["build_time"] = build_time
    if git_commit is not None:
        version_data["git_commit"] = git_commit
    if git_branch is not None:
        version_data["git_branch"] = git_branch

    # 写入文件
    version_file = VERSION_FILE
    version_file.parent.mkdir(parents=True, exist_ok=True)

    with open(version_file, "w", encoding="utf-8") as f:
        json.dump(version_data, f, indent=2, ensure_ascii=False)

    # 同时写入 fallback 位置
    VERSION_FILE_FALLBACK.parent.mkdir(parents=True, exist_ok=True)
    with open(VERSION_FILE_FALLBACK, "w", encoding="utf-8") as f:
        json.dump(version_data, f, indent=2, ensure_ascii=False)


__all__ = [
    "get_version_info",
    "display_version",
    "write_version_file",
]
