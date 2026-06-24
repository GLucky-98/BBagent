import asyncio

import pytest

from bbagent.core.agent import Agent, AgentConfig, AgentState
from bbagent.core.hook import HookType
from bbagent.core.input import AgentEvent, EventType, InputChannel
from bbagent.core.message import HumanMessage, ModelMessage, ToolMessage, ToolUseBlock
from bbagent.core.model import Model, Model_Input
from bbagent.core.tool import Tool


class ToolUseStreamModel(Model):
    def __init__(self):
        super().__init__(model="dummy", api_key="", base_url="http://localhost")
        self.provider = "dummy"
        self.max_completion_tokens = 1
        self.temperature = 0
        self.top_p = 1
        self.thinking = False
        self.extra_args = {}
        self.headers = {}
        self.tool_use = ToolUseBlock(id="tool-1", name="slow", input={})

    def invoke(self, model_input: Model_Input):
        raise AssertionError("streaming test should not call invoke")

    async def async_invoke(self, model_input: Model_Input):
        raise AssertionError("streaming test should not call async_invoke")

    async def async_stream_invoke(self, model_input: Model_Input):
        yield {"type": "completed_tool_use", "content": self.tool_use}
        yield {
            "type": "completed_message",
            "content": ModelMessage(
                id="model-1",
                content="I will use a tool.",
                stop_reason="tool_use",
                usage_data={},
                tool_calls=[self.tool_use],
            ),
        }

    def payload_construct(self, model_input: Model_Input) -> dict:
        return {}

    def model_response_parse(self, response: dict):
        return ""


class ToolThenEndStreamModel(ToolUseStreamModel):
    def __init__(self):
        super().__init__()
        self.call_count = 0

    async def async_stream_invoke(self, model_input: Model_Input):
        self.call_count += 1
        if self.call_count == 1:
            yield {"type": "completed_tool_use", "content": self.tool_use}
            yield {
                "type": "completed_message",
                "content": ModelMessage(
                    id="model-1",
                    content="I will use a tool.",
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
                content="Done.",
                stop_reason="end_turn",
                usage_data={},
            ),
        }


class CountingEndStreamModel(ToolUseStreamModel):
    def __init__(self):
        super().__init__()
        self.call_count = 0

    async def async_stream_invoke(self, model_input: Model_Input):
        self.call_count += 1
        yield {
            "type": "completed_message",
            "content": ModelMessage(
                id=f"model-{self.call_count}",
                content="Done.",
                stop_reason="end_turn",
                usage_data={},
            ),
        }


class FailingStreamModel(ToolUseStreamModel):
    async def async_stream_invoke(self, model_input: Model_Input):
        raise RuntimeError("model exploded")
        yield {}


@pytest.mark.asyncio
async def test_input_channel_owns_queue_and_ignores_pushes_while_stopped():
    channel = InputChannel()

    channel.push("ignored before start")
    assert channel.queue.empty()

    await channel.start()
    channel.push("accepted")
    event = channel.queue.get_nowait()
    assert event.to_human_message().content[0].text == "accepted"

    channel.push("discarded on stop")
    await channel.stop()
    assert channel.queue.empty()

    channel.push("ignored after stop")
    assert channel.queue.empty()


@pytest.mark.asyncio
async def test_interrupt_during_tool_execution_drops_pending_tool_use_message(tmp_path):
    tool_started = asyncio.Event()
    tool_cancelled = asyncio.Event()
    release_tool = asyncio.Event()

    async def slow_tool() -> str:
        tool_started.set()
        try:
            await release_tool.wait()
        except asyncio.CancelledError:
            tool_cancelled.set()
            raise
        return "done"

    agent = Agent(
        AgentConfig(
            model=ToolUseStreamModel(),
            name="InterruptAgent",
            base_dir=tmp_path,
            tools=[
                Tool(
                    slow_tool,
                    name="slow",
                    description="Slow test tool",
                    input_schema={"type": "object", "properties": {}, "required": []},
                )
            ],
        )
    )

    chunks = []

    async def collect_chunks():
        async for chunk in agent.run(HumanMessage("please run the slow tool")):
            chunks.append(chunk)

    run_task = asyncio.create_task(collect_chunks())
    await asyncio.wait_for(tool_started.wait(), timeout=1)

    await agent.interrupt()
    await asyncio.wait_for(run_task, timeout=1)

    assert tool_cancelled.is_set()
    assert any(chunk["type"] == "interrupted" for chunk in chunks)
    assert not any(chunk["type"] == "tool_results" for chunk in chunks)

    assert agent.session is not None
    assert agent.session.turn_count == 1
    persisted_messages = agent.session.turns[0].messages
    assert len(persisted_messages) == 1
    assert isinstance(persisted_messages[0], HumanMessage)
    assert not any(isinstance(msg, ModelMessage) for msg in persisted_messages)
    assert not any(isinstance(msg, ToolMessage) for msg in persisted_messages)


