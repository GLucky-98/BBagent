"""Baseline tests for ctx_compress_hook — context compression behaviors."""

import pytest

from bbagent.built_in_hook.ctx_compress_hook import (
    create_ctx_compress_hook,
    compress_session,
)
from bbagent.core.message import (
    HumanMessage,
    ModelMessage,
    Session,
    TextBlock,
    ToolUseBlock,
)


class CompressModel:
    """Fake model that returns a fixed compression summary."""
    def __init__(self, summary="Compressed summary.", max_context_tokens=200000):
        self.summary = summary
        self.max_context_tokens = max_context_tokens
        self.invocations = 0
        self.max_completion_tokens = 4096

    def invoke(self, model_input):
        raise AssertionError("Tests use async_invoke")

    async def async_invoke(self, model_input):
        self.invocations += 1
        return ModelMessage(
            id=f"compress-{self.invocations}",
            content=self.summary,
            stop_reason="end_turn",
            usage_data={},
        )

    async def async_stream_invoke(self, model_input):
        raise AssertionError("Tests should not stream")
        yield {}

    def payload_construct(self, model_input):
        return {}

    def model_response_parse(self, response):
        return ""


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

    def set_trace_id(self, *_args, **_kwargs):
        pass

    def clear_trace_id(self):
        pass


def add_complete_turn(session, user_text="question", model_text="answer", token_count=1000):
    session.add_message(HumanMessage(content=user_text))
    session.add_message(
        ModelMessage(
            id=f"m-{len(session.turns)}",
            content=model_text,
            stop_reason="end_turn",
            usage_data={},
        )
    )
    session.turns[-1].token_count = token_count


@pytest.mark.asyncio
async def test_compress_skipped_with_only_one_visible_turn(tmp_path):
    model = CompressModel()
    session = Session.create(tmp_path)
    add_complete_turn(session)
    session.save()

    await compress_session(
        session=session,
        model=model,
        compression_threshold=0.8,
        merge_ratio=0.2,
        logger=DummyLogger(),
    )

    assert model.invocations == 0


@pytest.mark.asyncio
async def test_compress_runs_when_multiple_turns_exist(tmp_path):
    model = CompressModel(summary="Summary of conversation.")
    session = Session.create(tmp_path)
    for i in range(3):
        add_complete_turn(session, f"q{i}", f"a{i}")
    # 设置高的 token count 以触发压缩
    for turn in session.turns:
        turn.token_count = 100_000
    session.save()

    await compress_session(
        session=session,
        model=model,
        compression_threshold=0.8,
        merge_ratio=0.2,
        keep_recent_turns=1,
        logger=DummyLogger(),
    )

    assert model.invocations >= 1


@pytest.mark.asyncio
async def test_compress_marks_turns_as_summarized(tmp_path):
    model = CompressModel(summary="Combined summary.")
    session = Session.create(tmp_path)
    for i in range(4):
        add_complete_turn(session, f"q{i}", f"a{i}")
    for turn in session.turns:
        turn.token_count = 100_000
    session.save()

    await compress_session(
        session=session,
        model=model,
        compression_threshold=0.8,
        keep_recent_turns=1,
        logger=DummyLogger(),
    )

    summarized_count = sum(1 for t in session.turns if t.is_summarized)
    assert summarized_count >= 1


@pytest.mark.asyncio
async def test_compress_assigns_summary_group_ids(tmp_path):
    model = CompressModel(summary="Group summary.")
    session = Session.create(tmp_path)
    for i in range(4):
        add_complete_turn(session, f"q{i}", f"a{i}")
    for turn in session.turns:
        turn.token_count = 100_000
    session.save()

    await compress_session(
        session=session,
        model=model,
        compression_threshold=0.8,
        keep_recent_turns=1,
        logger=DummyLogger(),
    )

    group_ids = {t.summary_group_id for t in session.turns if t.summary_group_id}
    assert len(group_ids) >= 1
    for gid in group_ids:
        assert gid


@pytest.mark.asyncio
async def test_create_hook_returns_callable_pair():
    check, execute = create_ctx_compress_hook(compression_threshold=0.8)

    assert callable(check)
    assert callable(execute)


def test_compress_prompt_is_a_string():
    from bbagent.built_in_hook.ctx_compress_hook import COMPRESS_PROMPT

    assert isinstance(COMPRESS_PROMPT, str)
    assert "summarizer" in COMPRESS_PROMPT.lower()


def test_compress_prefix_includes_instructions():
    from bbagent.built_in_hook.ctx_compress_hook import COMPRESS_PREFIX

    assert "conversation history" in COMPRESS_PREFIX.lower()
    assert "summary" in COMPRESS_PREFIX.lower()
