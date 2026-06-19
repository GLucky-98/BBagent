"""Baseline tests for PromptFactory — CRUD and persistence."""

from backend.factories.prompt_factory import PromptFactory
from backend.schemas import PromptConfig


def _ensure_dir(data_dir):
    (data_dir / "prompts").mkdir(parents=True, exist_ok=True)


def make_config(**overrides):
    return PromptConfig(
        id=overrides.get("id", ""),
        name=overrides.get("name", "Test Prompt"),
        content=overrides.get("content", "You are a helpful assistant."),
        group=overrides.get("group", ""),
    )


def test_add_generates_id_and_persists(tmp_path):
    _ensure_dir(tmp_path)
    factory = PromptFactory(tmp_path)
    config = make_config()
    result = factory.add(config)

    assert result.id
    assert factory.get(result.id) is not None
    assert (tmp_path / "prompts" / f"{result.id}.json").exists()


def test_add_preserves_provided_id(tmp_path):
    _ensure_dir(tmp_path)
    factory = PromptFactory(tmp_path)
    config = make_config(id="prompt-1")

    result = factory.add(config)

    assert result.id == "prompt-1"
    assert factory.get("prompt-1").name == "Test Prompt"


def test_list_all_returns_added_prompts(tmp_path):
    _ensure_dir(tmp_path)
    factory = PromptFactory(tmp_path)

    factory.add(make_config(name="Prompt A"))
    factory.add(make_config(name="Prompt B"))

    all_prompts = factory.list_all()
    assert len(all_prompts) == 2
    assert {p.name for p in all_prompts} == {"Prompt A", "Prompt B"}


def test_update_modifies_content(tmp_path):
    _ensure_dir(tmp_path)
    factory = PromptFactory(tmp_path)
    config = factory.add(make_config(content="Original content"))

    updated = factory.update(config.id, {"content": "Updated content", "name": "Renamed"})

    assert updated.content == "Updated content"
    assert updated.name == "Renamed"
    assert updated.id == config.id
    assert factory.get(config.id).content == "Updated content"


def test_update_nonexistent_returns_none(tmp_path):
    _ensure_dir(tmp_path)
    factory = PromptFactory(tmp_path)

    assert factory.update("no-such-id", {"name": "X"}) is None


def test_delete_removes_from_registry_and_disk(tmp_path):
    _ensure_dir(tmp_path)
    factory = PromptFactory(tmp_path)
    config = factory.add(make_config())

    deleted = factory.delete(config.id)

    assert deleted is True
    assert factory.get(config.id) is None
    assert not (tmp_path / "prompts" / f"{config.id}.json").exists()


def test_delete_nonexistent_returns_false(tmp_path):
    _ensure_dir(tmp_path)
    factory = PromptFactory(tmp_path)

    assert factory.delete("no-id") is False


def test_load_restores_persisted_prompts(tmp_path):
    _ensure_dir(tmp_path)
    factory = PromptFactory(tmp_path)
    factory.add(make_config(name="Prompt 1"))
    factory.add(make_config(name="Prompt 2"))

    factory2 = PromptFactory(tmp_path)
    factory2.load()

    assert len(factory2.list_all()) == 2
    assert {p.name for p in factory2.list_all()} == {"Prompt 1", "Prompt 2"}
