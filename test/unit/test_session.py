#!/usr/bin/env python3
"""
test_session.py - Session component tests

Test for BBagent.core.message Session class.
"""
import sys
from pathlib import Path

TEST_DIR = Path(__file__).parent.parent
PROJECT_ROOT = TEST_DIR.parent
BBAGENT_DIR = PROJECT_ROOT / "BBagent"

sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(BBAGENT_DIR))

from core.message import Session, HumanMessage, ModelMessage, ToolMessage, TextBlock, Turn


def test_session_creation():
    """Test Session creation."""
    print("[TEST] test_session_creation")
    try:
        session_dir = Path(__file__).parent.parent / "temp" / "test_session"
        session_dir.mkdir(parents=True, exist_ok=True)

        session = Session.create(session_dir)
        assert session is not None
        assert session.id is not None
        assert len(session.turns) == 0
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_session_add_message():
    """Test adding messages to session."""
    print("[TEST] test_session_add_message")
    try:
        session_dir = Path(__file__).parent.parent / "temp" / "test_session"
        session_dir.mkdir(parents=True, exist_ok=True)

        session = Session.create(session_dir)

        human_msg = HumanMessage(content="Hello")
        session.add_message(human_msg)

        assert len(session.turns) == 1
        assert isinstance(session.turns[0], Turn)
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_session_fork():
    """Test session forking (branching)."""
    print("[TEST] test_session_fork")
    try:
        session_dir = Path(__file__).parent.parent / "temp" / "test_session"
        session_dir.mkdir(parents=True, exist_ok=True)

        session = Session.create(session_dir)
        session.add_message(HumanMessage(content="Hello"))

        forked_session = session.fork()
        assert forked_session is not None
        assert forked_session.id != session.id
        assert len(forked_session.turns) == len(session.turns)
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_session_messages_property():
    """Test session messages property."""
    print("[TEST] test_session_messages_property")
    try:
        session_dir = Path(__file__).parent.parent / "temp" / "test_session"
        session_dir.mkdir(parents=True, exist_ok=True)

        session = Session.create(session_dir)
        session.add_message(HumanMessage(content="Test"))

        messages = session.messages
        assert len(messages) == 1
        assert isinstance(messages[0], HumanMessage)
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_session_creation,
        test_session_add_message,
        test_session_fork,
        test_session_messages_property,
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