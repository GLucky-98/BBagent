#!/usr/bin/env python3
"""
test_grep_tool.py - Grep tool tests

Test for BBagent.built_in_tool.grep module.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BBAGENT_PKG = PROJECT_ROOT / "BBagent"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BBAGENT_PKG))

from BBagent.built_in_tool.grep import create_grep_tool


def test_grep_tool_creation():
    """Test Grep tool creation."""
    print("[TEST] test_grep_tool_creation")
    try:
        tool = create_grep_tool()
        assert tool is not None
        assert tool.name == "Grep"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_grep_basic_search():
    """Test basic text search."""
    print("[TEST] test_grep_basic_search")
    try:
        test_file = Path(__file__).parent.parent / "temp" / "test_grep.txt"
        test_file.write_text("Hello World\nThis is a test\nAnother line with World")

        tool = create_grep_tool()
        result = tool.invoke({"path": str(test_file), "pattern": "World"})

        assert "World" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_grep_regex():
    """Test regex pattern search."""
    print("[TEST] test_grep_regex")
    try:
        test_file = Path(__file__).parent.parent / "temp" / "test_grep_regex.txt"
        test_file.write_text("abc123\ndef456\nghi789")

        tool = create_grep_tool()
        result = tool.invoke({"path": str(test_file), "pattern": r"\d+"})

        assert "123" in result
        assert "456" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_grep_no_match():
    """Test search with no matches."""
    print("[TEST] test_grep_no_match")
    try:
        test_file = Path(__file__).parent.parent / "temp" / "test_grep_nomatch.txt"
        test_file.write_text("Hello World")

        tool = create_grep_tool()
        result = tool.invoke({"path": str(test_file), "pattern": "NonExistent"})

        assert result is not None
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_grep_nonexistent_file():
    """Test grep on nonexistent file."""
    print("[TEST] test_grep_nonexistent_file")
    try:
        tool = create_grep_tool()
        result = tool.invoke({"path": "/nonexistent/file.txt", "pattern": "test"})

        assert "Error" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_grep_tool_creation,
        test_grep_basic_search,
        test_grep_regex,
        test_grep_no_match,
        test_grep_nonexistent_file,
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