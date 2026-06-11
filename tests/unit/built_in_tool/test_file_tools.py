from bbagent.built_in_tool.edit import create_edit_tool
from bbagent.built_in_tool.find import create_find_tool
from bbagent.built_in_tool.grep import create_grep_tool
from bbagent.built_in_tool.ls import create_ls_tool
from bbagent.built_in_tool.policy import Policy
from bbagent.built_in_tool.read import create_read_tool
from bbagent.built_in_tool.write import create_write_tool


def test_write_and_read_round_trip_with_policy_cwd(tmp_path):
    policy = Policy(cwd=str(tmp_path))
    write = create_write_tool(policy)
    read = create_read_tool(policy)

    write_result = write.invoke({"path": "notes/todo.txt", "content": "one\ntwo\nthree"})
    read_result = read.invoke({"path": "notes/todo.txt", "offset": 2, "limit": 1})

    assert "Wrote 3 lines" in write_result
    assert (tmp_path / "notes" / "todo.txt").read_text(encoding="utf-8") == "one\ntwo\nthree"
    assert read_result.startswith("two")
    assert "Lines: 2-2/3" in read_result


def test_read_reports_binary_file(tmp_path):
    target = tmp_path / "blob.bin"
    target.write_bytes(b"\x00" * 128)

    result = create_read_tool(Policy(cwd=str(tmp_path))).invoke({"path": "blob.bin"})

    assert result.startswith("Error: File appears to be binary")


def test_edit_requires_unique_match_unless_partial_match_enabled(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text("same\nsame\n", encoding="utf-8")
    edit = create_edit_tool(Policy(cwd=str(tmp_path)))

    duplicate = edit.invoke({"path": "sample.txt", "old_string": "same", "new_string": "changed"})
    partial = edit.invoke(
        {
            "path": "sample.txt",
            "old_string": "same",
            "new_string": "changed",
            "partial_match": True,
        }
    )

    assert "appears 2 times" in duplicate
    assert partial.startswith("Applied edit")
    assert target.read_text(encoding="utf-8") == "changed\nsame\n"


def test_grep_supports_literal_case_insensitive_search_and_file_filter(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("Alpha\nbeta\n", encoding="utf-8")
    (tmp_path / "src" / "b.txt").write_text("alpha\n", encoding="utf-8")
    grep = create_grep_tool(Policy(cwd=str(tmp_path)))

    result = grep.invoke(
        {
            "pattern": "alpha",
            "path": "src",
            "case_sensitive": False,
            "is_regex": False,
            "file_pattern": "*.py",
        }
    )

    assert result == "a.py:1: Alpha"


def test_find_and_ls_return_expected_project_entries(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "module.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".hidden").write_text("secret", encoding="utf-8")
    policy = Policy(cwd=str(tmp_path))

    found = create_find_tool(policy).invoke({"pattern": "**/*.py"})
    listed = create_ls_tool(policy).invoke({"path": ".", "show_hidden": False})

    assert "pkg/__init__.py" in found
    assert "pkg/module.py" in found
    assert "[DIR]  pkg/" in listed
    assert ".hidden" not in listed
