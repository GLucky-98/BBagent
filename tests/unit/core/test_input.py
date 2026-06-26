"""Baseline tests for bbagent.core.input — InputChannel and InputEvent."""

import asyncio
from datetime import time as dt_time

import pytest

from bbagent.core.input import InputChannel, InputEvent, InputType, _parse_time, _seconds_until
from bbagent.core.message import HumanMessage


def test_input_event_to_human_message_with_string_payload():
    event = InputEvent(
        type=InputType.USER_INPUT,
        source_id="user",
        payload="Hello, agent!",
    )

    msg = event.to_human_message()

    assert isinstance(msg, HumanMessage)
    assert msg.content[0].text == "Hello, agent!"


def test_input_event_to_human_message_with_human_message_payload():
    existing = HumanMessage(content="Direct message")
    event = InputEvent(
        type=InputType.USER_INPUT,
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

    assert isinstance(event, InputEvent)
    assert event.type == InputType.USER_INPUT
    assert event.source_id == "user"
    msg = event.payload
    assert isinstance(msg, HumanMessage)
    assert msg.content[0].text == "Hello"


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


def test_input_channel_start_and_stop_timer_while_not_running():
    """When channel is not running, start_timer returns False, stopping non-existent timer also returns False."""
    channel = InputChannel()

    channel.every(60.0, name="pause", hint="Pauseable")

    started = channel.start_timer("pause")
    assert started is False

    assert channel.stop_timer("nonexistent") is False


@pytest.mark.asyncio
async def test_input_channel_start_and_stop_timer_success():
    """channel.start() automatically starts all timers, can manually stop/restart via stop_timer/start_timer."""
    channel = InputChannel()

    channel.every(60.0, name="pause", hint="Pauseable")
    await channel.start()

    # start() auto-starts, first confirm it's running
    assert channel.list_timers()[0]["running"] is True

    # stop_timer stops and returns True
    stopped = channel.stop_timer("pause")
    assert stopped is True
    assert channel.list_timers()[0]["running"] is False

    # start_timer restarts and returns True
    started = channel.start_timer("pause")
    assert started is True
    assert channel.list_timers()[0]["running"] is True

    await channel.stop()


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


# ============================================================================
# Tests for time-point (at) timer functionality
# ============================================================================

def test_parse_time_valid_hh_mm():
    """Test parsing HH:MM format"""
    result = _parse_time("08:00")
    assert result == dt_time(8, 0)


def test_parse_time_valid_hh_mm_ss():
    """Test parsing HH:MM:SS format"""
    result = _parse_time("14:30:45")
    assert result == dt_time(14, 30, 45)


def test_parse_time_invalid_format():
    """Test invalid time format"""
    with pytest.raises(ValueError, match="Invalid time format"):
        _parse_time("invalid")

    with pytest.raises(ValueError, match="Invalid time format"):
        _parse_time("12")

    with pytest.raises(ValueError, match="Invalid time format"):
        _parse_time("12:30:45:00")


def test_seconds_until_future_time():
    """Test calculating seconds until a future time"""
    # use a deterministic future time
    future_time = dt_time(23, 59, 59)
    result = _seconds_until(future_time)
    # result should be a positive number (seconds)
    assert result > 0


def test_input_channel_at_registers_timer_config():
    """Test at() method registers config"""
    channel = InputChannel()

    channel.at("08:00", name="morning", hint="Morning task")

    timers = channel.list_timers()
    assert len(timers) == 1
    assert timers[0]["type"] == "at"
    assert timers[0]["time"] == "08:00"
    assert timers[0]["name"] == "morning"
    assert timers[0]["hint"] == "Morning task"


def test_input_channel_at_upserts_existing_timer():
    """Test at() method updates existing config"""
    channel = InputChannel()

    channel.at("08:00", name="morning", hint="Original")
    channel.at("09:00", name="morning", hint="Updated")

    timers = channel.list_timers()
    assert len(timers) == 1
    assert timers[0]["type"] == "at"
    assert timers[0]["time"] == "09:00"
    assert timers[0]["hint"] == "Updated"


def test_input_channel_at_invalid_time_format():
    """Test invalid time format"""
    channel = InputChannel()

    with pytest.raises(ValueError):
        channel.at("invalid", name="bad")


def test_input_channel_at_cancel_removes_timer():
    """Test canceling time-point task"""
    channel = InputChannel()

    channel.at("08:00", name="morning", hint="Morning")
    removed = channel.cancel("morning")

    assert removed is True
    assert len(channel.list_timers()) == 0


def test_input_channel_list_timers_with_mixed_types():
    """Test mixed-type task list"""
    channel = InputChannel()

    channel.every(60.0, name="interval_task", hint="Interval")
    channel.at("08:00", name="at_task", hint="At")

    timers = channel.list_timers()
    assert len(timers) == 2

    interval_timer = next(t for t in timers if t["type"] == "interval")
    at_timer = next(t for t in timers if t["type"] == "at")

    assert interval_timer["seconds"] == 60.0
    assert interval_timer["name"] == "interval_task"
    assert at_timer["time"] == "08:00"
    assert at_timer["name"] == "at_task"


def test_input_channel_clear_timers_removes_all_mixed():
    """Test clearing all mixed-type tasks"""
    channel = InputChannel()

    channel.every(60.0, name="interval_task")
    channel.at("08:00", name="at_task")

    channel.clear_timers()

    assert len(channel.list_timers()) == 0


def test_input_channel_at_start_and_stop_timer_while_not_running():
    """When channel is not running, start_timer returns False"""
    channel = InputChannel()

    channel.at("08:00", name="morning", hint="Morning")

    started = channel.start_timer("morning")
    assert started is False


@pytest.mark.asyncio
async def test_input_channel_at_start_and_stop_timer_success():
    """channel.start() automatically starts all at timers, can manually stop/restart via stop_timer/start_timer."""
    channel = InputChannel()

    channel.at("08:00", name="morning", hint="Morning")
    await channel.start()

    # start() auto-starts, first confirm it's running
    at_timer = next(t for t in channel.list_timers() if t["name"] == "morning")
    assert at_timer["running"] is True

    # stop_timer stops and returns True
    stopped = channel.stop_timer("morning")
    assert stopped is True
    at_timer = next(t for t in channel.list_timers() if t["name"] == "morning")
    assert at_timer["running"] is False

    # start_timer restarts and returns True
    started = channel.start_timer("morning")
    assert started is True
    at_timer = next(t for t in channel.list_timers() if t["name"] == "morning")
    assert at_timer["running"] is True

    await channel.stop()


def test_input_channel_start_timer_mixed_types():
    """Test starting mixed-type tasks"""
    channel = InputChannel()

    channel.every(60.0, name="interval_task")
    channel.at("08:00", name="at_task")

    # neither can start when not running
    assert channel.start_timer("interval_task") is False
    assert channel.start_timer("at_task") is False


def test_input_channel_cancel_mixed_types():
    """Test cancelling mixed-type tasks"""
    channel = InputChannel()

    channel.every(60.0, name="interval_task")
    channel.at("08:00", name="at_task")

    # cancel interval task
    assert channel.cancel("interval_task") is True
    assert len(channel.list_timers()) == 1
    assert channel.list_timers()[0]["name"] == "at_task"

    # cancel time-point task
    assert channel.cancel("at_task") is True
    assert len(channel.list_timers()) == 0
