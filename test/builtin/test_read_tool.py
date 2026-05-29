#!/usr/bin/env python3
"""
test_read_tool.py - Read tool tests

Test for BBagent.built_in_tool.read module.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BBAGENT_PKG = PROJECT_ROOT / "BBagent"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BBAGENT_PKG))

from BBagent.built_in_tool.read import create_read_tool


def test_read_tool_creation():
    """Test Read tool creation."""
    print("[TEST] test_read_tool_creation")
    try:
        tool = create_read_tool()
        assert tool is not None
        assert tool.name == "Read"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_read_tool_basic_file():
    """Test reading a basic file."""
    print("[TEST] test_read_tool_basic_file")
    try:
        test_file = Path(__file__).parent.parent / "temp" / "test_read.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Line 1\nLine 2\nLine 3\n")

        tool = create_read_tool()
        result = tool.invoke({"path": str(test_file)})

        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_read_tool_with_offset():
    """Test reading file with offset."""
    print("[TEST] test_read_tool_with_offset")
    try:
        test_file = Path(__file__).parent.parent / "temp" / "test_read_offset.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")

        tool = create_read_tool()
        result = tool.invoke({"path": str(test_file), "offset": 3})

        assert "Line 3" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_read_tool_with_limit():
    """Test reading file with limit."""
    print("[TEST] test_read_tool_with_limit")
    try:
        test_file = Path(__file__).parent.parent / "temp" / "test_read_limit.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")

        tool = create_read_tool()
        result = tool.invoke({"path": str(test_file), "limit": 2})

        assert "Line 1" in result
        assert "Line 2" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_read_tool_nonexistent_file():
    """Test reading a nonexistent file."""
    print("[TEST] test_read_tool_nonexistent_file")
    try:
        tool = create_read_tool()
        result = tool.invoke({"path": "/nonexistent/file/path.txt"})

        assert "Error" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_read_tool_creation,
        test_read_tool_basic_file,
        test_read_tool_with_offset,
        test_read_tool_with_limit,
        test_read_tool_nonexistent_file,
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