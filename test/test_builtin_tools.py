import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from BBagent.built_in_tool.read import create_read_tool, DEFAULT_MAX_BYTES, DEFAULT_MAX_LINES
from BBagent.built_in_tool.write import create_write_tool
from BBagent.built_in_tool.edit import create_edit_tool
from BBagent.built_in_tool.grep import create_grep_tool
from BBagent.built_in_tool.find import create_find_tool
from BBagent.built_in_tool.ls import create_ls_tool
from BBagent.built_in_tool.policy import Policy


def make_temp_dir():
    return tempfile.mkdtemp(prefix="gl_test_")


def make_temp_file(tmp_dir, name, content):
    path = os.path.join(tmp_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_read_basic():
    tmp = make_temp_dir()
    try:
        path = make_temp_file(tmp, "hello.txt", "line1\nline2\nline3\n")
        tool = create_read_tool(Policy(cwd=tmp))
        result = tool.invoke({"path": "hello.txt"})

        assert "line1" in result
        assert "line2" in result
        assert "line3" in result
        assert "Lines: 3/3" in result
        print("[PASS] test_read_basic")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_read_offset():
    tmp = make_temp_dir()
    try:
        make_temp_file(tmp, "nums.txt", "1\n2\n3\n4\n5\n")
        tool = create_read_tool(Policy(cwd=tmp))
        result = tool.invoke({"path": "nums.txt", "offset": 3})

        assert "Lines: 3/5" in result
        assert "3" in result
        assert "4" in result
        assert "5" in result
        print("[PASS] test_read_offset")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_read_limit():
    tmp = make_temp_dir()
    try:
        make_temp_file(tmp, "nums.txt", "1\n2\n3\n4\n5\n")
        tool = create_read_tool(Policy(cwd=tmp))
        result = tool.invoke({"path": "nums.txt", "limit": 2})

        assert "Lines: 2/5" in result
        assert "1" in result
        assert "2" in result
        print("[PASS] test_read_limit")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_read_offset_and_limit():
    tmp = make_temp_dir()
    try:
        make_temp_file(tmp, "nums.txt", "1\n2\n3\n4\n5\n")
        tool = create_read_tool(Policy(cwd=tmp))
        result = tool.invoke({"path": "nums.txt", "offset": 2, "limit": 2})

        assert "Lines: 2/5" in result
        assert "2" in result
        assert "3" in result
        print("[PASS] test_read_offset_and_limit")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_read_empty_path():
    tool = create_read_tool()
    result = tool.invoke({"path": ""})
    assert result.startswith("Error: path is required")
    print("[PASS] test_read_empty_path")


def test_read_file_not_found():
    tool = create_read_tool(Policy(cwd="/tmp"))
    result = tool.invoke({"path": "nonexistent_file_xyz_123.txt"})
    assert "Error" in result
    print("[PASS] test_read_file_not_found")


def test_read_byte_truncation_with_utf8():
    tmp = make_temp_dir()
    try:
        chinese_line = "你好世界" * 500
        make_temp_file(tmp, "chinese.txt", chinese_line)
        tool = create_read_tool(Policy(cwd=tmp, max_read_size=2000, max_read_lines=DEFAULT_MAX_LINES))
        result = tool.invoke({"path": "chinese.txt"})

        footer_line = [l for l in result.split("\n") if l.startswith("[File:")]
        assert footer_line, "should contain file info footer"
        assert "[truncated: bytes]" in result
        print("[PASS] test_read_byte_truncation_with_utf8")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_read_byte_truncation_no_overlap_with_line_truncation():
    tmp = make_temp_dir()
    try:
        lines = ["line " + str(i) for i in range(100)]
        make_temp_file(tmp, "many.txt", "\n".join(lines))
        tool = create_read_tool(Policy(cwd=tmp, max_read_size=10_000, max_read_lines=10))
        result = tool.invoke({"path": "many.txt"})

        assert "[truncated: lines]" in result
        assert "Lines: 10/100" in result
        print("[PASS] test_read_byte_truncation_no_overlap_with_line_truncation")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_read_absolute_path():
    tmp = make_temp_dir()
    try:
        path = make_temp_file(tmp, "abs.txt", "hello world\n")
        tool = create_read_tool(Policy(cwd="/some/other/dir"))
        result = tool.invoke({"path": path})

        assert "hello world" in result
        print("[PASS] test_read_absolute_path")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_write_basic():
    tmp = make_temp_dir()
    try:
        tool = create_write_tool(Policy(cwd=tmp))
        result = tool.invoke({"path": "test.txt", "content": "hello world\n"})
        assert "Wrote" in result
        assert os.path.exists(os.path.join(tmp, "test.txt"))
        with open(os.path.join(tmp, "test.txt"), "r") as f:
            assert f.read() == "hello world\n"
        print("[PASS] test_write_basic")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_write_empty_path():
    tool = create_write_tool()
    result = tool.invoke({"path": "", "content": "x"})
    assert "Error: path is required" in result
    print("[PASS] test_write_empty_path")


def test_write_creates_directories():
    tmp = make_temp_dir()
    try:
        tool = create_write_tool(Policy(cwd=tmp, write_create_directories=True))
        result = tool.invoke({"path": "sub/dir/deep/file.txt", "content": "nested\n"})
        assert "Wrote" in result
        assert os.path.exists(os.path.join(tmp, "sub/dir/deep/file.txt"))
        print("[PASS] test_write_creates_directories")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_write_overwrite():
    tmp = make_temp_dir()
    try:
        tool = create_write_tool(Policy(cwd=tmp))
        tool.invoke({"path": "over.txt", "content": "first\n"})
        result = tool.invoke({"path": "over.txt", "content": "second\n"})
        assert "Wrote" in result
        with open(os.path.join(tmp, "over.txt"), "r") as f:
            assert f.read() == "second\n"
        print("[PASS] test_write_overwrite")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_write_absolute_path():
    tmp = make_temp_dir()
    try:
        abs_path = os.path.join(tmp, "abs_write.txt")
        tool = create_write_tool(Policy(cwd="/unrelated"))
        result = tool.invoke({"path": abs_path, "content": "absolute\n"})
        assert "Wrote" in result
        assert os.path.exists(abs_path)
        print("[PASS] test_write_absolute_path")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_write_no_create_directories():
    tmp = make_temp_dir()
    try:
        tool = create_write_tool(Policy(cwd=tmp, write_create_directories=False))
        result = tool.invoke({"path": "nonexistent/file.txt", "content": "test\n"})
        assert "Error" in result
        print("[PASS] test_write_no_create_directories")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_write_line_count():
    tmp = make_temp_dir()
    try:
        tool = create_write_tool(Policy(cwd=tmp))
        result = tool.invoke({"path": "lines.txt", "content": "a\nb\nc"})
        assert "3 lines" in result
        print("[PASS] test_write_line_count")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_edit_basic():
    tmp = make_temp_dir()
    try:
        make_temp_file(tmp, "edit.txt", "hello world\n")
        tool = create_edit_tool(Policy(cwd=tmp))
        result = tool.invoke({"path": "edit.txt", "old_string": "hello", "new_string": "hi"})

        assert "Applied edit" in result
        with open(os.path.join(tmp, "edit.txt"), "r") as f:
            assert f.read() == "hi world\n"
        print("[PASS] test_edit_basic")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_edit_empty_path():
    tool = create_edit_tool()
    result = tool.invoke({"path": "", "old_string": "a", "new_string": "b"})
    assert "Error: path is required" in result
    print("[PASS] test_edit_empty_path")


def test_edit_empty_old_string():
    tool = create_edit_tool()
    result = tool.invoke({"path": "x", "old_string": "", "new_string": "b"})
    assert "Error: old_string is required" in result
    print("[PASS] test_edit_empty_old_string")


def test_edit_file_not_found():
    tool = create_edit_tool(Policy(cwd="/tmp"))
    result = tool.invoke({"path": "nosuchfile_999.txt", "old_string": "a", "new_string": "b"})
    assert "File not found" in result
    print("[PASS] test_edit_file_not_found")


def test_edit_old_string_not_found():
    tmp = make_temp_dir()
    try:
        make_temp_file(tmp, "edit2.txt", "some content\n")
        tool = create_edit_tool(Policy(cwd=tmp))
        result = tool.invoke({"path": "edit2.txt", "old_string": "zzz", "new_string": "yyy"})

        assert "old_string not found" in result
        print("[PASS] test_edit_old_string_not_found")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_edit_multiple_occurrences_without_partial():
    tmp = make_temp_dir()
    try:
        make_temp_file(tmp, "edit3.txt", "dup dup dup\n")
        tool = create_edit_tool(Policy(cwd=tmp))
        result = tool.invoke({"path": "edit3.txt", "old_string": "dup", "new_string": "fix"})

        assert "appears 3 times" in result
        with open(os.path.join(tmp, "edit3.txt"), "r") as f:
            assert f.read() == "dup dup dup\n"
        print("[PASS] test_edit_multiple_occurrences_without_partial")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_edit_partial_match():
    tmp = make_temp_dir()
    try:
        make_temp_file(tmp, "edit4.txt", "dup dup dup\n")
        tool = create_edit_tool(Policy(cwd=tmp))
        result = tool.invoke({"path": "edit4.txt", "old_string": "dup", "new_string": "fix", "partial_match": True})

        assert "Applied edit" in result
        with open(os.path.join(tmp, "edit4.txt"), "r") as f:
            assert f.read() == "fix dup dup\n"
        print("[PASS] test_edit_partial_match")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_edit_no_change():
    tmp = make_temp_dir()
    try:
        make_temp_file(tmp, "edit5.txt", "same\n")
        tool = create_edit_tool(Policy(cwd=tmp))
        result = tool.invoke({"path": "edit5.txt", "old_string": "same", "new_string": "same"})

        assert "No changes made" in result
        print("[PASS] test_edit_no_change")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_edit_absolute_path():
    tmp = make_temp_dir()
    try:
        abs_path = make_temp_file(tmp, "abs_edit.txt", "absolute path edit\n")
        tool = create_edit_tool(Policy(cwd="/unrelated"))
        result = tool.invoke({"path": abs_path, "old_string": "absolute", "new_string": "ABSOLUTE"})

        assert "Applied edit" in result
        with open(abs_path, "r") as f:
            assert "ABSOLUTE" in f.read()
        print("[PASS] test_edit_absolute_path")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


async def _test_bash_basic():
    from BBagent.built_in_tool.bash import create_bash_tool
    tmp = make_temp_dir()
    try:
        tool = await create_bash_tool(Policy(cwd=tmp))
        result = await tool.async_invoke({"command": "echo hello"})
        assert "hello" in result
        assert "[stdout]" in result
        print("[PASS] test_bash_basic")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


async def _test_bash_stderr():
    from BBagent.built_in_tool.bash import create_bash_tool
    tmp = make_temp_dir()
    try:
        tool = await create_bash_tool(Policy(cwd=tmp))
        result = await tool.async_invoke({"command": "echo error >&2"})
        assert "[stderr]" in result
        assert "error" in result
        print("[PASS] test_bash_stderr")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


async def _test_bash_exit_code():
    from BBagent.built_in_tool.bash import create_bash_tool
    tmp = make_temp_dir()
    try:
        tool = await create_bash_tool(Policy(cwd=tmp))
        result = await tool.async_invoke({"command": "exit 42"})
        assert "[exit code: 42]" in result or "[exit code: -1]" in result
        print("[PASS] test_bash_exit_code")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


async def _test_bash_cwd():
    from BBagent.built_in_tool.bash import create_bash_tool
    tmp = make_temp_dir()
    try:
        tool = await create_bash_tool(Policy(cwd=tmp))
        result = await tool.async_invoke({"command": "pwd"})
        assert os.path.realpath(tmp) in result
        print("[PASS] test_bash_cwd")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


async def _test_bash_timeout():
    from BBagent.built_in_tool.bash import create_bash_tool
    tmp = make_temp_dir()
    try:
        tool = await create_bash_tool(Policy(cwd=tmp, bash_default_timeout=1))
        result = await tool.async_invoke({"command": "sleep 3"})
        assert "timed out" in result.lower()
        print("[PASS] test_bash_timeout")
    finally:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


async def _test_bash_cwd_not_exist():
    from BBagent.built_in_tool.bash import create_bash_tool
    tool = await create_bash_tool(Policy(cwd="/nonexistent_path_xyz_123"))
    result = await tool.async_invoke({"command": "echo x"})
    assert "does not exist" in result
    print("[PASS] test_bash_cwd_not_exist")


def test_bash():
    async def run_all():
        await _test_bash_basic()
        await _test_bash_stderr()
        await _test_bash_exit_code()
        await _test_bash_cwd()
        await _test_bash_timeout()
        await _test_bash_cwd_not_exist()
    asyncio.run(run_all())
