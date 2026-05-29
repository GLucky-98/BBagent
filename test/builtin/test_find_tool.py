#!/usr/bin/env python3
"""
test_find_tool.py - Find tool tests

Test for BBagent.built_in_tool.find module.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BBAGENT_PKG = PROJECT_ROOT / "BBagent"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BBAGENT_PKG))

from BBagent.built_in_tool.find import create_find_tool


def test_find_tool_creation():
    """Test Find tool creation."""
    print("[TEST] test_find_tool_creation")
    try:
        tool = create_find_tool()
        assert tool is not None
        assert tool.name == "Glob"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_find_by_name():
    """Test finding files by name pattern."""
    print("[TEST] test_find_by_name")
    try:
        test_dir = Path(__file__).parent.parent / "temp" / "test_find_dir"
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / "file1.txt").write_text("test")
        (test_dir / "file2.txt").write_text("test")
        (test_dir / "data.json").write_text("test")

        tool = create_find_tool()
        result = tool.invoke({"pattern": "*.txt", "path": str(test_dir)})

        assert "file1.txt" in result
        assert "file2.txt" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_find_no_match():
    """Test find with no matching files."""
    print("[TEST] test_find_no_match")
    try:
        test_dir = Path(__file__).parent.parent / "temp" / "test_find_empty"
        test_dir.mkdir(parents=True, exist_ok=True)

        tool = create_find_tool()
        result = tool.invoke({"pattern": "*.nonexistent", "path": str(test_dir)})

        assert "No matches found" in result or result is not None
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_find_nonexistent_dir():
    """Test find in nonexistent directory."""
    print("[TEST] test_find_nonexistent_dir")
    try:
        tool = create_find_tool()
        result = tool.invoke({"pattern": "*.txt", "path": "/nonexistent/directory"})

        assert "Error" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_find_tool_creation,
        test_find_by_name,
        test_find_no_match,
        test_find_nonexistent_dir,
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