import json

from backend.factories import _skill_id
from backend.factories.skill_factory import SkillFactory
from backend.schemas import SkillConfig


def make_skill(skill_dir, name="Example Skill", description="Use an example skill."):
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f"description: {description}",
                "---",
                "",
                "Do the thing.",
            ]
        ),
        encoding="utf-8",
    )


def add_skill_config(factory, data_dir, skill_dir):
    skill_id = _skill_id(str(skill_dir.resolve()))
    config = SkillConfig(
        id=skill_id,
        name="Example Skill",
        description="Use an example skill.",
        path=str(skill_dir.resolve()),
    )
    skills_dir = data_dir / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / f"{skill_id}.json").write_text(
        config.model_dump_json(indent=2),
        encoding="utf-8",
    )
    factory.load()
    return skill_id


def test_refresh_deletes_config_when_skill_directory_is_missing(tmp_path):
    data_dir = tmp_path / "data"
    skill_dir = tmp_path / "source" / "example"
    make_skill(skill_dir)
    factory = SkillFactory(data_dir)
    skill_id = add_skill_config(factory, data_dir, skill_dir)

    (skill_dir / "SKILL.md").unlink()
    skill_dir.rmdir()

    assert factory.refresh(skill_id) is None
    assert factory.get(skill_id) is None
    assert not (data_dir / "skills" / f"{skill_id}.json").exists()


def test_refresh_deletes_config_when_skill_md_is_missing(tmp_path):
    data_dir = tmp_path / "data"
    skill_dir = tmp_path / "source" / "example"
    make_skill(skill_dir)
    factory = SkillFactory(data_dir)
    skill_id = add_skill_config(factory, data_dir, skill_dir)

    (skill_dir / "SKILL.md").unlink()

    assert factory.refresh(skill_id) is None
    assert factory.get(skill_id) is None
    assert not (data_dir / "skills" / f"{skill_id}.json").exists()


def test_refresh_updates_config_when_skill_source_exists(tmp_path):
    data_dir = tmp_path / "data"
    skill_dir = tmp_path / "source" / "example"
    make_skill(skill_dir)
    factory = SkillFactory(data_dir)
    skill_id = add_skill_config(factory, data_dir, skill_dir)

    make_skill(skill_dir, name="Updated Skill", description="Updated description.")

    refreshed = factory.refresh(skill_id)

    assert refreshed is not None
    assert refreshed.name == "Updated Skill"
    assert refreshed.description == "Updated description."
    saved = json.loads((data_dir / "skills" / f"{skill_id}.json").read_text(encoding="utf-8"))
    assert saved["name"] == "Updated Skill"


def test_import_dir_imports_skill_md_from_selected_directory(tmp_path):
    data_dir = tmp_path / "data"
    skill_dir = tmp_path / "source" / "example"
    make_skill(skill_dir, name="Root Skill")
    factory = SkillFactory(data_dir)

    added, skipped = factory.import_dir(skill_dir)

    assert skipped == []
    assert len(added) == 1
    assert added[0].name == "Root Skill"
    assert added[0].path == str(skill_dir.resolve())


def test_import_dir_imports_selected_skill_md_file(tmp_path):
    data_dir = tmp_path / "data"
    skill_dir = tmp_path / "source" / "example"
    make_skill(skill_dir, name="Single File Skill")
    factory = SkillFactory(data_dir)

    added, skipped = factory.import_dir(skill_dir / "SKILL.md")

    assert skipped == []
    assert len(added) == 1
    assert added[0].name == "Single File Skill"
    assert added[0].path == str(skill_dir.resolve())
