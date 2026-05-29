#!/usr/bin/env python3
"""
test_agent_basic.py - Agent basic functionality tests

Test basic Agent initialization and conversation flow.
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

from BBagent.core.agent import Agent, AgentConfig, AgentState
from BBagent.core.model import AnthropicModel
from BBagent.core.message import HumanMessage, Session


def create_test_agent():
    """Create a test agent with env config."""
    model = AnthropicModel(
        model=ENV["model"],
        api_key=ENV["api_key"],
        base_url=ENV["base_url"],
        max_tokens=1000
    )

    session_dir = Path(__file__).parent.parent / "temp" / "test_agent_session"
    session_dir.mkdir(parents=True, exist_ok=True)
    session = Session.create(session_dir)

    config = AgentConfig(
        model=model,
        name="TestAgent_Basic",
        session=session,
        tools=[],
        skills=[],
    )

    return Agent(config)


def test_agent_creation():
    """Test Agent creation and initialization."""
    print("[TEST] test_agent_creation")
    try:
        agent = create_test_agent()
        assert agent is not None
        assert agent.name == "TestAgent_Basic"
        assert agent.state == AgentState.Ready
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_agent_single_turn():
    """Test single-turn conversation."""
    print("[TEST] test_agent_single_turn")
    try:
        agent = create_test_agent()

        async def run_test():
            result = ""
            async for chunk in agent.run(HumanMessage(content="Say 'test' in one word")):
                # chunk is a dict with 'type' and 'content' keys
                if chunk.get('type') == 'text':
                    result += chunk.get('content', '')
            return result

        import asyncio
        result = asyncio.run(run_test())
        assert len(result) > 0
        print(f"[PASS] Agent responded with: {result[:50]}")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_agent_multi_turn():
    """Test multi-turn conversation."""
    print("[TEST] test_agent_multi_turn")
    try:
        agent = create_test_agent()

        async def run_test():
            async for chunk in agent.run(HumanMessage(content="My name is Alice")):
                pass
            async for chunk in agent.run(HumanMessage(content="What is my name?")):
                pass
            return True

        import asyncio
        result = asyncio.run(run_test())
        assert result is True
        print("[PASS] Multi-turn conversation completed")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_agent_save():
    """Test Agent state save."""
    print("[TEST] test_agent_save")
    try:
        agent = create_test_agent()
        agent.save()

        assert agent.session_dir.exists()
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_agent_creation,
        test_agent_single_turn,
        test_agent_multi_turn,
        test_agent_save,
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