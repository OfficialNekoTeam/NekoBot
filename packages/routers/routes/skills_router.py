from __future__ import annotations

from quart import Blueprint, current_app

from ..deps import require_auth

skills_bp = Blueprint("skills", __name__, url_prefix="/api/v1/skills")


def _skill_manager():
    fw = current_app.config.get("FRAMEWORK")
    return getattr(fw, "skill_manager", None) if fw else None


def _skill_to_dict(skill, include_content: bool = False) -> dict:
    d: dict = {
        "name": skill.name,
        "description": skill.description,
        "path": str(skill.path),
    }
    if include_content:
        d["content"] = skill.content
    return d


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@skills_bp.route("", methods=["GET"], strict_slashes=False)
@require_auth
async def list_skills() -> tuple[dict, int] | dict:
    mgr = _skill_manager()
    if mgr is None:
        return {"success": False, "message": "Skill manager not available."}, 503
    skills = [_skill_to_dict(s) for s in mgr.list_skills()]
    return {"success": True, "data": skills}


# ---------------------------------------------------------------------------
# Single skill
# ---------------------------------------------------------------------------


@skills_bp.route("/<name>", methods=["GET"])
@require_auth
async def get_skill(name: str) -> tuple[dict, int] | dict:
    mgr = _skill_manager()
    if mgr is None:
        return {"success": False, "message": "Skill manager not available."}, 503
    skill = mgr.get_skill(name)
    if skill is None:
        return {"success": False, "message": f"Skill {name!r} not found."}, 404
    return {"success": True, "data": _skill_to_dict(skill, include_content=True)}


# ---------------------------------------------------------------------------
# Reload all skills from disk
# ---------------------------------------------------------------------------


@skills_bp.route("/reload", methods=["POST"])
@require_auth
async def reload_skills() -> tuple[dict, int] | dict:
    mgr = _skill_manager()
    if mgr is None:
        return {"success": False, "message": "Skill manager not available."}, 503
    try:
        await mgr.load_all()
        skills = [_skill_to_dict(s) for s in mgr.list_skills()]
        return {"success": True, "data": skills}
    except Exception as exc:
        return {"success": False, "message": str(exc)}, 500
