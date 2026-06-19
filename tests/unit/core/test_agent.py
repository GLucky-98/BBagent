"""Baseline tests for bbagent.core.agent — main run loop and lifecycle."""

import asyncio

import pytest

from bbagent.core.agent import Agent, AgentConfig
from bbagent.core.input import AgentEvent, EventType
from bbagent.core.message import (
    HumanMessage,
    ModelMessage,
    TextBlock,
    ToolMessage,
    ToolUseBlock,
)
from bbagent.core.model import Model, Model_Input
from bbagent.core.tool import Tool


class EchoToolModel(Model):
    def __init__(self):
        super().__init__(model="echo", api_key="", base_url="http://localhost")
        self.provider = "dummy"
        self.max_completion_tokens = 1
        self.temperature = 0
        self.top_p = 1
        self.thinking = False
        self.extra_args = {}
        self.headers = {}

    def invoke(self, model_input: Model_Input):
        raise AssertionError("Agent tests use streaming")

    async def async_invoke(self, model_input: Model_Input):
        raise AssertionError("Agent tests use streaming")

    async def async_stream_invoke(self, model_input: Model_Input):
        yield {
            "type": "completed_message",
            "content": ModelMessage(
                id="model-1",
                content="Hello!",
                stop_reason="end_turn",
                usage_data={},
            ),
        }

    def payload_construct(self, model_input: Model_Input) -> dict:
        return {}

    def model_response_parse(self, response: dict):
        return ""


class ToolUseThenEndModel(Model):
    def __init__(self, tool_use: ToolUseBlock):
        super().__init__(model="tool-user", api_key="", base_url="http://localhost")
        self.provider = "dummy"
        self.max_completion_tokens = 1
        self.temperature = 0
        self.top_p = 1
        self.thinking = False
        self.extra_args = {}
        self.headers = {}
        self.tool_use = tool_use
        self.call_count = 0

    def invoke(self, model_input: Model_Input):
        raise AssertionError("Agent tests use streaming")

    async def async_invoke(self, model_input: Model_Input):
        raise AssertionError("Agent tests use streaming")

    async def async_stream_invoke(self, model_input: Model_Input):
        self.call_count += 1
        if self.call_count == 1:
            yield {"type": "completed_tool_use", "content": self.tool_use}
            yield {
                "type": "completed_message",
                "content": ModelMessage(
                    id="model-1",
                    content="Using tool...",
                    stop_reason="tool_use",
                    usage_data={},
                    tool_calls=[self.tool_use],
                ),
            }
            return
        yield {
            "type": "completed_message",
            "content": ModelMessage(
                id="model-2",
                content="Done after tool.",
                stop_reason="end_turn",
                usage_data={},
            ),
        }

    def payload_construct(self, model_input: Model_Input) -> dict:
        return {}

    def model_response_parse(self, response: dict):
        return ""


@pytest.mark.asyncio
async def test_agent_run_produces_completed_message(tmp_path):
    agent = Agent(
        AgentConfig(
            model=EchoToolModel(),
            name="TestAgent",
            base_dir=tmp_path,
            system_prompt="You are a test agent.",
        )
    )

    chunks = []
    async for chunk in agent.run(HumanMessage(content="Hello")):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert chunks[0]["type"] == "completed_message"
    assert chunks[0]["content"].stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_agent_run_with_tool_then_end(tmp_path):
    tool_use = ToolUseBlock(id="call-1", name="greet", input={"name": "World"})

    def greet(name: str) -> str:
        return f"Hello, {name}!"

    tool = Tool(greet, source="built_in")

    agent = Agent(
        AgentConfig(
            model=ToolUseThenEndModel(tool_use),
            name="ToolAgent",
            base_dir=tmp_path,
            system_prompt="You are a tool using agent.",
            tools=[tool],
        )
    )

    chunks = []
    async for chunk in agent.run(HumanMessage(content="Greet World")):
        chunks.append(chunk)

    types = [c["type"] for c in chunks]
    assert types == [
        "completed_tool_use",
        "completed_message",
        "tool_results",
        "completed_message",
    ]


@pytest.mark.asyncio
async def test_agent_add_tools_protects_duplicate_names(tmp_path):
    def a():
        return "a"

    def b():
        return "b"

    agent = Agent(
        AgentConfig(
            model=EchoToolModel(),
            name="DupAgent",
            base_dir=tmp_path,
            tools=[Tool(a, name="shared")],
        )
    )

    with pytest.raises(ValueError, match="Duplicate tool name"):
        agent.add_tools([Tool(b, name="shared")])


def test_agent_construct_model_input_includes_system_prompt(tmp_path):
    agent = Agent(
        AgentConfig(
            model=EchoToolModel(),
            name="PromptAgent",
            base_dir=tmp_path,
            system_prompt="SYSTEM: Be helpful.",
        )
    )

    model_input = agent.construct_model_input()

    assert "SYSTEM: Be helpful." in model_input.prompt


def test_agent_construct_model_input_uses_visible_context(tmp_path):
    agent = Agent(
        AgentConfig(
            model=EchoToolModel(),
            name="ContextAgent",
            base_dir=tmp_path,
            system_prompt="You are helpful.",
        )
    )

    agent._ensure_session()
    agent.session.add_message(HumanMessage(content="First question"))
    agent.session.add_message(
        ModelMessage(id="m1", content=[TextBlock(text="Answer 1")], stop_reason="end_turn", usage_data={})
    )
    agent.session.save()

    model_input = agent.construct_model_input()

    assert len(model_input.messages) > 0


def test_agent_change_system_prompt_updates_file_and_in_memory(tmp_path):
    agent = Agent(
        AgentConfig(
            model=EchoToolModel(),
            name="PromptAgent",
            base_dir=tmp_path,
            system_prompt="Original prompt.",
        )
    )

    agent.change_system_prompt("Updated prompt.")

    assert agent.system_prompt == "Updated prompt."
    assert agent.system_prompt_path.read_text(encoding="utf-8") == "Updated prompt."


def test_agent_session_is_auto_created(tmp_path):
    agent = Agent(
        AgentConfig(
            model=EchoToolModel(),
            name="SessionAgent",
            base_dir=tmp_path,
        )
    )

    agent._ensure_session()

    assert agent.session is not None
    assert agent.session.id
    assert agent.session.dir.exists()


def test_agent_remove_tools(tmp_path):
    def a():
        return "a"

    def b():
        return "b"

    agent = Agent(
        AgentConfig(
            model=EchoToolModel(),
            name="RemoveAgent",
            base_dir=tmp_path,
            tools=[Tool(a, name="tool-a"), Tool(b, name="tool-b")],
        )
    )

    assert "tool-a" in agent.tools
    assert "tool-b" in agent.tools

    agent.remove_tools(["tool-a"])

    assert "tool-a" not in agent.tools
    assert "tool-b" in agent.tools