@pytest.mark.asyncio
async def test_completed_tool_execution_persists_closed_tool_round(tmp_path):
    async def fast_tool() -> str:
        return "done"

    agent = Agent(
        AgentConfig(
            model=ToolThenEndStreamModel(),
            name="CompleteToolAgent",
            base_dir=tmp_path,
            tools=[
                Tool(
                    fast_tool,
                    name="slow",
                    description="Fast test tool",
                    input_schema={"type": "object", "properties": {}, "required": []},
                )
            ],
        )
    )

    chunks = [chunk async for chunk in agent.run(HumanMessage("please run the tool"))]

    assert any(chunk["type"] == "tool_results" for chunk in chunks)
    assert agent.session is not None
    assert agent.session.turn_count == 1
    assert agent.session.turns[0].is_complete
    assert [type(msg).__name__ for msg in agent.session.turns[0].messages] == [
        "HumanMessage",
        "ModelMessage",
        "ToolMessage",
        "ModelMessage",
    ]


@pytest.mark.asyncio
async def test_hook_break_uses_unified_interrupt_signal(tmp_path):
    agent = Agent(
        AgentConfig(
            model=ToolUseStreamModel(),
            name="HookInterruptAgent",
            base_dir=tmp_path,
        )
    )

    @agent.hook.hook(HookType.BEFORE_STREAM)
    def break_before_stream(context):
        context.break_loop()

    chunks = [chunk async for chunk in agent.run(HumanMessage("stop before stream"))]

    assert chunks == [{"type": "interrupted", "content": "Agent interrupted"}]
    assert agent.session is not None
    assert agent.session.turn_count == 1
    assert [type(msg).__name__ for msg in agent.session.turns[0].messages] == [
        "HumanMessage",
    ]


@pytest.mark.asyncio
async def test_stop_interrupts_current_event_and_drops_queued_events(tmp_path):
    model = CountingEndStreamModel()
    first_event_started = asyncio.Event()
    release_first_event = asyncio.Event()

    agent = Agent(
        AgentConfig(
            model=model,
            name="StopDropsQueuedEventsAgent",
            base_dir=tmp_path,
        )
    )

    @agent.hook.hook(HookType.BEFORE_STREAM)
    async def pause_first_event(context):
        first_event_started.set()
        await release_first_event.wait()

    start_task = asyncio.create_task(agent.start())
    for _ in range(10):
        if agent.input._running:
            break
        await asyncio.sleep(0.01)

    agent.input.push("first")
    await asyncio.wait_for(first_event_started.wait(), timeout=1)
    agent.input.push(
        "queued team message",
        source_id="team:Alice",
        event_type=EventType.AGENT_MESSAGE,
    )

    await agent.stop()
    release_first_event.set()
    await asyncio.wait_for(start_task, timeout=1)

    assert model.call_count == 0
    assert agent.session is not None
    assert agent.session.turn_count == 1
    assert len(agent.session.turns[0].messages) == 1
    assert isinstance(agent.session.turns[0].messages[0], HumanMessage)
    assert agent.is_running is False


@pytest.mark.asyncio
async def test_handle_event_emits_user_input_event(tmp_path):
    agent = Agent(
        AgentConfig(
            model=CountingEndStreamModel(),
            name="UserInputEventAgent",
            base_dir=tmp_path,
        )
    )
    chunks = []
    agent.on_output(lambda chunk: chunks.append(dict(chunk)))

    await agent._handle_event(
        AgentEvent(
            type=EventType.USER_MESSAGE,
            source_id="user",
            payload=HumanMessage("hello"),
        )
    )

    input_events = [chunk for chunk in chunks if chunk.get("type") == "input_event"]
    assert input_events == [
        {
            "type": "input_event",
            "event_type": EventType.USER_MESSAGE.value,
            "source_id": "user",
            "content": "hello",
        }
    ]


@pytest.mark.asyncio
async def test_run_preserves_error_state_after_stream_failure(tmp_path):
    agent = Agent(
        AgentConfig(
            model=FailingStreamModel(),
            name="RunFailureAgent",
            base_dir=tmp_path,
        )
    )

    with pytest.raises(RuntimeError, match="model exploded"):
        async for _ in agent.run(HumanMessage("fail")):
            pass

    assert agent.state == AgentState.Error


@pytest.mark.asyncio
async def test_start_preserves_error_state_and_does_not_emit_ready_after_event_failure(tmp_path):
    agent = Agent(
        AgentConfig(
            model=FailingStreamModel(),
            name="LoopFailureAgent",
            base_dir=tmp_path,
        )
    )
    chunks = []
    agent.on_output(lambda chunk: chunks.append(dict(chunk)))

    start_task = asyncio.create_task(agent.start())
    for _ in range(10):
        if agent.input._running:
            break
        await asyncio.sleep(0.01)

    agent.input.push("fail")
    await asyncio.wait_for(start_task, timeout=1)

    assert agent.state == AgentState.Error
    states = [chunk["state"] for chunk in chunks if chunk.get("type") == "agent_state"]
    assert states[-1] == AgentState.Error
    assert AgentState.Ready not in states[states.index(AgentState.Error) + 1:]
