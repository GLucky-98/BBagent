#!/usr/bin/env python3
"""
test_agent_skill.py - Agent skill invocation tests

Test Agent skill loading and invocation.
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
from BBagent.core.skill import Skill


def create_test_skill():
    """Create a test skill file."""
    skill_dir = Path(__file__).parent.parent / "temp" / "test_skills"
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_content = """---
name: test_skill
description: A test skill for testing
---
# Test Skill

You are a test skill. When invoked, respond with "Skill test successful".
"""
    skill_file = skill_dir / "test_skill.md"
    skill_file.write_text(skill_content)
    return skill_dir


def create_agent_with_skill():
    """Create a test agent with skills."""
    model = AnthropicModel(
        model=ENV["model"],
        api_key=ENV["api_key"],
        base_url=ENV["base_url"],
        max_tokens=1000
    )

    session_dir = Path(__file__).parent.parent / "temp" / "test_agent_skill_session"
    session_dir.mkdir(parents=True, exist_ok=True)
    session = Session.create(session_dir)

    skill_dir = create_test_skill()

    skill = Skill(
        name="test_skill",
        description="A test skill",
        body="# Test Skill\n\nWhen invoked, respond with 'Skill test successful'.",
        path=skill_dir / "test_skill.md"
    )

    config = AgentConfig(
        model=model,
        name="TestAgent_Skill",
        session=session,
        tools=[],
        skills=[skill],
    )

    return Agent(config)


def test_agent_skill_loading():
    """Test skill loading into Agent."""
    print("[TEST] test_agent_skill_loading")
    try:
        agent = create_agent_with_skill()
        assert len(agent.skills) == 1
        assert "test_skill" in agent.skills
        print("[PASS] Skill loaded successfully")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_agent_skill_invocation():
    """Test skill invocation via message."""
    print("[TEST] test_agent_skill_invocation")
    try:
        agent = create_agent_with_skill()

        async def run_test():
            result = ""
            async for chunk in agent.run(HumanMessage(content="Use the test skill")):
                # chunk is a dict with 'type' and 'content' keys
                if chunk.get('type') == 'text':
                    result += chunk.get('content', '')
            return result

        import asyncio
        result = asyncio.run(run_test())
        assert len(result) > 0
        print(f"[PASS] Skill invocation result: {result[:100]}")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_agent_skill_loading,
        test_agent_skill_invocation,
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