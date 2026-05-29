#!/usr/bin/env python3
"""
test_logger.py - Logger component tests

Test for BBagent.core.logger module.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "BBagent"))

from core.logger import AgentLogger


def test_logger_creation():
    """Test AgentLogger creation."""
    print("[TEST] test_logger_creation")
    try:
        log_dir = Path(__file__).parent.parent / "temp" / "test_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        logger = AgentLogger(name="test_logger", log_dir=log_dir)
        assert logger is not None
        assert logger.name == "test_logger"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_logger_info():
    """Test logger info output."""
    print("[TEST] test_logger_info")
    try:
        log_dir = Path(__file__).parent.parent / "temp" / "test_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        logger = AgentLogger(name="test_logger", log_dir=log_dir)
        logger.info("Test info message")
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_logger_warning():
    """Test logger warning output."""
    print("[TEST] test_logger_warning")
    try:
        log_dir = Path(__file__).parent.parent / "temp" / "test_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        logger = AgentLogger(name="test_logger", log_dir=log_dir)
        logger.warning("Test warning message")
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_logger_span():
    """Test logger span context manager."""
    print("[TEST] test_logger_span")
    try:
        log_dir = Path(__file__).parent.parent / "temp" / "test_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        logger = AgentLogger(name="test_logger", log_dir=log_dir)
        with logger.span("test_operation"):
            pass
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_logger_creation,
        test_logger_info,
        test_logger_warning,
        test_logger_span,
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