"""Baseline tests for backend Pydantic schemas — frontend contract surface."""

import json

from backend.schemas import (
    ModelConfig,
    ToolConfig,
    SkillConfig,
    MCPServerConfig,
    PromptConfig,
    AgentConfig,
    TeamConfig,
    CreateTeamRequest,
    HookDescriptor,
    HookFieldSchema,
    HookSection,
    HookListResponse,
    TimerConfig,
    SessionForkRequest,
    FileNode,
    UIState,
)


def test_model_config_serialization_round_trip():
    config = ModelConfig(
        id="model-1",
        name="Claude",
        provider="anthropic",
        modelName="claude-sonnet-4-20250514",
        apiKey="sk-test",
        baseUrl="https://api.anthropic.com",
        maxContextTokens=200000,
        maxCompletionTokens=4096,
        maxConcurrent=5,
        temperature=0.7,
        topP=0.9,
        thinking=True,
    )

    data = config.model_dump()
    restored = ModelConfig(**data)

    assert restored.id == "model-1"
    assert restored.provider == "anthropic"
    assert restored.modelName == "claude-sonnet-4-20250514"
    assert restored.maxContextTokens == 200000
    assert restored.temperature == 0.7


def test_model_config_core_dict_maps_fields_for_model_ctor():
    config = ModelConfig(
        id="m1",
        name="Test",
        provider="anthropic",
        modelName="claude-opus-4-20250514",
        apiKey="key123",
        baseUrl="https://api.anthropic.com",
        maxContextTokens=100000,
        maxCompletionTokens=2048,
        maxConcurrent=3,
        temperature=0.5,
        topP=1.0,
        thinking=False,
    )

    core = config.core_dict

    assert core["provider"] == "anthropic"
    assert core["model"] == "claude-opus-4-20250514"
    assert core["api_key"] == "key123"
    assert core["base_url"] == "https://api.anthropic.com"
    assert core["max_completion_tokens"] == 2048
    assert core["max_context_tokens"] == 100000
    assert core["max_concurrent"] == 3
    assert core["temperature"] == 0.5
    assert core["top_p"] == 1.0
    assert core["thinking"] is False


def test_tool_config_persisted_id_and_source():
    cfg = ToolConfig(
        id="tool-uuid",
        name="read",
        source="built_in",
    )

    data = json.loads(cfg.model_dump_json())
    restored = ToolConfig(**data)

    assert restored.id == "tool-uuid"
    assert restored.source == "built_in"


def test_tool_config_mcp_fields():
    cfg = ToolConfig(
        id="mcp-tool-uuid",
        name="search",
        source="mcp",
        description="Search the web",
        mcpServerId="mcp-1",
    )

    assert cfg.mcpServerId == "mcp-1"
    assert cfg.source == "mcp"


def test_skill_config_serialization():
    cfg = SkillConfig(
        id="skill-1",
        name="Code Review",
        description="Review code changes",
        path="/path/to/skill",
    )

    data = cfg.model_dump()
    restored = SkillConfig(**data)

    assert restored.name == "Code Review"
    assert restored.path == "/path/to/skill"


def test_mcp_server_config_default_arrays():
    cfg = MCPServerConfig(
        id="mcp-1",
        name="Filesystem",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem"],
        env={"HOME": "/tmp"},
    )

    assert cfg.args == ["-y", "@modelcontextprotocol/server-filesystem"]
    assert cfg.env == {"HOME": "/tmp"}
    assert cfg.tools == []


def test_prompt_config_group_defaults_to_empty():
    cfg = PromptConfig(
        id="p1",
        name="Greeting",
        content="Hello, assistant!",
    )

    assert cfg.group == ""


def test_agent_config_working_dir_syncs_with_tool_policy_cwd():
    cfg = AgentConfig(
        id="a1",
        name="Helper",
        modelId="m1",
        workingDir="/projects",
        toolPolicy={"cwd": "/projects", "bash_default_timeout": 30},
    )

    assert cfg.workingDir == "/projects"
    assert cfg.toolPolicy["cwd"] == "/projects"


def test_agent_config_tool_ids_and_skill_ids_default_to_empty():
    cfg = AgentConfig(
        id="a1",
        name="Agent",
        modelId="m1",
    )

    assert cfg.toolIds == []
    assert cfg.skillIds == []
    assert cfg.hookNames == []
    assert cfg.hookConfig == {}


def test_timer_config_serialization():
    timer = TimerConfig(
        name="Daily review",
        seconds=3600.0,
        hint="Review the codebase",
        enabled=True,
    )

    data = timer.model_dump()
    restored = TimerConfig(**data)

    assert restored.name == "Daily review"
    assert restored.seconds == 3600.0
    assert restored.hint == "Review the codebase"
    assert restored.enabled is True


def test_team_config_contacts_and_member_ids():
    cfg = TeamConfig(
        id="team-1",
        name="CodeTeam",
        teamDescription="A coding team",
        workingDir="/shared",
        memberIds=["agent-a", "agent-b"],
        contacts={"agent-a": {"agent-b": "Reviewer"}, "agent-b": {}},
        started=True,
    )

    assert cfg.memberIds == ["agent-a", "agent-b"]
    assert cfg.contacts["agent-a"]["agent-b"] == "Reviewer"
    assert cfg.started is True


def test_create_team_request_separates_member_configs():
    req = CreateTeamRequest(
        name="NewTeam",
        teamDescription="Team for coding",
        workingDir="/team-dir",
        members=[
            AgentConfig(id="", name="Coder", modelId="m1", workingDir="/team-dir"),
            AgentConfig(id="", name="Reviewer", modelId="m2", workingDir="/team-dir"),
        ],
        contacts={"Coder": {"Reviewer": "Peer"}},
    )

    assert req.name == "NewTeam"
    assert len(req.members) == 2
    assert req.members[0].name == "Coder"


def test_hook_descriptor_and_list_response():
    field = HookFieldSchema(key="threshold", type="number", label="Threshold", default=0.8)
    section = HookSection(title="Config", fields=[field])
    desc = HookDescriptor(
        name="ctx_compress",
        displayName="Context Compression",
        description="Compress context when too long",
        fieldSections=[section],
    )
    resp = HookListResponse(hooks=[desc])

    data = resp.model_dump()
    restored = HookListResponse(**data)

    assert len(restored.hooks) == 1
    assert restored.hooks[0].name == "ctx_compress"
    assert restored.hooks[0].fieldSections[0].fields[0].key == "threshold"


def test_session_fork_request_with_and_without_target():
    fork = SessionForkRequest(turnIndex=3)
    assert fork.turnIndex == 3
    assert fork.targetAgentId is None

    fork_target = SessionForkRequest(turnIndex=0, targetAgentId="agent-b")
    assert fork_target.targetAgentId == "agent-b"


def test_file_node_handles_all_types():
    node = FileNode(
        name="src",
        path="/app/src",
        type="directory",
        children=[
            FileNode(name="main.py", path="/app/src/main.py", type="file", size=1024, extension=".py"),
        ],
    )

    data = json.loads(node.model_dump_json())
    restored = FileNode(**data)

    assert restored.type == "directory"
    assert restored.children[0].name == "main.py"
    assert restored.children[0].size == 1024


def test_ui_state_defaults():
    state = UIState()

    assert state.currentTab == "agent"
    assert state.currentAgentId is None
    assert state.settingsOpen is False
    assert state.settingsTab == "models"
