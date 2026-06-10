"""SkillFactory — manages SkillConfig CRUD and Skill instance cache.

每个 SkillConfig 持久化为 data/skills/{id}.json。
Skill 实例采用懒加载：import 时 scan 直接实例化，load 从 JSON 恢复后通过 get_instance 按需创建。
"""

import json
from pathlib import Path
from typing import Optional

from bbagent.core.skill import Skill, scan_skills, parse_skill_md

from backend.schemas import SkillConfig
from backend.factories import _skill_id, _safe_filename
from backend.logging import get_backend_logger


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
        self._file_path(config.id).write_text(
            config.model_dump_json(indent=2), encoding="utf-8",
        )

    def _delete_config_file(self, skill_id: str):
        p = self._file_path(skill_id)
        if p.exists():
            p.unlink()

    @staticmethod
    def _load_single_skill(skill_dir: Path) -> Optional[Skill]:
        """从单个 skill 目录加载 Skill 实例。"""
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
        """从 data/skills/*.json 恢复所有 SkillConfig。Skill 实例后续懒加载。"""
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

    def get(self, skill_id: str) -> Optional[SkillConfig]:
        return self._configs.get(skill_id)

    def get_instance(self, skill_id: str) -> Optional[Skill]:
        """获取 Skill 运行时实例。首次调用时从源目录懒加载并缓存。"""
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
        """扫描目录，生成 SkillConfig 并落盘，同时创建 Skill 实例缓存。

        Returns:
            (added, skipped): imported configs 和已存在被跳过的 skill name 列表。
        """
        scanned = scan_skills(dir_path)
        added: list[SkillConfig] = []
        skipped: list[str] = []

        for name, skill in scanned.items():
            skill_path = str(skill.path.resolve())
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
        """删除单个 SkillConfig 和对应的缓存 Skill 实例。"""
        if skill_id not in self._configs:
            return False
        del self._configs[skill_id]
        self._instances.pop(skill_id, None)
        self._delete_config_file(skill_id)
        return True

    # --- refresh ---

    def refresh(self, skill_id: str) -> Optional[SkillConfig]:
        """重新从源文件加载 skill 并更新 config + 清除实例缓存。"""
        config = self._configs.get(skill_id)
        if not config:
            return None

        skill_dir = Path(config.path)
        if not skill_dir.exists():
            self._logger.warning(f"Skill source dir not found, keeping stale config: {config.path}")
            return config

        skill = self._load_single_skill(skill_dir)
        if not skill:
            return config

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
