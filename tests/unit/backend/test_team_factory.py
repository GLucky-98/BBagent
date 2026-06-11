import json

import pytest

from backend.factories.team_factory import TeamFactory
from bbagent.core.agent import Agent, AgentConfig
from bbagent.core.model import Model, Model_Input
from bbagent.core.team import AgentTeam, TeamConfig


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
        raise AssertionError("Team factory tests should not call the model")

    async def async_invoke(self, model_input: Model_Input):
        raise AssertionError("Team factory tests should not call the model")

    async def async_stream_invoke(self, model_input: Model_Input):
        raise AssertionError("Team factory tests should not call the model")
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


class FakeAgentFactory:
    def __init__(self, agents):
        self.agents = agents
        self.updated = []
        self.deleted = []

    async def update(self, agent_id: str, updates: dict):
        self.updated.append((agent_id, updates))
        agent = self.agents[agent_id]
        if "name" in updates:
            agent.name = updates["name"]
        if "systemPrompt" in updates:
            agent.change_system_prompt(updates["systemPrompt"])
        return agent

    async def delete(self, agent_id: str):
        self.deleted.append(agent_id)
        self.agents.pop(agent_id, None)
        return True


@pytest.mark.asyncio
async def test_update_team_members_removes_member_from_runtime_and_config(tmp_path):
    alice = make_agent("Alice", tmp_path)
    bob = make_agent("Bob", tmp_path)
    agent_factory = FakeAgentFactory({"alice-id": alice, "bob-id": bob})
    team_factory = TeamFactory(tmp_path, agent_factory)
    team_dir = tmp_path / "teams" / "team-id" / "Research"
    team_dir.mkdir(parents=True)

    team = AgentTeam.create(
        TeamConfig(
            name="Research",
            team_description="Coordinate carefully.",
            agents={"Alice": alice, "Bob": bob},
            contacts={"Alice": {"Bob": "Reviewer"}, "Bob": {"Alice": "Lead"}},
        )
    )
    team.base_dir = team_dir
    meta = {
        "id": "team-id",
        "name": "Research",
        "teamDescription": "Coordinate carefully.",
        "workingDir": str(tmp_path),
        "memberIds": ["alice-id", "bob-id"],
        "contacts": {"Alice": {"Bob": "Reviewer"}, "Bob": {"Alice": "Lead"}},
        "started": False,
    }
    (team_dir / "team_config.json").write_text(json.dumps(meta), encoding="utf-8")
    team_factory.teams["team-id"] = team
    team_factory._team_meta["team-id"] = meta

    updated = await team_factory.update(
        "team-id",
        {
            "members": [
                {
                    "name": "Alice",
                    "modelId": "model-id",
                    "systemPrompt": "You are Alice.",
                    "workingDir": str(tmp_path),
                    "toolIds": [],
                    "skillIds": [],
                    "hookNames": [],
                    "hookConfig": {},
                    "toolPolicy": {},
                }
            ],
            "contacts": {"Alice": {}},
            "deleteRemovedMemberIds": ["bob-id"],
        },
    )

    assert updated is team_factory.teams["team-id"]
    assert list(team_factory._team_meta["team-id"]["memberIds"]) == ["alice-id"]
    assert set(team_factory.teams["team-id"].agents) == {"Alice"}
    assert bob.team_prompt == ""
    assert bob.teammate_prompt == ""
    assert "send_message" not in bob.tools
    assert agent_factory.deleted == ["bob-id"]
    assert json.loads((team_dir / "team_config.json").read_text(encoding="utf-8"))["memberIds"] == ["alice-id"]
