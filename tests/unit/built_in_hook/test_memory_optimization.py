import pytest

from bbagent.built_in_hook.memory.fingerprint import (
    extract_seen_memory_keys,
    memory_fingerprint,
)
from bbagent.built_in_hook.memory.memory_hook import (
    INJECT_USER_PREFIX,
    _format_messages_for_extraction,
    create_memory_hook,
)
from bbagent.built_in_hook.memory.memory_tool import create_add_memory_tool, inject_memory_context
from bbagent.built_in_hook.memory.runtime import MemoryRuntime
from bbagent.core.hook import HookContext
from bbagent.core.message import HumanMessage, ModelMessage, Session, TextBlock, ToolUseBlock, Turn
from bbagent.core.model import Model, Model_Input


class DummyLogger:
    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def span(self, _name):
        class Span:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        return Span()

    def trace(self, *args, **kwargs):
        return self.span("trace")

    def set_trace_id(self, *_args, **_kwargs):
        pass

    def clear_trace_id(self):
        pass


class SelectingModel(Model):
    def __init__(self, selected_ids):
        super().__init__(model="selector", api_key="", base_url="http://localhost")
        self.provider = "dummy"
        self.max_completion_tokens = 1
        self.temperature = 0
        self.top_p = 1
        self.thinking = False
        self.extra_args = {}
        self.headers = {}
        self.selected_ids = selected_ids
        self.prompts = []

    def invoke(self, model_input: Model_Input):
        raise AssertionError("Tests use async_invoke")

    async def async_invoke(self, model_input: Model_Input):
        self.prompts.append(model_input.messages[-1].content)
        tool_calls = [
            ToolUseBlock(
                id="select-1",
                name="inject_memories",
                input={"memory_ids": self.selected_ids},
            )
        ]
        return ModelMessage(
            id="selector-1",
            content="selecting",
            stop_reason="tool_use",
            usage_data={},
            tool_calls=tool_calls,
        )

    async def async_stream_invoke(self, model_input: Model_Input):
        raise AssertionError("Tests should not stream")
        yield {}

    def payload_construct(self, model_input: Model_Input) -> dict:
        return {}

    def model_response_parse(self, response: dict):
        return ""


class FakeMemoryManager:
    def __init__(self, memories):
        self.memories = memories
        self.search_sizes = []
        self.accessed = []

    @property
    def count(self):
        return len(self.memories)

    def get_all(self):
        return list(self.memories)

    async def hybrid_search(self, query, n_results, **_kwargs):
        self.search_sizes.append(n_results)
        candidates = self.memories[:n_results]
        return {
            "ids": [c["id"] for c in candidates],
            "documents": [c["content"] for c in candidates],
        }

    def get_by_ids(self, memory_ids):
        by_id = {m["id"]: m["content"] for m in self.memories}
        return [{"id": mid, "content": by_id[mid]} for mid in memory_ids if mid in by_id]

    def increment_access(self, memory_id):
        self.accessed.append(memory_id)


class FakeAddMemoryManager:
    def __init__(self, result):
        self.result = result
        self.saved = []

    async def add_memories(self, memories):
        self.saved.extend(memories)
        return self.result


class RecordingRuntime(MemoryRuntime):
    def __init__(self):
        super().__init__(logger=DummyLogger())
        self.scheduled = []

    def schedule(self, coro, name: str):
        self.scheduled.append((name, coro))
        coro.close()
        return None


class FakeAgent:
    def __init__(self, session):
        self.session = session
        self.model = type("AgentModel", (), {"max_context_tokens": 1000})()
        self.logger = DummyLogger()


def complete_turn(content, memory_extracted: bool = False) -> Turn:
    return Turn(
        messages=[
            HumanMessage(content=content),
            ModelMessage(id="m", content="done", stop_reason="end_turn", usage_data={}),
        ],
        memory_extracted=memory_extracted,
    )


