"""Baseline tests for TeamConversationManager — conversation lifecycle."""


import pytest

from backend.errors import ConflictError
from backend.factories.team_conversation_factory import TeamConversationManager
from bbagent.core.agent import Agent, AgentConfig
from bbagent.core.model import Model, Model_Input
from bbagent.core.team import AgentTeam, TeamConfig, TeamMessage


class DummyModel(Model):
    def __init__(self):
        super().__init__(model="dummy", api_key="", base_url="http://localhost")
        self.provider = "dummy"
        self.max_completion_tokens = 1
        self.temperature = 0
        self.top_p = 1
        self.thinking = False
        self.extra_args = {}
        self.headers = {}

    def invoke(self, model_input: Model_Input):
        raise AssertionError("Tests should not call the model")

    async def async_invoke(self, model_input: Model_Input):
        raise AssertionError("Tests should not call the model")

    async def async_stream_invoke(self, model_input: Model_Input):
        raise AssertionError("Tests should not call the model")
        yield {}

    def payload_construct(self, model_input: Model_Input) -> dict:
        return {}

    def model_response_parse(self, response: dict):
        return ""


class FakeAgentFactory:
    def __init__(self, agents):
        self.agents = agents
        self.switched = []
        self.new_sessions = []

    async def switch_session(self, agent_id, session_id):
        self.switched.append((agent_id, session_id))

    async def new_session(self, agent_id):
        self.new_sessions.append(agent_id)
        agent = self.agents[agent_id]
        from bbagent.core.message import Session
        agent.session = Session.create(agent.session_dir)


def make_team(tmp_path, agent_factory):
    alice = Agent(
        AgentConfig(
            model=DummyModel(),
            name="Alice",
            base_dir=tmp_path / "alice",
            system_prompt="You are Alice.",
        )
    )
    bob = Agent(
        AgentConfig(
            model=DummyModel(),
            name="Bob",
            base_dir=tmp_path / "bob",
            system_prompt="You are Bob.",
        )
    )

    agent_factory.agents["agent-a"] = alice
    agent_factory.agents["agent-b"] = bob

    from bbagent.core.message import Session
    alice.session = Session.create(alice.session_dir)
    bob.session = Session.create(bob.session_dir)

    team = AgentTeam.create(
        TeamConfig(
            name="PairTeam",
            team_description="Pair programming team",
            agents={"Alice": alice, "Bob": bob},
            contacts={"Alice": {"Bob": "Pair"}, "Bob": {}},
        )
    )
    team.base_dir = tmp_path / "team-data"
    team.base_dir.mkdir(parents=True, exist_ok=True)
    return team


def test_team_message_round_trip():
    msg = TeamMessage(
        from_agent="Alice",
        to_agent="Bob",
        content="Team update",
        type="broadcast",
    )

    data = msg.to_dict()
    restored = TeamMessage.from_dict(data)

    assert restored.from_agent == "Alice"
    assert restored.to_agent == "Bob"
    assert restored.content[0].text == "Team update"
    assert restored.type == "broadcast"


def test_team_message_serialization_includes_all_fields():
    msg = TeamMessage(
        from_agent="Agent1",
        to_agent="Agent2",
        content="Hello",
        type="direct",
    )

    data = msg.to_dict()

    assert data["from_agent"] == "Agent1"
    assert data["to_agent"] == "Agent2"
    assert data["content"][0]["text"] == "Hello"
    assert data["type"] == "direct"
    assert "timestamp" in data


def test_record_message_appends_to_active_conversation(tmp_path):
    agent_factory = FakeAgentFactory({})
    manager = TeamConversationManager(agent_factory)
    team = make_team(tmp_path, agent_factory)

    active = manager.ensure_loaded("team-1", team)

    msg = TeamMessage(
        from_agent="Alice",
        to_agent="Bob",
        content="Hello Bob!",
        type="direct",
    )

    manager.record_message(team, msg.to_dict())

    # read directly from file via conversation_id
    messages = manager.get_messages(team, active["id"])
    assert len(messages) == 1
    assert messages[0]["from_agent"] == "Alice"
    assert messages[0]["to_agent"] == "Bob"
    assert messages[0]["content"][0]["text"] == "Hello Bob!"


@pytest.mark.asyncio
async def test_create_and_list_conversations(tmp_path):
    agent_factory = FakeAgentFactory({})
    manager = TeamConversationManager(agent_factory)
    team = make_team(tmp_path, agent_factory)

    await manager.create_conversation(team, "First Chat")
    conversations = manager.list_conversations(team)

    assert len(conversations) == 1
    assert conversations[0]["name"] == "First Chat"
    assert conversations[0]["active"] is True

    await manager.create_conversation(team, "Second Chat")
    conversations = manager.list_conversations(team)

    assert len(conversations) == 2
    assert conversations[0]["name"] == "Second Chat"
    assert conversations[0]["active"] is True


def test_assert_member_session_switch_allowed_when_team_ready(tmp_path):
    agent_factory = FakeAgentFactory({})
    manager = TeamConversationManager(agent_factory)
    team = make_team(tmp_path, agent_factory)

    # should not raise
    manager.assert_member_session_switch_allowed(team, "agent-a")
    # update_state called internally, both agents are idle
    assert team.state == "ready"


def test_assert_member_session_switch_allowed_raises_when_agent_running_in_conversation(tmp_path):
    agent_factory = FakeAgentFactory({})
    manager = TeamConversationManager(agent_factory)
    team = make_team(tmp_path, agent_factory)

    # make team enter running state
    team.agents["Alice"].state = "running"
    # create an active conversation, Alice is in it
    active = manager.ensure_loaded("team-1", team)
    active["memberSessions"] = {"Alice": "session-alice"}

    with pytest.raises(ConflictError, match="Cannot switch session"):
        manager.assert_member_session_switch_allowed(team, "agent-a")


@pytest.mark.asyncio
async def test_create_conversation_fails_when_team_not_ready(tmp_path):
    agent_factory = FakeAgentFactory({})
    manager = TeamConversationManager(agent_factory)
    team = make_team(tmp_path, agent_factory)

    # make member agent running → update_state() derives as running
    team.agents["Alice"].state = "running"

    with pytest.raises(ConflictError, match="not ready"):
        await manager.create_conversation(team, "Test")


@pytest.mark.asyncio
async def test_delete_conversation_activates_remaining(tmp_path):
    agent_factory = FakeAgentFactory({})
    manager = TeamConversationManager(agent_factory)
    team = make_team(tmp_path, agent_factory)

    await manager.create_conversation(team, "A")
    await manager.create_conversation(team, "B")

    conversations = manager.list_conversations(team)
    active_id = conversations[0]["id"]

    result = await manager.delete_conversation(team, active_id)

    assert result["success"] is True
    remaining = manager.list_conversations(team)
    assert len(remaining) == 1
    assert remaining[0]["name"] == "A"


def test_empty_conversations_list(tmp_path):
    agent_factory = FakeAgentFactory({})
    manager = TeamConversationManager(agent_factory)
    team = make_team(tmp_path, agent_factory)

    conversations = manager.list_conversations(team)

    assert isinstance(conversations, list)
    assert len(conversations) == 0
