#!/usr/bin/env python3
"""
test_edit_tool.py - Edit tool tests

Test for BBagent.built_in_tool.edit module.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BBAGENT_PKG = PROJECT_ROOT / "BBagent"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BBAGENT_PKG))

from BBagent.built_in_tool.edit import create_edit_tool


def test_edit_tool_creation():
    """Test Edit tool creation."""
    print("[TEST] test_edit_tool_creation")
    try:
        tool = create_edit_tool()
        assert tool is not None
        assert tool.name == "Edit"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_edit_tool_single_replacement():
    """Test single text replacement."""
    print("[TEST] test_edit_tool_single_replacement")
    try:
        test_file = Path(__file__).parent.parent / "temp" / "test_edit.txt"
        test_file.write_text("Hello, World!")

        tool = create_edit_tool()
        result = tool.invoke({"path": str(test_file), "old_string": "World", "new_string": "BBagent"})

        assert "BBagent" in test_file.read_text()
        assert "World" not in test_file.read_text()
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_edit_tool_multiline():
    """Test multiline replacement."""
    print("[TEST] test_edit_tool_multiline")
    try:
        test_file = Path(__file__).parent.parent / "temp" / "test_edit_multiline.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3\n")

        tool = create_edit_tool()
        result = tool.invoke({
            "path": str(test_file),
            "old_string": "Line 2",
            "new_string": "Modified Line 2"
        })

        content = test_file.read_text()
        assert "Modified Line 2" in content
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_edit_tool_no_match():
    """Test edit with no matching text."""
    print("[TEST] test_edit_tool_no_match")
    try:
        test_file = Path(__file__).parent.parent / "temp" / "test_edit_nomatch.txt"
        test_file.write_text("Hello, World!")

        tool = create_edit_tool()
        result = tool.invoke({"path": str(test_file), "old_string": "NonExistent", "new_string": "Test"})

        assert "Error" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_edit_tool_nonexistent_file():
    """Test edit on nonexistent file."""
    print("[TEST] test_edit_tool_nonexistent_file")
    try:
        tool = create_edit_tool()
        result = tool.invoke({"path": "/nonexistent/file.txt", "old_string": "a", "new_string": "b"})

        assert "Error" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_edit_tool_creation,
        test_edit_tool_single_replacement,
        test_edit_tool_multiline,
        test_edit_tool_no_match,
        test_edit_tool_nonexistent_file,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[ERROR] {test.__name__}: {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)