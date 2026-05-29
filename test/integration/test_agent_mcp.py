#!/usr/bin/env python3
"""
test_agent_mcp.py - Agent MCP tool calling tests

Test Agent MCP client connection and tool invocation.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BBAGENT_PKG = PROJECT_ROOT / "BBagent"
TEST_DIR = PROJECT_ROOT / "test"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BBAGENT_PKG))
sys.path.insert(0, str(TEST_DIR))

from BBagent.core.mcp import MCPClient, MCPServerConfig, parse_config_file, load_configs


def create_mcp_config():
    """Create a test MCP server config."""
    return MCPServerConfig(
        name="test_mcp",
        command="echo",
        args=["test"],
        env={}
    )


def test_mcp_client_creation():
    """Test MCPClient creation."""
    print("[TEST] test_mcp_client_creation")
    try:
        config = create_mcp_config()
        client = MCPClient(config)
        assert client is not None
        assert client.name == "test_mcp"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_load_configs():
    """Test load_configs function."""
    print("[TEST] test_load_configs")
    try:
        import tempfile, json, os
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"name": "test", "command": "echo", "args": ["hello"]}
            with open(os.path.join(tmpdir, "test.json"), "w") as f:
                json.dump(config, f)
            result = load_configs(tmpdir)
            assert len(result) == 1
            assert "test" in result
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_agent_mcp_tool_registration():
    """Test Agent MCP tool registration via config."""
    print("[TEST] test_agent_mcp_tool_registration")
    try:
        from env import get_env
        ENV = get_env()

        from BBagent.core.model import AnthropicModel
        from BBagent.core.agent import Agent, AgentConfig
        from BBagent.core.message import Session

        model = AnthropicModel(
            model=ENV["model"],
            api_key=ENV["api_key"],
            base_url=ENV["base_url"],
            max_tokens=1000
        )

        session_dir = Path(__file__).parent.parent / "temp" / "test_agent_mcp_session"
        session_dir.mkdir(parents=True, exist_ok=True)
        session = Session.create(session_dir)

        config = AgentConfig(
            model=model,
            name="TestAgent_MCP",
            session=session,
            tools=[],
            skills=[],
        )

        agent = Agent(config)
        assert agent is not None
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_mcp_client_creation,
        test_load_configs,
        test_agent_mcp_tool_registration,
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