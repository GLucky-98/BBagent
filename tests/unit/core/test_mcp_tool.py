import re

import pytest

from bbagent.core.agent import Agent, AgentConfig
from bbagent.core.mcp import MCPTool, make_safe_mcp_runtime_name
from bbagent.core.tool import Tool


class FakeMCPClient:
    name = "Demo Server/v1"

    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        return {"ok": True}


def _mcp_config(name: str = "search.tools/run"):
    return {
        "name": name,
        "description": "Run a fake MCP tool",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    }


def test_make_safe_mcp_runtime_name_uses_mcp_prefix_and_safe_characters():
    name = make_safe_mcp_runtime_name("Demo Server/v1", "search.tools/run")

    assert name == "mcp__Demo_Server_v1__search_tools_run"
    assert re.fullmatch(r"[A-Za-z0-9_-]+", name)


@pytest.mark.asyncio
async def test_mcp_tool_exposes_safe_name_but_calls_raw_name():
    client = FakeMCPClient()
    tool = MCPTool(client, _mcp_config())

    assert tool.name == "mcp__Demo_Server_v1__search_tools_run"
    assert tool.raw_name == "search.tools/run"

    await tool.async_invoke({"query": "agent"})

    assert client.calls == [("search.tools/run", {"query": "agent"})]


def test_agent_rejects_duplicate_tool_names(tmp_path):
    def first():
        return "first"

    def second():
        return "second"

    first_tool = Tool(first, name="same_name")
    second_tool = Tool(second, name="same_name")
    agent = Agent(
        AgentConfig(
            model=None,
            name="DuplicateToolAgent",
            base_dir=tmp_path,
            tools=[first_tool],
        )
    )

    with pytest.raises(ValueError, match="Duplicate tool name: same_name"):
        agent.add_tools([second_tool])
