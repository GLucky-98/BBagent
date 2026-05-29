#!/usr/bin/env python3
"""
test_tool.py - Tool component tests

Test for BBagent.core.tool module.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "BBagent"))

from core.tool import Tool, tool


def test_tool_creation():
    """Test Tool creation."""
    print("[TEST] test_tool_creation")
    try:
        def test_func(arg1: str, arg2: int = 10):
            return f"{arg1} {arg2}"

        t = Tool(func=test_func, name="test_tool", description="A test tool")
        assert t.name == "test_tool"
        assert t.description == "A test tool"
        assert "arg1" in t.input_schema.get("properties", {})
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_tool_invoke():
    """Test Tool synchronous invocation."""
    print("[TEST] test_tool_invoke")
    try:
        def add(a: int, b: int) -> int:
            return a + b

        t = Tool(func=add, name="add_tool", description="Add two numbers")
        result = t.invoke({"a": 5, "b": 3})
        assert result == 8
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_tool_with_default_params():
    """Test Tool invocation with default parameters."""
    print("[TEST] test_tool_with_default_params")
    try:
        def greet(name: str, greeting: str = "Hello"):
            return f"{greeting}, {name}!"

        t = Tool(func=greet, name="greet", description="Greet someone")
        result = t.invoke({"name": "Alice"})
        assert result == "Hello, Alice!"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_tool_schema_generation():
    """Test automatic input schema generation from function signature."""
    print("[TEST] test_tool_schema_generation")
    try:
        def sample_func(name: str, count: int, active: bool = True):
            pass

        t = Tool(func=sample_func)
        schema = t.input_schema

        assert "name" in schema.get("properties", {})
        assert "count" in schema.get("properties", {})
        assert "active" in schema.get("properties", {})
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_tool_to_config_dict():
    """Test Tool configuration serialization."""
    print("[TEST] test_tool_to_config_dict")
    try:
        def config_func(x: int):
            return x

        t = Tool(func=config_func, name="config_test", description="Test config")
        config = t.to_config_dict()

        assert "name" in config
        assert "description" in config
        assert "input_schema" in config
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_tool_creation,
        test_tool_invoke,
        test_tool_with_default_params,
        test_tool_schema_generation,
        test_tool_to_config_dict,
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