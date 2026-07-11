"""SkillFactory — manages SkillConfig CRUD and Skill instance cache.

Each SkillConfig is persisted as data/skills/{id}.json.
Skill instances use lazy loading: on import scan directly instantiates, on load restores from JSON then get_instance creates on demand.
"""

import json
from pathlib import Path

from backend.factories import _safe_filename, _skill_id
from backend.logging import get_backend_logger
from backend.schemas import SkillConfig
from bbagent.core.skill import Skill, parse_skill_md, scan_skills


class SkillFactory:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._configs: dict[str, SkillConfig] = {}   # skill_id -> SkillConfig
        self._instances: dict[str, Skill] = {}        # skill_id -> Skill instance
        self._logger = get_backend_logger("state.skill_factory")

    # --- paths ---

    def _skills_dir(self) -> Path:
        return self._data_dir / "skills"

    def _file_path(self, skill_id: str) -> Path:
        return self._skills_dir() / f"{_safe_filename(skill_id)}.json"

    def _save_config(self, config: SkillConfig):
        self._skills_dir().mkdir(parents=True, exist_ok=True)
        self._file_path(config.id).write_text(
            config.model_dump_json(indent=2), encoding="utf-8",
        )

    def _delete_config_file(self, skill_id: str):
        p = self._file_path(skill_id)
        if p.exists():
            p.unlink()

    @staticmethod
    def _load_single_skill(skill_dir: Path) -> Skill | None:
        """Load Skill instance from a single skill directory."""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None
        skill_data = parse_skill_md(skill_md)
        if not skill_data:
            return None
        return Skill(
            name=skill_data["name"],
            description=skill_data["description"],
            body=skill_data["body"],
            path=skill_dir,
            metadata=skill_data["metadata"],
        )

    # --- load ---

    def load(self):
        """Restore all SkillConfigs from data/skills/*.json. Skill instances lazy-loaded afterwards."""
        skills_dir = self._skills_dir()
        self._configs = {}
        self._instances = {}
        for item in sorted(skills_dir.iterdir()):
            if not item.is_file() or item.suffix != ".json":
                continue
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                config = SkillConfig(**data)
                self._configs[config.id] = config
            except Exception as e:
                self._logger.warning(f"Failed to load skill config from {item}: {e}")

    # --- accessors ---

    def get(self, skill_id: str) -> SkillConfig | None:
        return self._configs.get(skill_id)

    def get_instance(self, skill_id: str) -> Skill | None:
        """Get Skill runtime instance. Lazy-loads from source directory on first call and caches."""
        if skill_id in self._instances:
            return self._instances[skill_id]

        config = self._configs.get(skill_id)
        if not config:
            return None

        skill_dir = Path(config.path)
        if not skill_dir.exists():
            self._logger.warning(f"Skill source dir not found: {config.path}")
            return None

        skill = self._load_single_skill(skill_dir)
        if not skill:
            self._logger.warning(f"Failed to load skill from {config.path}")
            return None

        self._instances[skill_id] = skill
        return skill

    def list_all(self) -> list[SkillConfig]:
        return list(self._configs.values())

    # --- import ---

    def import_dir(self, dir_path: Path) -> tuple[list[SkillConfig], list[str]]:
        """Scan directory, generate SkillConfig and persist, also create Skill instance cache.

        Returns:
            (added, skipped): imported configs and list of already-existing skipped skill names.
        """
        scanned = scan_skills(dir_path)
        added: list[SkillConfig] = []
        skipped: list[str] = []

        for name, skill in scanned.items():
            skill_path = str((skill.path or dir_path).resolve())
            sid = _skill_id(skill_path)

            if sid in self._configs:
                skipped.append(name)
                continue

            config = SkillConfig(
                id=sid,
                name=skill.name,
                description=skill.description,
                path=skill_path,
            )
            self._configs[sid] = config
            self._instances[sid] = skill
            self._save_config(config)
            added.append(config)

        return added, skipped

    # --- delete ---

    def delete(self, skill_id: str) -> bool:
        """Delete a single SkillConfig and its cached Skill instance."""
        if skill_id not in self._configs:
            return False
        del self._configs[skill_id]
        self._instances.pop(skill_id, None)
        self._delete_config_file(skill_id)
        return True

    # --- refresh ---

    def refresh(self, skill_id: str) -> SkillConfig | None:
        """Reload skill from source file and update config + clear instance cache."""
        config = self._configs.get(skill_id)
        if not config:
            return None

        skill_dir = Path(config.path)
        if not skill_dir.exists():
            self._logger.warning(f"Skill source dir not found, deleting stale config: {config.path}")
            self.delete(skill_id)
            return None

        skill = self._load_single_skill(skill_dir)
        if not skill:
            self._logger.warning(f"Failed to reload skill, deleting stale config: {config.path}")
            self.delete(skill_id)
            return None

        new_config = SkillConfig(
            id=skill_id,
            name=skill.name,
            description=skill.description,
            path=config.path,
        )
        self._configs[skill_id] = new_config
        self._instances.pop(skill_id, None)
        self._save_config(new_config)
        return new_config
