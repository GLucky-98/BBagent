"""Baseline tests for ModelFactory — CRUD, persistence, refcounting."""

import pytest

from backend.factories.model_factory import ModelFactory
from backend.schemas import ModelConfig
from backend.errors import NotFoundError


def _ensure_dir(data_dir):
    (data_dir / "models").mkdir(parents=True, exist_ok=True)


def make_config(**overrides):
    return ModelConfig(
        id=overrides.get("id", ""),
        name=overrides.get("name", "Test Model"),
        provider=overrides.get("provider", "anthropic"),
        modelName=overrides.get("modelName", "claude-sonnet-4-20250514"),
        apiKey=overrides.get("apiKey", "sk-test"),
        baseUrl=overrides.get("baseUrl", "https://api.anthropic.com"),
        maxContextTokens=overrides.get("maxContextTokens", 200000),
        maxCompletionTokens=overrides.get("maxCompletionTokens", 4096),
    )


def test_add_generates_id_and_persists_to_disk(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)
    config = make_config()
    result = factory.add(config)

    assert result.id
    assert result.id != ""
    assert factory.get(result.id) is not None
    assert (tmp_path / "models" / f"{result.id}.json").exists()


def test_add_preserves_provided_id(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)
    config = make_config(id="custom-id")
    result = factory.add(config)

    assert result.id == "custom-id"
    assert factory.get("custom-id") is not None


def test_list_all_returns_persisted_configs(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)

    factory.add(make_config(name="Model A"))
    factory.add(make_config(name="Model B"))

    all_models = factory.list_all()

    assert len(all_models) == 2
    names = {m.name for m in all_models}
    assert names == {"Model A", "Model B"}


def test_update_modifies_fields_and_persists(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)
    config = make_config(name="Original")
    result = factory.add(config)

    updated = factory.update(result.id, {"name": "Updated", "temperature": 0.5})

    assert updated.name == "Updated"
    assert updated.temperature == 0.5
    assert updated.id == result.id
    assert factory.get(result.id).name == "Updated"


def test_update_with_new_id_moves_file(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)
    config = make_config(name="Old")
    result = factory.add(config)
    old_path = tmp_path / "models" / f"{result.id}.json"

    updated = factory.update(result.id, {"id": "new-id"})

    assert updated.id == "new-id"
    assert factory.get("new-id") is not None
    assert not old_path.exists()
    assert (tmp_path / "models" / "new-id.json").exists()


def test_delete_removes_from_registry_and_disk(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)
    config = factory.add(make_config())

    deleted = factory.delete(config.id)

    assert deleted is True
    assert factory.get(config.id) is None
    assert not (tmp_path / "models" / f"{config.id}.json").exists()


def test_delete_nonexistent_returns_false(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)

    assert factory.delete("nonexistent") is False


def test_acquire_creates_and_caches_model_instance(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)
    config = factory.add(make_config())

    instance1 = factory.acquire(config.id)
    instance2 = factory.acquire(config.id)

    assert instance1 is instance2
    assert factory._refcount[config.id] == 2


def test_acquire_raises_not_found_for_unknown_id(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)

    with pytest.raises(NotFoundError):
        factory.acquire("unknown-id")


def test_acquire_submodel_allows_missing(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)

    result = factory.acquire_submodel("nonexistent")

    assert result is None


def test_acquire_raises_value_error_for_empty_id(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)

    with pytest.raises(ValueError, match="empty"):
        factory.acquire("")


@pytest.mark.asyncio
async def test_release_decrements_refcount(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)
    config = factory.add(make_config())

    factory.acquire(config.id)
    factory.acquire(config.id)
    await factory.release(config.id)

    assert factory._refcount[config.id] == 1


@pytest.mark.asyncio
async def test_release_to_zero_removes_instance_from_cache(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)
    config = factory.add(make_config())

    factory.acquire(config.id)
    await factory.release(config.id)

    assert config.id not in factory._instances
    assert config.id not in factory._refcount


@pytest.mark.asyncio
async def test_invalidate_force_removes_cached_instance(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)
    config = factory.add(make_config())
    factory.acquire(config.id)

    await factory.invalidate(config.id)

    assert config.id not in factory._instances
    assert config.id not in factory._refcount


@pytest.mark.asyncio
async def test_release_idempotent_for_unknown_id(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)

    await factory.release("nonexistent")


def test_load_restores_persisted_configs(tmp_path):
    _ensure_dir(tmp_path)
    factory = ModelFactory(tmp_path)
    factory.add(make_config(name="Model 1"))
    factory.add(make_config(name="Model 2"))

    factory2 = ModelFactory(tmp_path)
    factory2.load()

    assert len(factory2.list_all()) == 2
    names = {m.name for m in factory2.list_all()}
    assert names == {"Model 1", "Model 2"}
