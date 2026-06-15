import pytest

from backend.dispatcher import AgentOutputDispatcher


async def _queued_items(queue):
    items = []
    while not queue.empty():
        items.append(await queue.get())
    return items


@pytest.mark.asyncio
async def test_tool_use_completed_message_keeps_replay_buffer():
    dispatcher = AgentOutputDispatcher()

    await dispatcher.on_chunk({"type": "completed_tool_use", "content": {"id": "call-1"}})
    await dispatcher.on_chunk({
        "type": "completed_message",
        "content": {"stop_reason": "tool_use"},
    })

    queue = dispatcher.subscribe("subscriber", replay=True)

    assert [item["type"] for item in await _queued_items(queue)] == [
        "completed_tool_use",
        "completed_message",
    ]


@pytest.mark.asyncio
async def test_end_turn_completed_message_clears_replay_buffer():
    dispatcher = AgentOutputDispatcher()

    await dispatcher.on_chunk({"type": "completed_tool_use", "content": {"id": "call-1"}})
    await dispatcher.on_chunk({
        "type": "completed_message",
        "content": {"stop_reason": "end_turn"},
    })

    queue = dispatcher.subscribe("subscriber", replay=True)

    assert await _queued_items(queue) == []


@pytest.mark.asyncio
async def test_interrupted_clears_replay_buffer():
    dispatcher = AgentOutputDispatcher()

    await dispatcher.on_chunk({"type": "completed_tool_use", "content": {"id": "call-1"}})
    await dispatcher.on_chunk({"type": "interrupted"})

    queue = dispatcher.subscribe("subscriber", replay=True)

    assert await _queued_items(queue) == []


@pytest.mark.asyncio
async def test_agent_error_clears_replay_buffer():
    dispatcher = AgentOutputDispatcher()

    await dispatcher.on_chunk({"type": "completed_tool_use", "content": {"id": "call-1"}})
    await dispatcher.on_chunk({"type": "agent_state", "state": "error"})

    queue = dispatcher.subscribe("subscriber", replay=True)

    assert await _queued_items(queue) == []


@pytest.mark.asyncio
async def test_replay_buffer_is_not_silently_truncated():
    dispatcher = AgentOutputDispatcher()

    for i in range(600):
        await dispatcher.on_chunk({"type": "text", "content": f"chunk-{i}"})

    queue = dispatcher.subscribe("subscriber", replay=True)

    assert len(await _queued_items(queue)) == 600


@pytest.mark.asyncio
async def test_disabled_replay_buffer_does_not_cache_events():
    dispatcher = AgentOutputDispatcher(replay_buffer=False)

    await dispatcher.on_chunk({"type": "text", "content": "not cached"})

    queue = dispatcher.subscribe("subscriber", replay=True)

    assert await _queued_items(queue) == []
