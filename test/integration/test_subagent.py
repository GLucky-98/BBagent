#!/usr/bin/env python3
"""
test_subagent.py - SubAgent functionality tests

Test SubAgent creation and context compression.
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

from BBagent.core.agent import SubAgent, AgentConfig
from BBagent.core.model import AnthropicModel
from BBagent.core.message import HumanMessage, Session


def create_test_subagent():
    """Create a test SubAgent."""
    model = AnthropicModel(
        model=ENV["model"],
        api_key=ENV["api_key"],
        base_url=ENV["base_url"],
        max_tokens=1000
    )

    session_dir = Path(__file__).parent.parent / "temp" / "test_subagent_session"
    session_dir.mkdir(parents=True, exist_ok=True)

    # SubAgent takes (model, tools, system_prompt, skills, name, logger) not AgentConfig
    return SubAgent(
        model=model,
        tools=[],
        system_prompt="",
        skills=[],
        name="TestSubAgent",
        logger=None
    )


def test_subagent_creation():
    """Test SubAgent creation."""
    print("[TEST] test_subagent_creation")
    try:
        subagent = create_test_subagent()
        assert subagent is not None
        assert subagent.name == "TestSubAgent"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_subagent_run():
    """Test SubAgent run execution."""
    print("[TEST] test_subagent_run")
    try:
        subagent = create_test_subagent()

        async def run_test():
            # SubAgent.run() returns str, not an async generator
            result = await subagent.run(HumanMessage(content="Say 'subagent test' in one phrase"))
            return result

        import asyncio
        result = asyncio.run(run_test())
        assert len(result) > 0
        print(f"[PASS] SubAgent responded: {result[:50]}")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_subagent_creation,
        test_subagent_run,
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