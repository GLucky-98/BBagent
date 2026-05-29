#!/usr/bin/env python3
"""
test_team.py - Multi-agent collaboration tests

Test AgentTeam creation and inter-agent messaging.
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

from BBagent.core.team import AgentTeam, TeamConfig
from BBagent.core.model import AnthropicModel
from BBagent.core.agent import Agent, AgentConfig
from BBagent.core.message import Session


def create_test_agent(name: str):
    """Create a test agent."""
    model = AnthropicModel(
        model=ENV["model"],
        api_key=ENV["api_key"],
        base_url=ENV["base_url"],
        max_tokens=1000
    )

    session_dir = Path(__file__).parent.parent / "temp" / f"test_team_{name}_session"
    session_dir.mkdir(parents=True, exist_ok=True)
    session = Session.create(session_dir)

    config = AgentConfig(
        model=model,
        name=name,
        session=session,
        tools=[],
        skills=[],
    )

    return Agent(config)


def test_team_creation():
    """Test AgentTeam creation."""
    print("[TEST] test_team_creation")
    try:
        team = AgentTeam(name="TestTeam")
        assert team is not None
        assert team.name == "TestTeam"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_team_agent_registration():
    """Test agent registration with team."""
    print("[TEST] test_team_agent_registration")
    try:
        team = AgentTeam(name="TestTeam")
        agent1 = create_test_agent("Agent1")
        agent2 = create_test_agent("Agent2")

        team.add_agent(agent1)
        team.add_agent(agent2)

        assert len(team.agents) == 2
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_team_to_config_dict():
    """Test team configuration serialization."""
    print("[TEST] test_team_to_config_dict")
    try:
        team = AgentTeam(name="TestTeam")
        agent = create_test_agent("ConfigTest")
        team.add_agent(agent)

        config = team.to_config_dict()
        assert "name" in config
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_team_creation,
        test_team_agent_registration,
        test_team_to_config_dict,
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