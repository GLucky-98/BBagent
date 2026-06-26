import pytest

from bbagent.built_in_hook import _setup_todo
from bbagent.built_in_hook.todo import (
    TodoItemInput,
    TodoManager,
    TodoRuntime,
    create_todo_hook,
    create_todo_tools,
)
from bbagent.core.agent import Agent, AgentConfig
from bbagent.core.hook import HookContext
from bbagent.core.message import HumanMessage, Session, ToolMessage, Turn
from bbagent.core.model import Model, Model_Input


def test_todo_manager_blocks_and_unblocks_dependencies():
    manager = TodoManager()

    result = manager.create_list(
        "Implement todo subsystem",
        [
            TodoItemInput(id="manager", content="Implement manager"),
            TodoItemInput(
                id="tests",
                content="Run tests",
                blocked_by=["manager"],
            ),
        ],
    )

    assert result.changed is True
    snapshot = manager.snapshot()
    assert snapshot["summary"]["pending"] == 1
    assert snapshot["summary"]["blocked"] == 1
    assert snapshot["items"][1]["status"] == "blocked"
    assert snapshot["items"][1]["ready"] is False

    update = manager.update_item("manager", status="done")

    assert update.changed is True
    snapshot = manager.snapshot()
    assert snapshot["items"][1]["status"] == "pending"
    assert snapshot["items"][1]["ready"] is True


def test_todo_manager_rejects_invalid_dependencies_and_cycles():
    manager = TodoManager()

    missing = manager.create_list(
        "Bad deps",
        [TodoItemInput(id="a", content="A", blocked_by=["missing"])],
    )
    assert missing.changed is False
    assert "unknown dependencies" in missing.message

    cycle = manager.create_list(
        "Cycle",
        [
            TodoItemInput(id="a", content="A", blocked_by=["b"]),
            TodoItemInput(id="b", content="B", blocked_by=["a"]),
        ],
    )
    assert cycle.changed is False
    assert "cycle" in cycle.message


def test_todo_manager_rejects_starting_blocked_item():
    manager = TodoManager()
    manager.create_list(
        "Blocked work",
        [
            TodoItemInput(id="a", content="A"),
            TodoItemInput(id="b", content="B", blocked_by=["a"]),
        ],
    )

    result = manager.update_item("b", status="in_progress")

    assert result.changed is False
    assert "blocked by unfinished items: a" in result.message


def test_todo_manager_clears_when_all_items_terminal():
    manager = TodoManager()
    manager.create_list(
        "Finish",
        [
            TodoItemInput(id="a", content="A"),
            TodoItemInput(id="b", content="B"),
        ],
    )

    first = manager.update_item("a", status="done")
    second = manager.update_item("b", status="cancelled")

    assert first.changed is True
    assert second.changed is True
    assert "Todo list completed and cleared." in second.message
    assert manager.current() is None


def _text_blocks(message):
    return [block for block in message.content if hasattr(block, "text")]


@pytest.mark.asyncio
async def test_todo_tools_mark_runtime_dirty_and_report_completion():
    manager = TodoManager()
    runtime = TodoRuntime()
    tools = {tool.name: tool for tool in create_todo_tools(manager, runtime)}

    create_result = await tools["todo_create"].async_invoke({
        "title": "Tool list",
        "items": [{"id": "a", "content": "A"}],
    })
    assert "Created todo list" in create_result
    assert "[Current Todo List]" in create_result
    assert "a: A" in create_result
    assert runtime.dirty is True
    assert runtime.version == 1
    assert runtime.stream_count_since_inject == 0

    done_result = await tools["todo_update"].async_invoke({
        "item_id": "a",
        "status": "done",
    })
    assert "Todo list completed and cleared." in done_result
    assert "No active todo list." in done_result
    assert runtime.version == 2
    assert runtime.stream_count_since_inject == 0


