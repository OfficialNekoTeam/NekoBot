from __future__ import annotations

import os
from pathlib import Path

from quart import Blueprint, Response, current_app, request, send_file

from ..deps import require_auth

log_bp = Blueprint("logs", __name__, url_prefix="/api/v1/logs")

_LOG_DIR = Path("data/logs")
_DEFAULT_TAIL_LINES = 200
_MAX_TAIL_LINES = 5000


def _safe_log_path(filename: str) -> Path | None:
    """Resolve and validate that the path stays within _LOG_DIR."""
    try:
        target = (_LOG_DIR / filename).resolve()
        _LOG_DIR.resolve()
        target.relative_to(_LOG_DIR.resolve())
        return target
    except (ValueError, Exception):
        return None


# ---------------------------------------------------------------------------
# List log files
# ---------------------------------------------------------------------------


@log_bp.route("", methods=["GET"], strict_slashes=False)
@require_auth
async def list_logs() -> tuple[dict, int] | dict:
    if not _LOG_DIR.exists():
        return {"success": True, "data": []}
    files = []
    for entry in sorted(_LOG_DIR.iterdir()):
        if entry.is_file():
            stat = entry.stat()
            files.append({
                "name": entry.name,
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
            })
    return {"success": True, "data": files}


# ---------------------------------------------------------------------------
# Tail a log file
# ---------------------------------------------------------------------------


@log_bp.route("/<filename>", methods=["GET"])
@require_auth
async def tail_log(filename: str) -> tuple[dict, int] | dict | Response:
    path = _safe_log_path(filename)
    if path is None or not path.exists():
        return {"success": False, "message": "Log file not found."}, 404

    download = request.args.get("download", "").lower() in ("1", "true", "yes")
    if download:
        return await send_file(path, as_attachment=True, download_name=filename)

    n = min(int(request.args.get("lines", _DEFAULT_TAIL_LINES)), _MAX_TAIL_LINES)
    try:
        lines = _tail_file(path, n)
        return {"success": True, "data": {"filename": filename, "lines": lines}}
    except Exception as exc:
        return {"success": False, "message": str(exc)}, 500


def _tail_file(path: Path, n: int) -> list[str]:
    """Read the last n lines of a file efficiently."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        if size == 0:
            return []

        buf_size = min(size, 8192)
        chunks: list[bytes] = []
        lines_found = 0
        pos = size

        while pos > 0 and lines_found <= n:
            read_size = min(buf_size, pos)
            pos -= read_size
            f.seek(pos)
            chunk = f.read(read_size)
            chunks.append(chunk)
            lines_found += chunk.count(b"\n")

        raw = b"".join(reversed(chunks))
        all_lines = raw.decode(errors="replace").splitlines()
        return all_lines[-n:] if len(all_lines) > n else all_lines
