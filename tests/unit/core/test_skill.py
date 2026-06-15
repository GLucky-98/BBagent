from bbagent.core.skill import scan_skills


def make_skill(skill_dir, name, description="A useful skill."):
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f"description: {description}",
                "---",
                "",
                "Use this skill.",
            ]
        ),
        encoding="utf-8",
    )


def test_scan_skills_includes_selected_directory_skill_md(tmp_path):
    make_skill(tmp_path, "Root Skill")

    skills = scan_skills(tmp_path)

    assert list(skills) == ["Root Skill"]
    assert skills["Root Skill"].path == tmp_path


def test_scan_skills_includes_root_and_child_skill_dirs(tmp_path):
    make_skill(tmp_path, "Root Skill")
    make_skill(tmp_path / "child", "Child Skill")

    skills = scan_skills(tmp_path)

    assert set(skills) == {"Root Skill", "Child Skill"}
    assert skills["Root Skill"].path == tmp_path
    assert skills["Child Skill"].path == tmp_path / "child"


def test_scan_skills_imports_selected_skill_md_file(tmp_path):
    make_skill(tmp_path, "Single File Skill")

    skills = scan_skills(tmp_path / "SKILL.md")

    assert list(skills) == ["Single File Skill"]
    assert skills["Single File Skill"].path == tmp_path
