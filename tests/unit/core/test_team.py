import pytest

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
        raise AssertionError("Team communication tests should not call the model")

    async def async_invoke(self, model_input: Model_Input):
        raise AssertionError("Team communication tests should not call the model")

    async def async_stream_invoke(self, model_input: Model_Input):
        raise AssertionError("Team communication tests should not call the model")
        yield {}

    def payload_construct(self, model_input: Model_Input) -> dict:
        return {}

    def model_response_parse(self, response: dict):
        return ""


def make_agent(name: str, tmp_path):
    return Agent(
        AgentConfig(
            model=DummyModel(),
            name=name,
            base_dir=tmp_path,
            system_prompt=f"You are {name}.",
        )
    )


@pytest.mark.asyncio
async def test_team_injects_tools_only_for_visible_contacts(tmp_path):
    alice = make_agent("Alice", tmp_path)
    bob = make_agent("Bob", tmp_path)
    carol = make_agent("Carol", tmp_path)

    team = AgentTeam.create(
        TeamConfig(
            name="Research",
            team_description="Coordinate carefully.",
            agents={"Alice": alice, "Bob": bob, "Carol": carol},
            contacts={"Alice": {"Bob": "Reviewer"}, "Bob": {}, "Carol": {"Alice": "Lead"}},
        )
    )

    assert set(team.agents) == {"Alice", "Bob", "Carol"}
    assert {"send_message", "broadcast"} <= set(alice.tools)
    assert "send_message" not in bob.tools
    assert {"send_message", "broadcast"} <= set(carol.tools)
    assert "Bob: Reviewer" in alice.teammate_prompt
    assert alice.team_prompt.startswith("[Team Context]")


@pytest.mark.asyncio
async def test_send_message_respects_contacts_and_records_message(tmp_path):
    alice = make_agent("Alice", tmp_path)
    bob = make_agent("Bob", tmp_path)
    carol = make_agent("Carol", tmp_path)
    team_dir = tmp_path / "team"
    team_dir.mkdir()

    team = AgentTeam.create(
        TeamConfig(
            name="Research",
            team_description="",
            agents={"Alice": alice, "Bob": bob, "Carol": carol},
            contacts={"Alice": {"Bob": "Reviewer"}, "Bob": {"Alice": "Lead"}, "Carol": {}},
        )
    )
    team.base_dir = team_dir

    ok = await alice.tools["send_message"].async_invoke({"to_agent": "Bob", "message": "Please review."})
    blocked = await alice.tools["send_message"].async_invoke({"to_agent": "Carol", "message": "Secret."})

    assert ok == "Message sent to Bob"
    assert blocked == "Error: 'Carol' is not in your contacts"
    assert len(team._team_messages) == 1
    assert team._team_messages[0].from_agent == "Alice"
    assert team._team_messages[0].to_agent == "Bob"
    assert team._team_messages[0].content == "Please review."


@pytest.mark.asyncio
async def test_broadcast_sends_to_visible_contacts_only(tmp_path):
    alice = make_agent("Alice", tmp_path)
    bob = make_agent("Bob", tmp_path)
    carol = make_agent("Carol", tmp_path)
    team = AgentTeam.create(
        TeamConfig(
            name="Research",
            team_description="",
            agents={"Alice": alice, "Bob": bob, "Carol": carol},
            contacts={"Alice": {"Bob": "Reviewer", "Carol": "Tester"}},
        )
    )

    result = await alice.tools["broadcast"].async_invoke({"message": "Status?"})

    assert result == "Broadcast sent to 2 agents"
    assert team._team_messages[-1].type == "broadcast"
    assert team._team_messages[-1].to_agent == "Bob,Carol"


def test_team_message_round_trip_preserves_content_blocks():
    msg = TeamMessage(from_agent="Alice", to_agent="Bob", content="hello", type="direct", timestamp=123)

    restored = TeamMessage.from_dict(msg.to_dict())

    assert restored.from_agent == "Alice"
    assert restored.to_agent == "Bob"
    assert restored.content == "hello"
    assert restored.type == "direct"
    assert restored.timestamp == 123
