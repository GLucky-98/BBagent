"""Baseline tests for ToolFactory — builtin registration and MCP notifications."""

from backend.factories import _builtin_tool_id, _mcp_tool_id
from backend.factories.tool_factory import ToolFactory
from backend.schemas import ToolConfig


def test_load_builtins_registers_all_builtin_tools(tmp_path):
    factory = ToolFactory(tmp_path)
    factory.load_builtins()

    all_tools = factory.list_by_source("built_in")
    names = {t.name for t in all_tools}

    expected = {
        "read",
        "read_file",
        "write",
        "edit",
        "bash",
        "grep",
        "find",
        "ls",
        "web_search",
        "fetch_url",
        "sub_agent",
    }
    assert expected.issubset(names)
    for name in expected:
        assert name in names


def test_builtin_tool_has_stable_uuid5_id():
    read_id = _builtin_tool_id("read")

    assert read_id == _builtin_tool_id("read")
    assert read_id != _builtin_tool_id("write")


def test_load_builtins_is_idempotent(tmp_path):
    factory = ToolFactory(tmp_path)
    factory.load_builtins()
    count1 = len(factory.list_by_source("built_in"))

    factory.load_builtins()
    count2 = len(factory.list_by_source("built_in"))

    assert count1 == count2


def test_on_mcp_added_registers_tool_configs(tmp_path):
    factory = ToolFactory(tmp_path)
    mcp_id = "mcp-server-1"
    tools = [
        ToolConfig(
            id=_mcp_tool_id(mcp_id, "search"),
            name="search",
            source="mcp",
            description="Search tool",
            mcpServerId=mcp_id,
        ),
        ToolConfig(
            id=_mcp_tool_id(mcp_id, "list"),
            name="list",
            source="mcp",
            description="List tool",
            mcpServerId=mcp_id,
        ),
    ]

    factory.on_mcp_added(mcp_id, tools)

    mcp_tools = factory.list_by_source("mcp")
    assert len(mcp_tools) == 2
    names = {t.name for t in mcp_tools}
    assert names == {"search", "list"}


def test_on_mcp_removed_clears_all_tools_for_that_server(tmp_path):
    factory = ToolFactory(tmp_path)
    mcp_id_a = "mcp-a"
    mcp_id_b = "mcp-b"

    factory.on_mcp_added(mcp_id_a, [
        ToolConfig(id=_mcp_tool_id(mcp_id_a, "tool-a"), name="tool-a", source="mcp", mcpServerId=mcp_id_a),
    ])
    factory.on_mcp_added(mcp_id_b, [
        ToolConfig(id=_mcp_tool_id(mcp_id_b, "tool-b"), name="tool-b", source="mcp", mcpServerId=mcp_id_b),
    ])

    factory.on_mcp_removed(mcp_id_a)

    mcp_tools = factory.list_by_source("mcp")
    assert len(mcp_tools) == 1
    assert mcp_tools[0].name == "tool-b"


def test_on_mcp_updated_replaces_all_tools(tmp_path):
    factory = ToolFactory(tmp_path)
    mcp_id = "mcp-1"

    factory.on_mcp_added(mcp_id, [
        ToolConfig(id=_mcp_tool_id(mcp_id, "old-tool"), name="old-tool", source="mcp", mcpServerId=mcp_id),
    ])
    factory.on_mcp_updated(mcp_id, [
        ToolConfig(id=_mcp_tool_id(mcp_id, "new-tool"), name="new-tool", source="mcp", mcpServerId=mcp_id),
    ])

    mcp_tools = factory.list_by_source("mcp")
    assert len(mcp_tools) == 1
    assert mcp_tools[0].name == "new-tool"


def test_list_by_source_filters_correctly(tmp_path):
    factory = ToolFactory(tmp_path)
    factory.load_builtins()

    factory.on_mcp_added("mcp-1", [
        ToolConfig(id=_mcp_tool_id("mcp-1", "mcp-read"), name="mcp-read", source="mcp", mcpServerId="mcp-1"),
    ])

    builtins = factory.list_by_source("built_in")
    mcps = factory.list_by_source("mcp")

    assert len(builtins) >= 1
    assert all(t.source == "built_in" for t in builtins)
    assert len(mcps) == 1
    assert all(t.source == "mcp" for t in mcps)


def test_mcp_tool_id_is_deterministic():
    id1 = _mcp_tool_id("server-1", "read_file")
    id2 = _mcp_tool_id("server-1", "read_file")
    id3 = _mcp_tool_id("server-1", "write_file")
    id4 = _mcp_tool_id("server-2", "read_file")

    assert id1 == id2
    assert id1 != id3
    assert id1 != id4
