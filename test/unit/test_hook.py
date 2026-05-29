#!/usr/bin/env python3
"""
test_hook.py - Hook component tests

Test for BBagent.core.hook module.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "BBagent"))

from core.hook import (
    HookType,
    HookContext,
    Hook,
    AgentHook,
    HookControl,
)


def test_hook_type_enum():
    """Test HookType enum values."""
    print("[TEST] test_hook_type_enum")
    try:
        assert HookType.BEFORE_RUN.value == "before_run"
        assert HookType.AFTER_INPUT.value == "after_input"
        assert HookType.BEFORE_STREAM.value == "before_stream"
        assert HookType.ON_TEXT_CHUNK.value == "on_text_chunk"
        assert HookType.ON_THINKING_CHUNK.value == "on_thinking_chunk"
        assert HookType.ON_TOOL_USE.value == "on_tool_use"
        assert HookType.ON_TOOL_RESULT.value == "on_tool_result"
        assert HookType.ON_MESSAGE.value == "on_message"
        assert HookType.ON_ERROR.value == "on_error"
        assert HookType.AFTER_RUN.value == "after_run"
        assert HookType.NEW_SESSION.value == "new_session"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_hook_context():
    """Test HookContext data passing."""
    print("[TEST] test_hook_context")
    try:
        ctx = HookContext()
        ctx.set("test_key", "test_value")
        assert ctx.get("test_key") == "test_value"
        assert ctx.get("nonexistent", "default") == "default"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_hook_context_break_loop():
    """Test HookContext break loop functionality."""
    print("[TEST] test_hook_context_break_loop")
    try:
        ctx = HookContext()
        assert ctx.get_control() == HookControl.NORMAL

        ctx.break_loop()
        assert ctx.get_control() == HookControl.BREAK

        ctx.reset_control()
        assert ctx.get_control() == HookControl.NORMAL
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_agent_hook_creation():
    """Test AgentHook creation and initialization."""
    print("[TEST] test_agent_hook_creation")
    try:
        hook_manager = AgentHook()
        assert hook_manager._enabled is True
        assert hook_manager._context is None
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_agent_hook_register():
    """Test Hook registration with function."""
    print("[TEST] test_agent_hook_register")
    try:
        hook_manager = AgentHook()

        def test_handler(ctx, *args, **kwargs):
            pass

        hook_manager.register(
            HookType.BEFORE_RUN,
            test_handler,
            priority=100
        )

        hooks = hook_manager.list_hooks()
        assert HookType.BEFORE_RUN in hooks
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_agent_hook_decorator():
    """Test Hook registration with decorator."""
    print("[TEST] test_agent_hook_decorator")
    try:
        hook_manager = AgentHook()

        @hook_manager.hook(HookType.ON_TEXT_CHUNK, priority=50)
        def text_handler(ctx, chunk, *args, **kwargs):
            pass

        hooks = hook_manager.list_hooks()
        assert HookType.ON_TEXT_CHUNK in hooks
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_hook_priority_ordering():
    """Test Hooks are ordered by priority."""
    print("[TEST] test_hook_priority_ordering")
    try:
        hook_manager = AgentHook()

        @hook_manager.hook(HookType.BEFORE_RUN, priority=200)
        def low_priority(ctx, *args, **kwargs):
            pass

        @hook_manager.hook(HookType.BEFORE_RUN, priority=50)
        def high_priority(ctx, *args, **kwargs):
            pass

        hooks = hook_manager.list_hooks()
        before_run_hooks = hooks.get(HookType.BEFORE_RUN, [])

        # High priority (50) should come before low priority (200)
        assert len(before_run_hooks) == 2
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_hook_enable_disable():
    """Test AgentHook enable/disable functionality."""
    print("[TEST] test_hook_enable_disable")
    try:
        hook_manager = AgentHook()
        hook_manager.disable()
        assert hook_manager._enabled is False

        hook_manager.enable()
        assert hook_manager._enabled is True
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_hook_type_enum,
        test_hook_context,
        test_hook_context_break_loop,
        test_agent_hook_creation,
        test_agent_hook_register,
        test_agent_hook_decorator,
        test_hook_priority_ordering,
        test_hook_enable_disable,
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