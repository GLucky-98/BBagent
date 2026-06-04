"""SkillFactory — manages SkillConfig CRUD and Skill instance cache."""

import json
import logging
from pathlib import Path
from typing import Optional

from BBagent.core.skill import Skill, scan_skills

from backend.schemas import SkillConfig
from backend.factories import _skill_id


class SkillFactory:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._configs: dict[str, SkillConfig] = {}   # skill_id -> SkillConfig
        self._instances: dict[str, Skill] = {}        # skill_id -> Skill instance
        self._skill_dirs: list[str] = []
        self._logger = logging.getLogger("state.skill_factory")

    def _skill_dirs_path(self) -> Path:
        return self._data_dir / "skills" / "skills.json"

    # --- load ---

    def load(self):
        dirs_path = self._skill_dirs_path()
        if dirs_path.exists():
            try:
                self._skill_dirs = json.loads(dirs_path.read_text(encoding="utf-8"))
            except Exception as e:
                self._logger.warning(f"Failed to load skill dirs: {e}")
                self._skill_dirs = []
        else:
            self._skill_dirs = []

        self._configs = {}
        self._instances = {}
        for d in self._skill_dirs:
            dir_path = Path(d)
            if not dir_path.exists():
                continue
            try:
                scanned = scan_skills(dir_path)
                for name, skill in scanned.items():
                    # Generate deterministic skill id from path
                    skill_path = str(skill.path.resolve()) if skill.path else str(dir_path / name)
                    sid = _skill_id(skill_path)
                    if sid in self._instances:
                        continue
                    self._instances[sid] = skill
                    self._configs[sid] = SkillConfig(
                        id=sid,
                        name=skill.name,
                        description=skill.description,
                        path=skill_path,
                    )
            except Exception as e:
                self._logger.warning(f"Failed to load skills from {d}: {e}")

    # --- accessors ---

    def get(self, skill_id: str) -> Optional[SkillConfig]:
        return self._configs.get(skill_id)

    def get_instance(self, skill_id: str) -> Optional[Skill]:
        return self._instances.get(skill_id)

    def list_all(self) -> list[SkillConfig]:
        return list(self._configs.values())

    # --- directory management ---

    def add_dir(self, dir_path: Path):
        path_str = str(dir_path.resolve())
        if path_str not in self._skill_dirs:
            self._skill_dirs.append(path_str)
        self._save_dirs()
        # Re-scan to pick up new skills
        try:
            scanned = scan_skills(dir_path)
            for name, skill in scanned.items():
                skill_path = str(skill.path.resolve()) if skill.path else str(dir_path / name)
                sid = _skill_id(skill_path)
                if not getattr(skill, "id", None):
                    skill.id = sid
                if sid in self._instances:
                    continue
                self._instances[sid] = skill
                self._configs[sid] = SkillConfig(
                    id=sid,
                    name=skill.name,
                    description=skill.description,
                    path=skill_path,
                )
        except Exception as e:
            self._logger.warning(f"Failed to scan skills from {dir_path}: {e}")

    def remove_dir(self, dir_path: str):
        if dir_path in self._skill_dirs:
            self._skill_dirs.remove(dir_path)
            self._save_dirs()

    def _save_dirs(self):
        path = self._skill_dirs_path()
        path.write_text(
            json.dumps(self._skill_dirs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
