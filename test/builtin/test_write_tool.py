#!/usr/bin/env python3
"""
test_write_tool.py - Write tool tests

Test for BBagent.built_in_tool.write module.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BBAGENT_PKG = PROJECT_ROOT / "BBagent"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BBAGENT_PKG))

from BBagent.built_in_tool.write import create_write_tool


def test_write_tool_creation():
    """Test Write tool creation."""
    print("[TEST] test_write_tool_creation")
    try:
        tool = create_write_tool()
        assert tool is not None
        assert tool.name == "Write"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_write_tool_create_file():
    """Test creating a new file with write tool."""
    print("[TEST] test_write_tool_create_file")
    try:
        test_file = Path(__file__).parent.parent / "temp" / "test_write_new.txt"

        tool = create_write_tool()
        result = tool.invoke({"path": str(test_file), "content": "Hello, World!"})

        assert test_file.exists()
        assert test_file.read_text() == "Hello, World!"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_write_tool_overwrite_file():
    """Test overwriting an existing file."""
    print("[TEST] test_write_tool_overwrite_file")
    try:
        test_file = Path(__file__).parent.parent / "temp" / "test_write_overwrite.txt"
        test_file.write_text("Original content")

        tool = create_write_tool()
        result = tool.invoke({"path": str(test_file), "content": "New content"})

        assert test_file.read_text() == "New content"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_write_tool_create_directory():
    """Test creating directory when writing file."""
    print("[TEST] test_write_tool_create_directory")
    try:
        test_file = Path(__file__).parent.parent / "temp" / "subdir" / "nested" / "test.txt"

        tool = create_write_tool()
        result = tool.invoke({"path": str(test_file), "content": "Nested content"})

        assert test_file.exists()
        assert test_file.read_text() == "Nested content"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_write_tool_creation,
        test_write_tool_create_file,
        test_write_tool_overwrite_file,
        test_write_tool_create_directory,
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