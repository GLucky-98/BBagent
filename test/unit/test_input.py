#!/usr/bin/env python3
"""
test_input.py - Input component tests

Test for BBagent.core.input module.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "BBagent"))

from core.input import EventType, AgentEvent, InputChannel


def test_event_type_enum():
    """Test EventType enum values."""
    print("[TEST] test_event_type_enum")
    try:
        assert EventType.USER_MESSAGE.value == "user_message"
        assert EventType.TIMER_TRIGGER.value == "timer_trigger"
        assert EventType.AGENT_MESSAGE.value == "agent_message"
        assert EventType.SYSTEM_EVENT.value == "system_event"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_agent_event_creation():
    """Test AgentEvent creation."""
    print("[TEST] test_agent_event_creation")
    try:
        event = AgentEvent(
            type=EventType.USER_MESSAGE,
            source_id="test_source",
            payload={"content": "Hello"}
        )
        assert event.type == EventType.USER_MESSAGE
        assert event.source_id == "test_source"
        assert event.payload["content"] == "Hello"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_input_channel_creation():
    """Test InputChannel creation."""
    print("[TEST] test_input_channel_creation")
    try:
        channel = InputChannel()
        assert channel is not None
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_input_channel_push():
    """Test pushing events to InputChannel."""
    print("[TEST] test_input_channel_push")
    try:
        channel = InputChannel()
        channel.push("test content", source_id="test")
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_event_type_enum,
        test_agent_event_creation,
        test_input_channel_creation,
        test_input_channel_push,
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