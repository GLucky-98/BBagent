"""ModelFactory — manages ModelConfig CRUD, Model instance cache and refcount."""

import json
from pathlib import Path
from typing import Optional

from bbagent.core.model import Model

from backend.schemas import ModelConfig
from backend.errors import NotFoundError, ErrorCode
from backend.factories import _next_id, _safe_filename
from backend.logging import get_backend_logger


class ModelFactory:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._configs: dict[str, ModelConfig] = {}   # model_id -> ModelConfig
        self._instances: dict[str, Model] = {}        # model_id -> Model (shared cache)
        self._refcount: dict[str, int] = {}           # model_id -> ref count
        self._logger = get_backend_logger("state.model_factory")

    # --- path helpers ---

    def _models_dir(self) -> Path:
        return self._data_dir / "models"

    def _file_path(self, model_id: str) -> Path:
        return self._models_dir() / f"{_safe_filename(model_id)}.json"

    def _save_file(self, config: ModelConfig):
        self._file_path(config.id).write_text(
            config.model_dump_json(indent=2), encoding="utf-8",
        )

    def _delete_file(self, model_id: str):
        p = self._file_path(model_id)
        if p.exists():
            p.unlink()

    # --- load ---

    def load(self):
        models_dir = self._models_dir()
        self._configs = {}
        for item in sorted(models_dir.iterdir()):
            if not item.is_file() or item.suffix != ".json":
                continue
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
                config = ModelConfig(**data)
                self._configs[config.id] = config
            except Exception as e:
                self._logger.warning(f"Failed to load model from {item}: {e}")

    # --- CRUD ---

    def get(self, model_id: str) -> Optional[ModelConfig]:
        return self._configs.get(model_id)

    def list_all(self) -> list[ModelConfig]:
        return list(self._configs.values())

    def add(self, config: ModelConfig) -> ModelConfig:
        if not config.id:
            config = config.model_copy(update={"id": _next_id()})
        self._configs[config.id] = config
        self._save_file(config)
        return config

    def update(self, model_id: str, updates: dict) -> Optional[ModelConfig]:
        config = self._configs.get(model_id)
        if not config:
            return None
        old_id = config.id
        data = config.model_dump()
        data.update(updates)
        new_config = ModelConfig(**data)
        if new_config.id != old_id:
            self._delete_file(old_id)
        self._configs[new_config.id] = new_config
        self._save_file(new_config)
        return new_config

    def delete(self, model_id: str) -> bool:
        if model_id not in self._configs:
            return False
        self._configs.pop(model_id)
        self._delete_file(model_id)
        return True

    # --- Model instance cache ---

    def acquire(self, model_id: str, allow_missing: bool = False) -> Optional[Model]:
        """Resolve a ModelConfig.id to a shared Model instance (refcount++)."""
        if not model_id or not model_id.strip():
            if allow_missing:
                return None
            raise ValueError("model_id is empty")
        mid = model_id.strip()
        cached = self._instances.get(mid)
        if cached is not None:
            self._refcount[mid] = self._refcount.get(mid, 0) + 1
            return cached
        config = self._configs.get(mid)
        if not config:
            if allow_missing:
                self._logger.warning(f"modelId '{mid}' not found, returning None")
                return None
            raise NotFoundError(ErrorCode.MODEL_NOT_FOUND, f"Model '{mid}' not found")
        model = Model.from_config_dict(config.core_dict)
        self._instances[mid] = model
        self._refcount[mid] = 1
        return model

    def acquire_submodel(self, submodel_id: str) -> Optional[Model]:
        return self.acquire(submodel_id, allow_missing=True)

    async def release(self, model_id: str) -> None:
        """Decrement refcount; when 0, aclose() and remove from cache."""
        if not model_id or model_id not in self._instances:
            return
        self._refcount[model_id] = max(0, self._refcount.get(model_id, 1) - 1)
        if self._refcount[model_id] == 0:
            model = self._instances.pop(model_id)
            self._refcount.pop(model_id, None)
            try:
                await model.aclose()
            except Exception as e:
                self._logger.warning(f"Model '{model_id}' aclose failed: {e}")

    async def invalidate(self, model_id: str) -> None:
        """Force-invalidate cached Model instance.

        The caller (State) is responsible for determining which agents
        are affected by checking agent_factory._model_ids.
        """
        if not model_id:
            return
        if model_id in self._instances:
            model = self._instances.pop(model_id)
            self._refcount.pop(model_id, None)
            try:
                await model.aclose()
            except Exception as e:
                self._logger.warning(f"Model '{model_id}' aclose failed: {e}")
