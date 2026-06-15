import pytest

from backend.factories.session_factory import SessionIndex, SessionManager
from bbagent.core.message import HumanMessage, ModelMessage, Session


class FakeAgent:
    def __init__(self, name, session_dir):
        self.name = name
        self.session_dir = session_dir
        self.session = None


class FakeAgentFactory:
    def __init__(self, agents):
        self.agents = agents
        self.switched = []

    async def switch_session(self, agent_id, session_id):
        self.switched.append((agent_id, session_id))
        self.agents[agent_id].session = Session.load(
            session_id,
            self.agents[agent_id].session_dir / session_id,
        )


def make_complete_session(root, text="hello"):
    session = Session.create(root)
    session.add_message(HumanMessage(content=text))
    session.add_message(
        ModelMessage(id="m1", content="done", stop_reason="end_turn", usage_data={})
    )
    session.turns[0].memory_extracted = True
    session.save()
    return session


def add_index(manager, session, agent_id, agent_name):
    manager._index[session.id] = SessionIndex(
        session_id=session.id,
        agent_id=agent_id,
        agent_name=agent_name,
        timestamp=session.timestamp,
        turn_count=len(session.turns),
        is_active=True,
        parent_session_id="",
        fork_turn_index=-1,
        session_dir=str(session.dir),
    )


@pytest.mark.asyncio
async def test_fork_at_turn_resets_memory_extracted_for_different_target_agent(tmp_path):
    source = make_complete_session(tmp_path / "agent-a-sessions")
    agents = {
        "agent-a": FakeAgent("A", tmp_path / "agent-a-sessions"),
        "agent-b": FakeAgent("B", tmp_path / "agent-b-sessions"),
    }
    agents["agent-a"].session = source
    manager = SessionManager(FakeAgentFactory(agents))
    add_index(manager, source, "agent-a", "A")

    result = await manager.fork_at_turn(source.id, 0, target_agent_id="agent-b")

    forked = Session.load(
        result["sessionId"],
        agents["agent-b"].session_dir / result["sessionId"],
    )
    assert forked.turns[0].memory_extracted is False


@pytest.mark.asyncio
async def test_fork_at_turn_preserves_memory_extracted_for_same_agent(tmp_path):
    source = make_complete_session(tmp_path / "agent-a-sessions")
    agents = {"agent-a": FakeAgent("A", tmp_path / "agent-a-sessions")}
    agents["agent-a"].session = source
    manager = SessionManager(FakeAgentFactory(agents))
    add_index(manager, source, "agent-a", "A")

    result = await manager.fork_at_turn(source.id, 0, target_agent_id="agent-a")

    forked = Session.load(
        result["sessionId"],
        agents["agent-a"].session_dir / result["sessionId"],
    )
    assert forked.turns[0].memory_extracted is True
