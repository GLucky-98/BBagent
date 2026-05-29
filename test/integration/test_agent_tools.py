#!/usr/bin/env python3
"""
test_agent_tools.py - Agent tool calling tests

Test Agent with tool registration and execution.
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

from BBagent.core.agent import Agent, AgentConfig
from BBagent.core.model import AnthropicModel
from BBagent.core.message import HumanMessage, Session
from BBagent.core.tool import Tool


def simple_add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def simple_greet(name: str, greeting: str = "Hello") -> str:
    """Greet someone."""
    return f"{greeting}, {name}!"


def get_env_info() -> str:
    """Return environment info (test tool)."""
    return "test_environment"


def create_test_agent_with_tools():
    """Create a test agent with tools."""
    model = AnthropicModel(
        model=ENV["model"],
        api_key=ENV["api_key"],
        base_url=ENV["base_url"],
        max_tokens=1000
    )

    session_dir = Path(__file__).parent.parent / "temp" / "test_agent_tools_session"
    session_dir.mkdir(parents=True, exist_ok=True)
    session = Session.create(session_dir)

    add_tool = Tool(func=simple_add, name="add_tool", description="Add two numbers")
    greet_tool = Tool(func=simple_greet, name="greet_tool", description="Greet someone")
    env_tool = Tool(func=get_env_info, name="env_info", description="Return environment info")

    config = AgentConfig(
        model=model,
        name="TestAgent_Tools",
        session=session,
        tools=[add_tool, greet_tool, env_tool],
        skills=[],
    )

    return Agent(config)


def test_agent_tools_registration():
    """Test tool registration with Agent."""
    print("[TEST] test_agent_tools_registration")
    try:
        agent = create_test_agent_with_tools()
        assert len(agent.tools) == 3
        print(f"[PASS] Registered {len(agent.tools)} tools")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_agent_tool_call_execution():
    """Test tool call execution via Agent."""
    print("[TEST] test_agent_tool_call_execution")
    try:
        agent = create_test_agent_with_tools()

        async def run_test():
            result = ""
            async for chunk in agent.run(HumanMessage(content="Use the add tool to calculate 5 + 3")):
                if hasattr(chunk, 'text'):
                    result += chunk.text
            return result

        import asyncio
        result = asyncio.run(run_test())
        print(f"[PASS] Agent tool call result: {result[:100]}")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_agent_tools_registration,
        test_agent_tool_call_execution,
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