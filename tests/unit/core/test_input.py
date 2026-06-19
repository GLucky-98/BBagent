"""Baseline tests for bbagent.core.input — InputChannel and AgentEvent."""

import asyncio

import pytest

from bbagent.core.input import AgentEvent, EventType, InputChannel
from bbagent.core.message import HumanMessage


def test_agent_event_to_human_message_with_string_payload():
    event = AgentEvent(
        type=EventType.USER_MESSAGE,
        source_id="user",
        payload="Hello, agent!",
    )

    msg = event.to_human_message()

    assert isinstance(msg, HumanMessage)
    assert msg.content == "Hello, agent!"


def test_agent_event_to_human_message_with_human_message_payload():
    existing = HumanMessage(content="Direct message")
    event = AgentEvent(
        type=EventType.USER_MESSAGE,
        source_id="user",
        payload=existing,
    )

    msg = event.to_human_message()

    assert msg is existing


def test_input_channel_push_puts_event_on_queue():
    channel = InputChannel()
    channel._running = True

    channel.push("Hello", source_id="user")

    event = channel._queue.get_nowait()

    assert isinstance(event, AgentEvent)
    assert event.type == EventType.USER_MESSAGE
    assert event.source_id == "user"
    msg = event.payload
    assert isinstance(msg, HumanMessage)
    assert msg.content == "Hello"


def test_input_channel_push_ignores_when_not_running():
    channel = InputChannel()
    channel._running = False

    channel.push("Hello")

    assert channel._queue.empty()


def test_input_channel_every_registers_timer_config():
    channel = InputChannel()

    channel.every(60.0, name="review", hint="Review the code")

    timers = channel.list_timers()
    assert len(timers) == 1
    assert timers[0]["name"] == "review"
    assert timers[0]["seconds"] == 60.0
    assert timers[0]["hint"] == "Review the code"


def test_input_channel_every_upserts_existing_timer():
    channel = InputChannel()

    channel.every(60.0, name="review", hint="Original")
    channel.every(30.0, name="review", hint="Updated")

    timers = channel.list_timers()
    assert len(timers) == 1
    assert timers[0]["seconds"] == 30.0
    assert timers[0]["hint"] == "Updated"


def test_input_channel_cancel_removes_timer():
    channel = InputChannel()

    channel.every(60.0, name="review", hint="Review")
    removed = channel.cancel("review")

    assert removed is True
    assert len(channel.list_timers()) == 0


def test_input_channel_cancel_nonexistent_returns_false():
    channel = InputChannel()

    assert channel.cancel("no-such-timer") is False


def test_input_channel_clear_timers_removes_all():
    channel = InputChannel()

    channel.every(10.0, name="a")
    channel.every(20.0, name="b")
    channel.every(30.0, name="c")

    channel.clear_timers()

    assert len(channel.list_timers()) == 0


def test_input_channel_start_and_stop_timer():
    channel = InputChannel()

    channel.every(60.0, name="pause", hint="Pauseable")

    # 未启动状态下 start_timer 返回 False
    started = channel.start_timer("pause")
    assert started is False

    # 不存在 → False
    assert channel.stop_timer("nonexistent") is False


def test_input_channel_drain_queue_on_stop():
    channel = InputChannel()
    channel._running = True

    channel.push("msg-1")
    channel.push("msg-2")
    channel.push("msg-3")

    channel._drain_queue()

    assert channel._queue.empty()


@pytest.mark.asyncio
async def test_input_channel_stop_cancels_timers():
    channel = InputChannel()

    channel.every(0.01, name="fast")
    await channel.start()

    await asyncio.sleep(0.05)

    assert {"fast"} == {t[0] for t in channel._timers}

    await channel.stop()

    assert len(channel._timers) == 0
    assert channel._queue.empty()
