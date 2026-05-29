#!/usr/bin/env python3
"""
test_ls_tool.py - ls tool tests

Test for BBagent.built_in_tool.ls module.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BBAGENT_PKG = PROJECT_ROOT / "BBagent"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BBAGENT_PKG))

from BBagent.built_in_tool.ls import create_ls_tool


def test_ls_tool_creation():
    """Test ls tool creation."""
    print("[TEST] test_ls_tool_creation")
    try:
        tool = create_ls_tool()
        assert tool is not None
        assert tool.name == "LS"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_ls_basic():
    """Test basic directory listing."""
    print("[TEST] test_ls_basic")
    try:
        test_dir = Path(__file__).parent.parent / "temp" / "test_ls_dir"
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / "file1.txt").write_text("test")
        (test_dir / "file2.txt").write_text("test")

        tool = create_ls_tool()
        result = tool.invoke({"path": str(test_dir)})

        assert "file1.txt" in result
        assert "file2.txt" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_ls_nonexistent_dir():
    """Test ls on nonexistent directory."""
    print("[TEST] test_ls_nonexistent_dir")
    try:
        tool = create_ls_tool()
        result = tool.invoke({"path": "/nonexistent/directory"})

        assert "Error" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_ls_tool_creation,
        test_ls_basic,
        test_ls_nonexistent_dir,
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