@pytest.mark.asyncio
async def test_failed_todo_tool_call_does_not_mark_runtime_dirty():
    manager = TodoManager()
    runtime = TodoRuntime()
    tools = {tool.name: tool for tool in create_todo_tools(manager, runtime)}

    result = await tools["todo_create"].async_invoke({
        "title": "Bad dependencies",
        "items": [{"id": "a", "content": "A", "blocked_by": ["missing"]}],
    })

    assert "unknown dependencies" in result
    assert runtime.dirty is False
    assert runtime.version == 0


def test_todo_create_schema_describes_inputs():
    manager = TodoManager()
    runtime = TodoRuntime()
    tools = {tool.name: tool for tool in create_todo_tools(manager, runtime)}
    schema = tools["todo_create"].input_schema

    assert "Input fields:" in tools["todo_create"].description
    item_schema = schema["properties"]["items"]["items"]
    assert "notes" not in item_schema["properties"]
    assert "Short stable id" in item_schema["properties"]["id"]["description"]
    assert "actual work item" in item_schema["properties"]["content"]["description"]
    assert "must be done or cancelled" in item_schema["properties"]["blocked_by"]["description"]


class FakeAgent:
    def __init__(self, session):
        self.session = session
        self.emitted = []

    async def _emit(self, chunk):
        self.emitted.append(chunk)


@pytest.mark.asyncio
async def test_todo_hooks_inject_context_and_emit_dirty_snapshot():
    manager = TodoManager()
    runtime = TodoRuntime()
    manager.create_list(
        "Hook list",
        [TodoItemInput(id="a", content="A")],
    )
    runtime.mark_dirty()

    session = Session(id="session-1")
    session.turns = [Turn(messages=[HumanMessage(content="continue")])]
    agent = FakeAgent(session)
    ctx = HookContext()
    ctx.agent = agent

    (
        remind_before_stream,
        emit_on_tool_result,
        _clear_on_new_session,
        _cleanup_after_run,
    ) = create_todo_hook(manager, runtime, stream_inject_interval=0)

    await remind_before_stream(ctx)
    blocks = _text_blocks(session.turns[-1].messages[0])
    assert blocks[0].text.startswith("[Current Todo List]")
    assert blocks[0].origin == "system"
    assert blocks[1].text == "continue"
    assert runtime.stream_count_since_inject == 0

    await emit_on_tool_result(ctx, ToolMessage("tool-1", "todo_update", "ok"))

    assert agent.emitted[-1]["type"] == "stream_chunk"
    assert agent.emitted[-1]["chunk_type"] == "todo_list"
    assert agent.emitted[-1]["content"]["title"] == "Hook list"
    assert runtime.dirty is False


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
        raise AssertionError("not used")

    async def async_invoke(self, model_input: Model_Input):
        raise AssertionError("not used")

    async def async_stream_invoke(self, model_input: Model_Input):
        raise AssertionError("not used")
        yield {}

    def payload_construct(self, model_input: Model_Input) -> dict:
        return {}

    def model_response_parse(self, response: dict):
        return ""


def test_agent_construct_model_input_does_not_use_runtime_context_provider(tmp_path):
    agent = Agent(AgentConfig(model=DummyModel(), name="TodoAgent", base_dir=tmp_path))
    agent.session = Session(id="session-1")
    agent.session.turns = [Turn(messages=[HumanMessage(content="do work")])]

    model_input = agent.construct_model_input()

    session_blocks = _text_blocks(agent.session.turns[-1].messages[0])
    input_blocks = _text_blocks(model_input.messages[-1])
    assert input_blocks[0].text == "do work"
    assert session_blocks[0].text == "do work"
    assert session_blocks[0].origin == "user"


def test_setup_todo_sets_runtime_prompt_without_changing_base_system_prompt(tmp_path):
    agent = Agent(
        AgentConfig(
            model=DummyModel(),
            name="TodoSetupAgent",
            base_dir=tmp_path,
            system_prompt="Base prompt.",
        )
    )

    _setup_todo(agent)

    assert agent.system_prompt == "Base prompt."
    assert "built_in.todo" in agent.runtime_prompts
    assert "Runtime Todo System" in agent.construct_model_input().prompt
    assert "Runtime Todo System" in agent.runtime_prompts_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Throttle tests — BEFORE_STREAM injects only after the stream counter exceeds
