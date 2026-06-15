import pytest

from backend.errors import ConflictError, ErrorCode
from backend.factories.agent_factory import AgentFactory
from bbagent.core.agent import AgentState
from bbagent.core.message import (
    HumanMessage,
    ModelMessage,
    Session,
    TextBlock,
    ToolMessage,
    ToolUseBlock,
    Turn,
)


class FakeAgent:
    name = "Helper"

    def __init__(self, session):
        self.session = session


def make_factory_with_session(session):
    factory = AgentFactory.__new__(AgentFactory)
    factory.agents = {"agent-1": FakeAgent(session)}
    return factory


def test_get_messages_merges_user_text_blocks_and_outputs_millisecond_timestamp():
    session = Session()
    session.turns = [
        Turn(
            messages=[
                HumanMessage(
                    content=[TextBlock(text="first"), TextBlock(text="second")],
                    timestamp=1_700_000_000,
                ),
                ModelMessage(
                    id="model-1",
                    content="done",
                    stop_reason="end_turn",
                    usage_data={},
                    timestamp=1_700_000_001,
                ),
            ]
        )
    ]
    factory = make_factory_with_session(session)

    assert factory.get_messages("agent-1") == [
        {
            "role": "user",
            "content": "first\nsecond",
            "source_agent": "Helper",
            "timestamp": 1_700_000_000_000,
        },
        {
            "role": "assistant",
            "content": "done",
            "messageId": "model-1",
            "source_agent": "Helper",
            "timestamp": 1_700_000_001_000,
        },
    ]


def test_get_messages_keeps_model_text_blocks_and_tool_calls_separate():
    session = Session()
    session.turns = [
        Turn(
            messages=[
                ModelMessage(
                    id="model-1",
                    content=[TextBlock(text="part one"), TextBlock(text="part two")],
                    stop_reason="tool_use",
                    usage_data={},
                    thinking="reasoning",
                    tool_calls=[
                        ToolUseBlock(id="tool-1", name="read", input={"path": "README.md"})
                    ],
                    timestamp=1_700_000_001,
                ),
                ToolMessage(
                    id="tool-1",
                    name="read",
                    content="file contents",
                    timestamp=1_700_000_002,
                ),
                ModelMessage(
                    id="model-2",
                    content="done",
                    stop_reason="end_turn",
                    usage_data={},
                    timestamp=1_700_000_003,
                )
            ]
        )
    ]
    factory = make_factory_with_session(session)

    messages = factory.get_messages("agent-1")

    assert [message["chunkType"] for message in messages if message["role"] == "system"] == [
        "thinking",
        "tool_use",
        "tool_result",
    ]
    assert [message["content"] for message in messages if message["role"] == "assistant"] == [
        "part one",
        "part two",
        "done",
    ]
    tool_use = next(message for message in messages if message.get("chunkType") == "tool_use")
    tool_result = next(message for message in messages if message.get("chunkType") == "tool_result")
    assert tool_use["messageId"] == "model-1"
    assert tool_use["toolCallId"] == "tool-1"
    assert tool_result["messageId"] == "tool-1"
    assert tool_result["toolCallId"] == "tool-1"
    assert {message["timestamp"] for message in messages} == {
        1_700_000_001_000,
        1_700_000_002_000,
        1_700_000_003_000,
    }


def test_get_messages_skips_incomplete_turns():
    session = Session()
    session.turns = [
        Turn(
            messages=[
                HumanMessage(content="old", timestamp=1),
                ModelMessage(id="done", content="ok", stop_reason="end_turn", usage_data={}, timestamp=2),
            ]
        ),
        Turn(
            messages=[
                HumanMessage(content="new", timestamp=3),
                ModelMessage(
                    id="pending",
                    content="I need a tool",
                    stop_reason="tool_use",
                    usage_data={},
                    tool_calls=[
                        ToolUseBlock(id="pending-tool", name="read", input={"path": "README.md"})
                    ],
                    timestamp=4,
                ),
            ]
        ),
    ]
    factory = make_factory_with_session(session)

    messages = factory.get_messages("agent-1")

    assert [message["content"] for message in messages] == ["old", "ok"]


def test_get_messages_exposes_distinct_tool_call_ids_for_multiple_tool_uses():
    session = Session()
    session.turns = [
        Turn(
            messages=[
                HumanMessage(content="use tools", timestamp=1),
                ModelMessage(
                    id="model-1",
                    content="",
                    stop_reason="tool_use",
                    usage_data={},
                    tool_calls=[
                        ToolUseBlock(id="tool-a", name="read", input={"path": "a"}),
                        ToolUseBlock(id="tool-b", name="read", input={"path": "b"}),
                    ],
                    timestamp=2,
                ),
                ToolMessage(id="tool-a", name="read", content="a", timestamp=3),
                ToolMessage(id="tool-b", name="read", content="b", timestamp=4),
                ModelMessage(
                    id="model-2",
                    content="done",
                    stop_reason="end_turn",
                    usage_data={},
                    timestamp=5,
                ),
            ]
        )
    ]
    factory = make_factory_with_session(session)

    messages = factory.get_messages("agent-1")

    assert [
        message["toolCallId"]
        for message in messages
        if message.get("chunkType") == "tool_use"
    ] == ["tool-a", "tool-b"]


class RunningAgent:
    name = "Runner"
    state = AgentState.Running


@pytest.mark.asyncio
async def test_switch_session_rejects_running_agent():
    factory = AgentFactory.__new__(AgentFactory)
    factory.agents = {"agent-1": RunningAgent()}

    with pytest.raises(ConflictError) as exc:
        await factory.switch_session("agent-1", "session-1")

    assert exc.value.code == ErrorCode.AGENT_ALREADY_RUNNING


@pytest.mark.asyncio
async def test_new_session_rejects_running_agent():
    factory = AgentFactory.__new__(AgentFactory)
    factory.agents = {"agent-1": RunningAgent()}

    with pytest.raises(ConflictError) as exc:
        await factory.new_session("agent-1")

    assert exc.value.code == ErrorCode.AGENT_ALREADY_RUNNING


class WaitingAgent:
    name = "Waiter"
    state = AgentState.Waiting

    def __init__(self, session_dir):
        self.session_dir = session_dir
        self.loaded_session = None
        self.created_session = False

    async def load_session(self, session_path):
        self.loaded_session = session_path

    async def new_session(self):
        self.created_session = True


@pytest.mark.asyncio
async def test_switch_session_allows_waiting_agent(monkeypatch, tmp_path):
    factory = AgentFactory.__new__(AgentFactory)
    agent = WaitingAgent(tmp_path)
    factory.agents = {"agent-1": agent}
    monkeypatch.setattr("pathlib.Path.exists", lambda _self: True)
    monkeypatch.setattr(factory, "_update_last_session_id", lambda _agent_id: None)
    monkeypatch.setattr(factory, "_refresh_session_index", lambda _agent_id: None)

    await factory.switch_session("agent-1", "session-1")

    assert agent.loaded_session is not None


@pytest.mark.asyncio
async def test_new_session_allows_waiting_agent(monkeypatch, tmp_path):
    factory = AgentFactory.__new__(AgentFactory)
    agent = WaitingAgent(tmp_path)
    factory.agents = {"agent-1": agent}
    monkeypatch.setattr(factory, "_update_last_session_id", lambda _agent_id: None)
    monkeypatch.setattr(factory, "_refresh_session_index", lambda _agent_id: None)

    await factory.new_session("agent-1")

    assert agent.created_session
