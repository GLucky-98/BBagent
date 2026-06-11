import json

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
        raise AssertionError("Template compatibility tests should not call the model")

    async def async_invoke(self, model_input: Model_Input):
        raise AssertionError("Template compatibility tests should not call the model")

    async def async_stream_invoke(self, model_input: Model_Input):
        raise AssertionError("Template compatibility tests should not call the model")
        yield {}

    def payload_construct(self, model_input: Model_Input) -> dict:
        return {}

    def model_response_parse(self, response: dict):
        return ""


def test_codeteam_template_has_required_shape():
    with open("templates/CodeTeam_template.json", encoding="utf-8") as f:
        data = json.loads(f.read())

    assert data["name"] == "CodeTeam"
    assert isinstance(data["members"], list)
    assert len(data["members"]) >= 2
    assert isinstance(data["contacts"], dict)
    member_names = {member["name"] for member in data["members"]}
    assert set(data["contacts"]).issubset(member_names)
    for owner, contacts in data["contacts"].items():
        assert owner in member_names
        assert owner not in contacts
        assert set(contacts).issubset(member_names)


def test_codeteam_template_can_build_core_team(tmp_path):
    with open("templates/CodeTeam_template.json", encoding="utf-8") as f:
        data = json.loads(f.read())
    agents = {
        member["name"]: Agent(
            AgentConfig(
                model=DummyModel(),
                name=member["name"],
                base_dir=tmp_path,
                system_prompt=member.get("systemPrompt", ""),
            )
        )
        for member in data["members"]
    }

    team = AgentTeam.create(
        TeamConfig(
            name=data["name"],
            team_description=data.get("teamDescription", ""),
            agents=agents,
            contacts=data["contacts"],
        )
    )

    assert team.name == "CodeTeam"
    assert set(team.agents) == set(agents)
    assert any("send_message" in agent.tools for agent in team.agents.values())
