#!/usr/bin/env python3
"""
test_bash_tool.py - Bash tool tests

Test for BBagent.built_in_tool.bash module.
"""
import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BBAGENT_PKG = PROJECT_ROOT / "BBagent"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BBAGENT_PKG))

from BBagent.built_in_tool.bash import create_bash_tool


async def test_bash_tool_creation():
    """Test Bash tool creation."""
    print("[TEST] test_bash_tool_creation")
    try:
        tool = await create_bash_tool()
        assert tool is not None
        assert tool.name == "Bash"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def test_bash_simple_command():
    """Test executing a simple command."""
    print("[TEST] test_bash_simple_command")
    try:
        tool = await create_bash_tool()
        result = await tool.async_invoke({"command": "echo 'Hello from bash'"})

        assert "Hello from bash" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def test_bash_pwd():
    """Test pwd command."""
    print("[TEST] test_bash_pwd")
    try:
        tool = await create_bash_tool()
        result = await tool.async_invoke({"command": "pwd"})

        assert len(result) > 0
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def test_bash_exit_code():
    """Test command with non-zero exit code."""
    print("[TEST] test_bash_exit_code")
    try:
        tool = await create_bash_tool()
        result = await tool.async_invoke({"command": "exit 1"})

        assert "exit code: 1" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def run_async_tests():
    tests = [
        test_bash_tool_creation,
        test_bash_simple_command,
        test_bash_pwd,
        test_bash_exit_code,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            if asyncio.run(test()):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[ERROR] {test.__name__}: {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def main():
    return run_async_tests()


if __name__ == "__main__":
    sys.exit(0 if main() else 1)