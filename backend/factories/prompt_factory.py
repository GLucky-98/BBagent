"""PromptFactory — manages PromptConfig CRUD. Simplest factory."""

import json
from pathlib import Path

from backend.factories import _next_id, _safe_filename
from backend.logging import get_backend_logger
from backend.schemas import PromptConfig


class PromptFactory:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._configs: dict[str, PromptConfig] = {}
        self._logger = get_backend_logger("state.prompt_factory")

    def _prompts_dir(self) -> Path:
        return self._data_dir / "prompts"

    def _file_path(self, prompt_id: str) -> Path:
        return self._prompts_dir() / f"{_safe_filename(prompt_id)}.json"

    def _save_file(self, config: PromptConfig):
        self._file_path(config.id).write_text(
            config.model_dump_json(indent=2), encoding="utf-8",
        )

    def _delete_file(self, prompt_id: str):
        p = self._file_path(prompt_id)
        if p.exists():
            p.unlink()

    # --- load ---

    def load(self):
        prompts_dir = self._prompts_dir()
        self._configs = {}
        for item in sorted(prompts_dir.iterdir()):
            if not item.is_file() or item.suffix != ".json":
                continue
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
                config = PromptConfig(**data)
                self._configs[config.id] = config
            except Exception as e:
                self._logger.warning(f"Failed to load prompt from {item}: {e}")

    # --- CRUD ---

    def get(self, prompt_id: str) -> PromptConfig | None:
        return self._configs.get(prompt_id)

    def list_all(self) -> list[PromptConfig]:
        return list(self._configs.values())

    def add(self, config: PromptConfig) -> PromptConfig:
        if not config.id:
            config = config.model_copy(update={"id": _next_id()})
        self._configs[config.id] = config
        self._save_file(config)
        return config

    def update(self, prompt_id: str, updates: dict) -> PromptConfig | None:
        config = self._configs.get(prompt_id)
        if not config:
            return None
        data = config.model_dump()
        data.update(updates)
        new_config = PromptConfig(**data)
        new_config.id = prompt_id  # id is immutable
        self._configs[prompt_id] = new_config
        self._save_file(new_config)
        return new_config

    def delete(self, prompt_id: str) -> bool:
        if self._configs.pop(prompt_id, None) is None:
            return False
        self._delete_file(prompt_id)
        return True