@pytest.mark.asyncio
async def test_agent_add_memory_marks_current_turn_extracted_when_saved():
    session = Session(id="session-1")
    session.turns = [Turn(messages=[HumanMessage(content="remember this")])]
    manager = FakeAddMemoryManager(
        {"added_count": 1, "skipped_duplicates": 0, "failed_count": 0}
    )

    tool = create_add_memory_tool(
        manager,
        lambda: session.id,
        mark_current_turn_extracted=lambda: setattr(session.turns[-1], "memory_extracted", True),
    )

    await tool.async_invoke({"memories": ["User prefers dark mode."]})

    assert session.turns[-1].memory_extracted is True
    assert manager.saved[0].session_id == "session-1"


@pytest.mark.asyncio
async def test_agent_add_memory_marks_current_turn_extracted_when_duplicate_exists():
    session = Session(id="session-1")
    session.turns = [Turn(messages=[HumanMessage(content="remember this")])]
    manager = FakeAddMemoryManager(
        {"added_count": 0, "skipped_duplicates": 1, "failed_count": 0}
    )

    tool = create_add_memory_tool(
        manager,
        lambda: session.id,
        mark_current_turn_extracted=lambda: setattr(session.turns[-1], "memory_extracted", True),
    )

    await tool.async_invoke({"memories": ["User prefers dark mode."]})

    assert session.turns[-1].memory_extracted is True


@pytest.mark.asyncio
async def test_agent_add_memory_does_not_mark_current_turn_when_save_failed_or_callback_missing():
    failed_session = Session(id="session-1")
    failed_session.turns = [Turn(messages=[HumanMessage(content="remember this")])]
    failed_manager = FakeAddMemoryManager(
        {"added_count": 0, "skipped_duplicates": 0, "failed_count": 1}
    )
    failed_tool = create_add_memory_tool(
        failed_manager,
        lambda: failed_session.id,
        mark_current_turn_extracted=lambda: setattr(
            failed_session.turns[-1], "memory_extracted", True
        ),
    )

    await failed_tool.async_invoke({"memories": ["User prefers dark mode."]})

    assert failed_session.turns[-1].memory_extracted is False

    subagent_session = Session(id="session-2")
    subagent_session.turns = [Turn(messages=[HumanMessage(content="remember this")])]
    subagent_tool = create_add_memory_tool(
        FakeAddMemoryManager({"added_count": 1, "skipped_duplicates": 0, "failed_count": 0}),
        lambda: subagent_session.id,
    )

    await subagent_tool.async_invoke({"memories": ["User prefers dark mode."]})

    assert subagent_session.turns[-1].memory_extracted is False


@pytest.mark.asyncio
async def test_inject_memory_context_filters_seen_memories_and_oversamples():
    seen_content = "User prefers dark mode."
    manager = FakeMemoryManager(
        [
            {"id": "1", "content": seen_content},
            {"id": "2", "content": "User works with FastAPI."},
            {"id": "3", "content": "User likes compact answers."},
            {"id": "4", "content": "User debugs async services."},
        ]
    )
    model = SelectingModel(["2"])

    context = await inject_memory_context(
        query="What stack do I use?",
        memory_manager=manager,
        submodel=model,
        max_candidates=1,
        seen_memory_keys={memory_fingerprint(seen_content)},
        selected_memory_keys=[],
        oversample_factor=3,
        logger=DummyLogger(),
    )

    assert manager.search_sizes == [3]
    prompt_text = " ".join(block.text for block in model.prompts[0] if isinstance(block, TextBlock))
    assert "[ID: 1]" not in prompt_text
    assert "[ID: 2]" in prompt_text
    assert context == "- User works with FastAPI."
    assert manager.accessed == ["2"]


