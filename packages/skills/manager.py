from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import yaml
from loguru import logger

if TYPE_CHECKING:
    from ..app import NekoBotFramework


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str
    path: Path
    content: Optional[str] = None


class SkillManager:
    """Manages instruction-based skills (Markdown files)."""

    def __init__(self, framework: NekoBotFramework, data_dir: str = "data/skills") -> None:
        self.framework = framework
        self.data_dir = Path(data_dir)
        self._skills: dict[str, SkillInfo] = {}

    async def load_all(self, directory: Optional[str] = None) -> None:
        """Load skills from the directory (two levels deep, no full tree walk).

        Scans:
          - <dir>/*.md            (top-level Markdown files)
          - <dir>/<subdir>/skill.md  (one subdir level only)
        """
        search_dir = Path(directory) if directory else self.data_dir
        if not search_dir.exists():
            search_dir.mkdir(parents=True, exist_ok=True)
            return

        logger.info("SkillManager: loading skills from {}", search_dir)
        self._skills.clear()

        candidates: list[Path] = []
        for entry in search_dir.iterdir():
            if entry.is_file() and entry.suffix.lower() == ".md":
                candidates.append(entry)
            elif entry.is_dir():
                skill_file = entry / "skill.md"
                if not skill_file.exists():
                    skill_file = entry / "SKILL.md"
                if skill_file.exists():
                    candidates.append(skill_file)

        for path in candidates:
            await self._load_skill_file(path)

        logger.info("SkillManager: loaded {} skill(s)", len(self._skills))

    async def _load_skill_file(self, path: Path) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析 YAML Frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    metadata = yaml.safe_load(parts[1])
                    if isinstance(metadata, dict):
                        name = metadata.get("name")
                        description = metadata.get("description")
                        if name and description:
                            self._skills[name] = SkillInfo(
                                name=name,
                                description=description,
                                path=path,
                                content=parts[2].strip()
                            )
                            logger.debug("SkillManager: loaded skill {!r}", name)
                        else:
                            logger.warning("SkillManager: missing name or description in {}", path)
                    else:
                        logger.warning("SkillManager: invalid frontmatter in {}", path)
                else:
                    logger.warning("SkillManager: malformed frontmatter in {}", path)
            else:
                logger.warning("SkillManager: no frontmatter found in {}", path)
        except Exception as exc:
            logger.error("SkillManager: failed to load {}: {}", path, exc)

    def get_skill(self, name: str) -> Optional[SkillInfo]:
        return self._skills.get(name)

    def list_skills(self) -> list[SkillInfo]:
        return list(self._skills.values())

    @property
    def skill_descriptions(self) -> list[dict[str, str]]:
        """Used for injecting into system prompt."""
        return [
            {"name": s.name, "description": s.description}
            for s in self._skills.values()
        ]