# the configured interval.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_interval_throttles_unchanged_todo():
    """Unchanged todo is throttled by interval, injects on 4th stream when interval=3."""
    manager = TodoManager()
    runtime = TodoRuntime()
    manager.create_list(
        "Test",
        [TodoItemInput(id="a", content="A")],
    )
    runtime.mark_dirty()

    (
        remind_before_stream,
        _, _, _,
    ) = create_todo_hook(manager, runtime, stream_inject_interval=3)

    ctx = HookContext()
    session = Session(id="s")
    session.turns = [Turn(messages=[HumanMessage(content="continue")])]
    ctx.agent = FakeAgent(session)

    # 1st BEFORE_STREAM: counter 1, 1 <= 3, no injection
    await remind_before_stream(ctx)
    assert runtime.stream_count_since_inject == 1
    assert _text_blocks(session.turns[-1].messages[-1])[0].text == "continue"

    # 2nd BEFORE_STREAM: counter 2, 2 <= 3, no injection
    await remind_before_stream(ctx)
    assert runtime.stream_count_since_inject == 2
    assert _text_blocks(session.turns[-1].messages[-1])[0].text == "continue"

    # 3rd BEFORE_STREAM: counter 3, 3 <= 3, no injection
    await remind_before_stream(ctx)
    assert runtime.stream_count_since_inject == 3
    assert _text_blocks(session.turns[-1].messages[-1])[0].text == "continue"

    # 4th BEFORE_STREAM: counter 4, 4 > 3, inject and reset
    await remind_before_stream(ctx)
    blocks = _text_blocks(session.turns[-1].messages[-1])
    assert blocks[0].text.startswith("[Current Todo List]")
    assert blocks[0].origin == "system"
    assert runtime.stream_count_since_inject == 0


@pytest.mark.asyncio
async def test_before_stream_can_inject_into_last_tool_message():
    manager = TodoManager()
    runtime = TodoRuntime()
    manager.create_list(
        "Test",
        [TodoItemInput(id="a", content="A")],
    )

    (
        remind_before_stream,
        _, _, _,
    ) = create_todo_hook(manager, runtime, stream_inject_interval=0)

    session = Session(id="s")
    session.turns = [
        Turn(messages=[
            HumanMessage(content="continue"),
            ToolMessage("tool-1", "read", "tool output"),
        ])
    ]
    ctx = HookContext()
    ctx.agent = FakeAgent(session)

    await remind_before_stream(ctx)

    blocks = _text_blocks(session.turns[-1].messages[-1])
    assert blocks[0].text.startswith("[Current Todo List]")
    assert blocks[0].origin == "system"
    assert blocks[1].text == "tool output"
    assert blocks[1].origin == "tool"


@pytest.mark.asyncio
async def test_todo_tool_results_reset_before_stream_counter():
    manager = TodoManager()
    runtime = TodoRuntime()
    tools = {tool.name: tool for tool in create_todo_tools(manager, runtime)}

    runtime.stream_count_since_inject = 5
    result = await tools["todo_create"].async_invoke({
        "title": "Test",
        "items": [{"id": "a", "content": "A"}],
    })

    assert "[Current Todo List]" in result
    assert runtime.stream_count_since_inject == 0


@pytest.mark.asyncio
async def test_no_active_todo_no_injection():
    """No injection when there is no active todo, stream counter is reset."""
    manager = TodoManager()
    runtime = TodoRuntime()
    runtime.stream_count_since_inject = 3

    (
        remind_before_stream,
        _, _, _,
    ) = create_todo_hook(manager, runtime)

    ctx = HookContext()
    ctx.agent = FakeAgent(Session(id="s"))

    await remind_before_stream(ctx)
    assert runtime.stream_count_since_inject == 0
