from __future__ import annotations

from quart import Blueprint, current_app, request

from ...bootstrap.manager import ConfigManager
from ...plugins.reloader import PluginReloader
from ..deps import require_auth

plugin_bp = Blueprint("plugins", __name__, url_prefix="/api/v1/plugins")


def _framework():
    return current_app.config.get("FRAMEWORK")


def _manager() -> ConfigManager | None:
    fw = _framework()
    return getattr(fw, "config_manager", None) if fw else None


def _reloader() -> PluginReloader | None:
    fw = _framework()
    return getattr(fw, "plugin_reloader", None) if fw else None


def _build_plugin_info(name: str, fw, reloader: PluginReloader | None, mgr: ConfigManager | None) -> dict:
    registered = fw.runtime_registry.plugins.get(name)
    spec = registered.spec if registered else None

    # metadata from directory name (reloader tracks dir_name → metadata)
    meta = None
    if reloader:
        module_path = reloader.loaded_plugins.get(name, "")
        dir_name = module_path.split(".")[-1] if "." in module_path else module_path
        meta = reloader.get_metadata(dir_name)

    # enabled flag from plugin_bindings
    enabled = True
    if mgr:
        bindings = mgr.get_plugin_bindings()
        binding = bindings.get(name, {})
        enabled = bool(binding.get("enabled", True))

    info: dict = {"name": name, "enabled": enabled}
    if spec:
        info.update({
            "version": spec.version,
            "description": spec.description,
            "author": spec.author,
        })
    if meta:
        info.update({
            "display_name": meta.display_name,
            "repository": meta.repository,
            "tags": meta.tags,
            "nekobot_version": meta.nekobot_version,
            "support_platforms": meta.support_platforms,
            "root_dir": meta.root_dir,
        })
    return info


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


@plugin_bp.route("", methods=["GET"], strict_slashes=False)
@require_auth
async def list_plugins() -> tuple[dict, int] | dict:
    fw = _framework()
    if fw is None:
        return {"success": False, "message": "Framework not available."}, 503
    reloader = _reloader()
    mgr = _manager()
    names = list(fw.runtime_registry.plugins.keys())
    data = [_build_plugin_info(n, fw, reloader, mgr) for n in names]
    return {"success": True, "data": data}


# ---------------------------------------------------------------------------
# Single resource
# ---------------------------------------------------------------------------


@plugin_bp.route("/<name>", methods=["GET"])
@require_auth
async def get_plugin(name: str) -> tuple[dict, int] | dict:
    fw = _framework()
    if fw is None:
        return {"success": False, "message": "Framework not available."}, 503
    if name not in fw.runtime_registry.plugins:
        return {"success": False, "message": f"Plugin {name!r} not found."}, 404
    info = _build_plugin_info(name, fw, _reloader(), _manager())
    return {"success": True, "data": info}


# ---------------------------------------------------------------------------
# Enable / disable
# ---------------------------------------------------------------------------


@plugin_bp.route("/<name>/enabled", methods=["PATCH"])
@require_auth
async def set_plugin_enabled(name: str) -> tuple[dict, int] | dict:
    fw = _framework()
    if fw is None:
        return {"success": False, "message": "Framework not available."}, 503
    if name not in fw.runtime_registry.plugins:
        return {"success": False, "message": f"Plugin {name!r} not found."}, 404
    body = await request.get_json()
    if not isinstance(body, dict) or "enabled" not in body:
        return {"success": False, "message": "enabled field is required."}, 400
    mgr = _manager()
    if mgr is None:
        return {"success": False, "message": "Config manager not available."}, 503
    config_id = str(body.get("config_id", "default"))
    bindings = mgr.get_plugin_bindings(config_id)
    existing = dict(bindings.get(name, {}))
    existing["enabled"] = bool(body["enabled"])
    await mgr.set_plugin_binding(name, existing, config_id)
    return {"success": True, "data": {"name": name, "enabled": existing["enabled"]}}


# ---------------------------------------------------------------------------
# Plugin config
# ---------------------------------------------------------------------------


@plugin_bp.route("/<name>/config", methods=["GET"])
@require_auth
async def get_plugin_config(name: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return {"success": False, "message": "Config manager not available."}, 503
    config_id = request.args.get("config_id", "default")
    cfg = mgr.get_plugin_configs(config_id).get(name, {})
    return {"success": True, "data": cfg}


@plugin_bp.route("/<name>/config", methods=["PUT"])
@require_auth
async def update_plugin_config(name: str) -> tuple[dict, int] | dict:
    mgr = _manager()
    if mgr is None:
        return {"success": False, "message": "Config manager not available."}, 503
    body = await request.get_json()
    if not isinstance(body, dict):
        return {"success": False, "message": "Invalid request body."}, 400
    config_id = str(body.pop("config_id", "default"))
    await mgr.set_plugin_config(name, body, config_id)
    return {"success": True, "message": f"Plugin {name!r} config saved."}


# ---------------------------------------------------------------------------
# Hot reload
# ---------------------------------------------------------------------------


@plugin_bp.route("/<name>/reload", methods=["POST"])
@require_auth
async def reload_plugin(name: str) -> tuple[dict, int] | dict:
    fw = _framework()
    if fw is None:
        return {"success": False, "message": "Framework not available."}, 503
    reloader = _reloader()
    if reloader is None:
        return {"success": False, "message": "Plugin reloader not available."}, 503
    if name not in fw.runtime_registry.plugins and name not in reloader.loaded_plugins:
        return {"success": False, "message": f"Plugin {name!r} not found."}, 404
    ok = reloader.reload_plugin(name)
    if not ok:
        return {"success": False, "message": f"Failed to reload plugin {name!r}."}, 500
    return {"success": True, "message": f"Plugin {name!r} reloaded."}
