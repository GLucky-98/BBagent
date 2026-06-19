import json

import pytest

from backend.factories import _builtin_tool_id
from backend.factories.agent_factory import AgentFactory
from backend.factories.tool_factory import ToolFactory
from backend.schemas import AgentConfig
from bbagent.core.model import Model, Model_Input


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
        raise AssertionError("Agent factory policy tests should not call the model")

    async def async_invoke(self, model_input: Model_Input):
        raise AssertionError("Agent factory policy tests should not call the model")

    async def async_stream_invoke(self, model_input: Model_Input):
        raise AssertionError("Agent factory policy tests should not call the model")
        yield {}

    def payload_construct(self, model_input: Model_Input) -> dict:
        return {}

    def model_response_parse(self, response: dict):
        return ""


class FakeModelFactory:
    def __init__(self):
        self.model = DummyModel()
        self.acquired_submodels: list[str] = []

    def acquire(self, model_id: str):
        return self.model

    def acquire_submodel(self, model_id: str):
        self.acquired_submodels.append(model_id)
        return self.model

    async def release(self, model_id: str):
        return None


class EmptyFactory:
    pass


@pytest.mark.asyncio
async def test_update_working_dir_refreshes_builtin_tool_instance_cache(tmp_path):
    old_cwd = tmp_path / "old"
    new_cwd = tmp_path / "new"
    old_cwd.mkdir()
    new_cwd.mkdir()
    (old_cwd / "marker.txt").write_text("old cwd", encoding="utf-8")
    (new_cwd / "marker.txt").write_text("new cwd", encoding="utf-8")

    tool_factory = ToolFactory(tmp_path / "data")
    tool_factory.load_builtins()
    agent_factory = AgentFactory(
        tmp_path / "data",
        FakeModelFactory(),
        tool_factory,
        EmptyFactory(),
        EmptyFactory(),
    )
    read_tool_id = _builtin_tool_id("read")

    agent = await agent_factory.create(
        AgentConfig(
            id="agent-1",
            name="PolicyAgent",
            modelId="model-1",
            workingDir=str(old_cwd),
            toolIds=[read_tool_id],
        )
    )
    await agent_factory._lazy_init("agent-1")
    old_tool = agent.tools["read"]

    await agent_factory.update("agent-1", {"workingDir": str(new_cwd)})

    refreshed_tool = agent.tools["read"]
    cached_tool = agent_factory._tool_instances["agent-1"][read_tool_id]
    assert refreshed_tool is cached_tool
    assert refreshed_tool is not old_tool
    assert "new cwd" in cached_tool.invoke({"path": "marker.txt"})
    assert "old cwd" not in cached_tool.invoke({"path": "marker.txt"})


@pytest.mark.asyncio
async def test_agent_config_json_does_not_persist_redundant_type_field(tmp_path):
    agent_factory = AgentFactory(
        tmp_path / "data",
        FakeModelFactory(),
        ToolFactory(tmp_path / "data"),
        EmptyFactory(),
        EmptyFactory(),
    )

    agent = await agent_factory.create(
        AgentConfig(
            id="agent-1",
            name="PlainAgent",
            modelId="model-1",
        )
    )

    persisted = json.loads((agent.base_dir / "agent_config.json").read_text(encoding="utf-8"))

    assert "type" not in persisted


@pytest.mark.asyncio
async def test_sub_agent_without_sub_model_falls_back_to_main_model_on_lazy_init(tmp_path):
    tool_factory = ToolFactory(tmp_path / "data")
    tool_factory.load_builtins()
    model_factory = FakeModelFactory()
    agent_factory = AgentFactory(
        tmp_path / "data",
        model_factory,
        tool_factory,
        EmptyFactory(),
        EmptyFactory(),
    )
    sub_agent_tool_id = _builtin_tool_id("sub_agent")

    agent = await agent_factory.create(
        AgentConfig(
            id="agent-1",
            name="SubAgent",
            modelId="main-model",
            toolIds=[sub_agent_tool_id],
            toolPolicy={},
        )
    )

    await agent_factory._lazy_init("agent-1")

    assert "main-model" in model_factory.acquired_submodels
    result = await agent.tools["sub_agent"].async_invoke(
        {"task": "say hi", "system_prompt": "be brief", "allowed_tools": []}
    )
    assert result.startswith("Error: Failed to create sub-agent model:")
    assert "No sub-agent model configured" not in result


@pytest.mark.asyncio
async def test_adding_sub_agent_without_sub_model_falls_back_to_main_model(tmp_path):
    tool_factory = ToolFactory(tmp_path / "data")
    tool_factory.load_builtins()
    model_factory = FakeModelFactory()
    agent_factory = AgentFactory(
        tmp_path / "data",
        model_factory,
        tool_factory,
        EmptyFactory(),
        EmptyFactory(),
    )
    sub_agent_tool_id = _builtin_tool_id("sub_agent")

    agent = await agent_factory.create(
        AgentConfig(
            id="agent-1",
            name="SubAgent",
            modelId="main-model",
            toolIds=[],
            toolPolicy={},
        )
    )

    await agent_factory.update("agent-1", {"toolIds": [sub_agent_tool_id]})

    assert "main-model" in model_factory.acquired_submodels
    result = await agent.tools["sub_agent"].async_invoke(
        {"task": "say hi", "system_prompt": "be brief", "allowed_tools": []}
    )
    assert result.startswith("Error: Failed to create sub-agent model:")
    assert "No sub-agent model configured" not in result


@pytest.mark.asyncio
async def test_changing_main_model_refreshes_default_sub_agent_model(tmp_path):
    tool_factory = ToolFactory(tmp_path / "data")
    tool_factory.load_builtins()
    model_factory = FakeModelFactory()
    agent_factory = AgentFactory(
        tmp_path / "data",
        model_factory,
        tool_factory,
        EmptyFactory(),
        EmptyFactory(),
    )
    sub_agent_tool_id = _builtin_tool_id("sub_agent")

    await agent_factory.create(
        AgentConfig(
            id="agent-1",
            name="SubAgent",
            modelId="old-main-model",
            toolIds=[sub_agent_tool_id],
            toolPolicy={},
        )
    )
    await agent_factory._lazy_init("agent-1")
    model_factory.acquired_submodels.clear()

    await agent_factory.update("agent-1", {"modelId": "new-main-model"})

    assert "new-main-model" in model_factory.acquired_submodels


@pytest.mark.asyncio
async def test_changing_main_model_updates_config_and_persistence(tmp_path):
    agent_factory = AgentFactory(
        tmp_path / "data",
        FakeModelFactory(),
        ToolFactory(tmp_path / "data"),
        EmptyFactory(),
        EmptyFactory(),
    )

    agent = await agent_factory.create(
        AgentConfig(
            id="agent-1",
            name="ModelSwitchAgent",
            modelId="old-main-model",
        )
    )

    await agent_factory.update("agent-1", {"modelId": "new-main-model"})

    cfg = agent_factory.get_agent_config("agent-1")
    persisted = json.loads((agent.base_dir / "agent_config.json").read_text(encoding="utf-8"))

    assert agent_factory._model_ids["agent-1"] == "new-main-model"
    assert cfg.modelId == "new-main-model"
    assert persisted["modelId"] == "new-main-model"
