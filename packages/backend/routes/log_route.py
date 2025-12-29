"""日志管理API

提供日志的查看和过滤功能
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from loguru import logger

from .route import Route, Response, RouteContext

LOGS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "logs"


class LogRoute(Route):
    """日志管理路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.logs_dir = LOGS_DIR
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.routes = {
            "/api/logs/list": ("GET", self.get_log_files),
            "/api/logs/content": ("GET", self.get_log_content),
        }

    async def get_log_files(self) -> Dict[str, Any]:
        """获取日志文件列表"""
        try:
            from quart import request

            log_type = request.args.get("type", "all")

            log_files = []
            for file in self.logs_dir.iterdir():
                if file.is_file() and file.suffix == ".log":
                    file_name = file.name
                    file_size = file.stat().st_size
                    modified_time = datetime.fromtimestamp(file.stat().st_mtime)

                    if log_type == "all" or self._match_log_type(file_name, log_type):
                        log_files.append(
                            {
                                "name": file_name,
                                "size": file_size,
                                "modified": modified_time.isoformat(),
                            }
                        )

            log_files.sort(key=lambda x: x["modified"], reverse=True)
            return Response().ok(data={"files": log_files}).to_dict()
        except Exception as e:
            logger.error(f"获取日志列表失败: {e}")
            return Response().error(f"获取日志列表失败: {str(e)}").to_dict()

    async def get_log_content(self) -> Dict[str, Any]:
        """获取日志文件内容"""
        try:
            from quart import request

            file_name = request.args.get("file")
            if not file_name:
                return Response().error("缺少文件名参数").to_dict()

            file_path = self.logs_dir / file_name
            if not file_path.exists() or not file_path.is_file():
                return Response().error("日志文件不存在").to_dict()

            lines = request.args.get("lines", "100")
            try:
                lines = int(lines)
            except ValueError:
                lines = 100

            lines = max(10, min(lines, 1000))

            content = self._read_last_lines(file_path, lines)
            return (
                Response()
                .ok(
                    data={
                        "file": file_name,
                        "content": content,
                        "lines": len(content.split("\n")),
                    }
                )
                .to_dict()
            )
        except Exception as e:
            logger.error(f"获取日志内容失败: {e}")
            return Response().error(f"获取日志内容失败: {str(e)}").to_dict()

    def _match_log_type(self, file_name: str, log_type: str) -> bool:
        """匹配日志类型"""
        if log_type == "all":
            return True

        if log_type == "error":
            return "error" in file_name.lower()
        if log_type == "info":
            return "info" in file_name.lower()
        if log_type == "debug":
            return "debug" in file_name.lower()

        return True

    def _read_last_lines(self, file_path: Path, lines: int) -> str:
        """读取文件最后几行"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()
                if len(all_lines) <= lines:
                    return "".join(all_lines)
                return "".join(all_lines[-lines:])
        except Exception as e:
            logger.error(f"读取日志文件失败: {e}")
            return f"读取日志文件失败: {str(e)}"
