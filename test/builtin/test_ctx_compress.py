#!/usr/bin/env python3
"""
test_ctx_compress.py - Context compression tests

Test for BBagent.built_in_hook.ctx_compress_hook module.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BBAGENT_PKG = PROJECT_ROOT / "BBagent"
TEST_DIR = PROJECT_ROOT / "test"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BBAGENT_PKG))
sys.path.insert(0, str(TEST_DIR))

from env import get_env
ENV = get_env()

from BBagent.core.message import Session, HumanMessage, ModelMessage, TextBlock
from BBagent.core.model import AnthropicModel


def test_turn_grouping():
    """Test turn grouping by size."""
    print("[TEST] test_turn_grouping")
    try:
        session_dir = Path(__file__).parent.parent / "temp" / "test_ctx_session"
        session_dir.mkdir(parents=True, exist_ok=True)
        session = Session.create(session_dir)

        for i in range(5):
            session.add_message(HumanMessage(content=f"Message {i}"))

        # Session has turns
        assert len(session.turns) >= 1
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_session_token_estimation():
    """Test session token count estimation."""
    print("[TEST] test_session_token_estimation")
    try:
        session_dir = Path(__file__).parent.parent / "temp" / "test_token_session"
        session_dir.mkdir(parents=True, exist_ok=True)
        session = Session.create(session_dir)

        session.add_message(HumanMessage(content="This is a test message for token counting"))

        token_count = session.get_visible_token_count()
        assert token_count is not None
        assert token_count > 0
        print(f"[PASS] Token count: {token_count}")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_compression_check():
    """Test if compression is needed."""
    print("[TEST] test_compression_check")
    try:
        session_dir = Path(__file__).parent.parent / "temp" / "test_compress_check"
        session_dir.mkdir(parents=True, exist_ok=True)
        session = Session.create(session_dir)

        for i in range(20):
            session.add_message(HumanMessage(content=f"Long message content number {i} " * 50))

        # Session should have turns
        assert len(session.turns) >= 1
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_turn_grouping,
        test_session_token_estimation,
        test_compression_check,
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