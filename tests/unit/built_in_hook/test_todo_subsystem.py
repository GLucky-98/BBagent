import pytest

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

    assert first.completed_and_cleared is False
    assert second.completed_and_cleared is True
    assert "Todo list completed and cleared." in second.message
    assert manager.current() is None


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
    assert runtime.dirty is True
    assert runtime.version == 1

    done_result = await tools["todo_update"].async_invoke({
        "item_id": "a",
        "status": "done",
    })
    assert "Todo list completed and cleared." in done_result
    assert runtime.version == 2


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
        inject_after_input,
        remind_before_stream,
        emit_on_tool_result,
        _clear_on_new_session,
        _cleanup_after_run,
        todo_context_provider,
    ) = create_todo_hook(manager, runtime)

    await inject_after_input(ctx)
    assert session.turns[-1].messages[0].content == "continue"
    assert todo_context_provider().startswith("[Current Todo List]")

    manager.update_item("a", status="in_progress")
    runtime.mark_dirty()
    await remind_before_stream(ctx)
    assert session.turns[-1].messages[0].content == "continue"
    assert "In progress:" in todo_context_provider()

    await emit_on_tool_result(ctx, ToolMessage("tool-1", "todo_update", "ok"))

    assert agent.emitted[-1]["type"] == "todo_list"
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


def test_agent_runtime_context_is_transient_and_does_not_mutate_session(tmp_path):
    agent = Agent(AgentConfig(model=DummyModel(), name="TodoAgent", base_dir=tmp_path))
    agent.session = Session(id="session-1")
    agent.session.turns = [Turn(messages=[HumanMessage(content="do work")])]
    agent.runtime_context_providers.append(lambda: "[Current Todo List]\n- a: A\n[End Current Todo List]")

    model_input = agent.construct_model_input()

    assert model_input.messages[-1].content.startswith("[Current Todo List]")
    assert agent.session.turns[-1].messages[0].content == "do work"