def test_runtime_recovers_seen_memory_keys_from_session_prefix_incrementally():
    prefix = INJECT_USER_PREFIX.split("{search_context}", 1)[0]
    session = Session(id="session-1")
    session.turns = [
        complete_turn(
            "[Relevant memories from past messages]\n"
            "- User prefers dark mode.\n\n"
            "What should we build?"
        )
    ]
    runtime = MemoryRuntime(logger=DummyLogger())

    seen = runtime.get_seen_memory_keys(session, prefix)
    assert memory_fingerprint("User prefers dark mode.") in seen

    session.turns.append(
        complete_turn(
            [
                TextBlock(
                    text="[Relevant memories from past messages]\n"
                    "- User works with FastAPI.\n\n"
                ),
                TextBlock(text="Continue."),
            ]
        )
    )

    seen = runtime.get_seen_memory_keys(session, prefix)
    assert memory_fingerprint("User works with FastAPI.") in seen
    assert len(seen) == 2


def test_extract_seen_memory_keys_parses_only_prefixed_user_messages():
    session = Session(id="session-1")
    session.turns = [
        complete_turn("No prefix\n- User prefers dark mode."),
        complete_turn(
            "[Relevant memories from past messages]\n"
            "- User works with FastAPI.\n\n"
            "Question"
        ),
    ]

    seen = extract_seen_memory_keys(
        session,
        INJECT_USER_PREFIX.split("{search_context}", 1)[0],
    )

    assert memory_fingerprint("User works with FastAPI.") in seen
    assert memory_fingerprint("User prefers dark mode.") not in seen


def test_memory_extraction_format_skips_system_origin_blocks():
    messages = [
        HumanMessage(
            content=[
                TextBlock(text="[Relevant memories]\n- Already injected", origin="system"),
                TextBlock(text="My real request", origin="user"),
            ]
        )
    ]

    formatted = _format_messages_for_extraction(messages)

    assert "My real request" in formatted
    assert "Already injected" not in formatted


@pytest.mark.asyncio
async def test_memory_injection_uses_system_origin_block():
    runtime = MemoryRuntime(logger=DummyLogger())
    session = Session(id="session-1")
    session.turns = [Turn(messages=[HumanMessage(content="What do I like?")])]
    agent = FakeAgent(session)
    ctx = HookContext()
    ctx.agent = agent

    hooks = create_memory_hook(
        memory_manager=FakeMemoryManager([{"id": "1", "content": "User likes tests."}]),
        submodel=SelectingModel(["1"]),
        runtime=runtime,
    )
    inject_memory_hook = hooks[3]

    await inject_memory_hook(ctx)

    content = session.turns[-1].messages[0].content
    assert content[0].origin == "system"
    assert content[0].text.startswith("[Relevant memories from past messages]")
    assert content[1].origin == "user"
    assert content[1].text == "What do I like?"


@pytest.mark.asyncio
async def test_after_run_interval_claims_and_schedules_complete_unextracted_turns():
    runtime = RecordingRuntime()
    session = Session(id="session-1")
    session.turns = [complete_turn(f"turn {i}") for i in range(5)]
    agent = FakeAgent(session)
    ctx = HookContext()
    ctx.agent = agent

    hooks = create_memory_hook(
        memory_manager=FakeMemoryManager([]),
        submodel=SelectingModel([]),
        runtime=runtime,
        extract_turn_interval=5,
    )
    extract_after_interval = hooks[-1]

    await extract_after_interval(ctx)

    assert len(runtime.scheduled) == 1
    assert runtime.scheduled[0][0] == "memory_extract_interval:session-1"
    assert runtime.inflight_turns == {("session-1", i) for i in range(5)}


@pytest.mark.asyncio
async def test_after_run_interval_does_not_claim_when_below_threshold():
    runtime = RecordingRuntime()
    session = Session(id="session-1")
    session.turns = [complete_turn(f"turn {i}") for i in range(4)]
    agent = FakeAgent(session)
    ctx = HookContext()
    ctx.agent = agent

    hooks = create_memory_hook(
        memory_manager=FakeMemoryManager([]),
        submodel=SelectingModel([]),
        runtime=runtime,
        extract_turn_interval=5,
    )
    extract_after_interval = hooks[-1]

    await extract_after_interval(ctx)

    assert not runtime.scheduled
    assert not runtime.inflight_turns
