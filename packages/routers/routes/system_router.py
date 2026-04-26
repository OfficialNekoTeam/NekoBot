from __future__ import annotations

import sys

from quart import Blueprint, current_app

from ..deps import require_auth

system_bp = Blueprint("system", __name__, url_prefix="/api/v1/system")


# ---------------------------------------------------------------------------
# System info
# ---------------------------------------------------------------------------


@system_bp.route("/info", methods=["GET"])
@require_auth
async def system_info() -> tuple[dict, int] | dict:
    import datetime

    start_time = current_app.config.get("START_TIME")
    now = datetime.datetime.now(datetime.timezone.utc)
    uptime_seconds = (now - start_time).total_seconds() if start_time else None

    info: dict = {
        "python_version": sys.version,
        "uptime_seconds": uptime_seconds,
    }

    try:
        import psutil
        process = psutil.Process()
        mem = process.memory_info()
        info["memory"] = {
            "rss_bytes": mem.rss,
            "vms_bytes": mem.vms,
        }
        info["cpu_percent"] = process.cpu_percent(interval=None)
        info["system_memory"] = {
            "total": psutil.virtual_memory().total,
            "available": psutil.virtual_memory().available,
            "percent": psutil.virtual_memory().percent,
        }
    except ImportError:
        info["memory"] = None
        info["system_memory"] = None

    fw = current_app.config.get("FRAMEWORK")
    if fw is not None:
        rr = getattr(fw, "runtime_registry", None)
        if rr is not None:
            info["plugins_loaded"] = len(rr.plugins)
            info["providers_loaded"] = len(rr.providers)

    return {"success": True, "data": info}


# ---------------------------------------------------------------------------
# Config reload
# ---------------------------------------------------------------------------


@system_bp.route("/reload-config", methods=["POST"])
@require_auth
async def reload_config() -> tuple[dict, int] | dict:
    fw = current_app.config.get("FRAMEWORK")
    if fw is None:
        return {"success": False, "message": "Framework not available."}, 503
    try:
        from pathlib import Path

        from ...bootstrap.config import load_app_config
        new_config = load_app_config(Path("data/config.json"))
        await fw.update_framework_config(new_config)
        return {"success": True, "message": "Config reloaded."}
    except Exception as exc:
        return {"success": False, "message": str(exc)}, 500
