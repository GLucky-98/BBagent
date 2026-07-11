import asyncio

from backend.logging import get_backend_logger

logger = get_backend_logger("dispatcher")


def _make_serializable(obj):
    """Recursively convert dataclass objects to plain dicts via to_dict()."""
    if hasattr(obj, "to_dict"):
        return _make_serializable(obj.to_dict())
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    return obj


def _is_completed_end_turn(chunk: dict) -> bool:
    if not (chunk.get("type") == "stream_chunk" and chunk.get("chunk_type") == "completed_message"):
        return False
    content = chunk.get("content") or {}
    return isinstance(content, dict) and content.get("stop_reason") == "end_turn"


def _should_clear_buffer(chunk: dict) -> bool:
    if _is_completed_end_turn(chunk):
        return True
    if chunk.get("type") == "event" and chunk.get("event_type") == "interrupted":
        return True
    return (
        chunk.get("type") == "event"
        and chunk.get("event_type") == "agent_state"
        and chunk.get("state") == "error"
    )


class AgentOutputDispatcher:
    def __init__(self, replay_buffer: bool = True):
        self._subscribers: dict[str, asyncio.Queue[dict]] = {}
        self._round_buffer: list[dict] = []
        self._replay_buffer = replay_buffer

    async def on_chunk(self, chunk):
        # Serialize dataclass content to plain dicts so downstream
        # consumers (WebSocket send_json, etc.) never see non-JSON types.
        serializable = _make_serializable(chunk)

        if self._replay_buffer:
            # Cache the current incomplete turn for replay. It is intentionally
            # not truncated; otherwise switching back can restore only part of
            # an in-flight tool loop.
            self._round_buffer.append(serializable)

            # Clear buffer only when the full turn ends or is terminated.
            # A completed_message with stop_reason=tool_use is still mid-turn.
            if _should_clear_buffer(serializable):
                self._round_buffer.clear()

        # Broadcast to existing subscribers
        for q in list(self._subscribers.values()):
            try:
                await q.put(serializable)
            except Exception as e:
                logger.warning(f"Failed to forward chunk to subscriber: {e}")

    def subscribe(self, subscriber_id: str, replay: bool = False) -> asyncio.Queue[dict]:
        q: asyncio.Queue[dict] = asyncio.Queue()
        if replay and self._round_buffer:
            for chunk in self._round_buffer:
                q.put_nowait(chunk)
        self._subscribers[subscriber_id] = q
        logger.info(
            "Subscriber '%s' attached, total: %d (replay=%s, buffer=%d chunks)",
            subscriber_id, len(self._subscribers), replay, len(self._round_buffer),
        )
        return q

    def unsubscribe(self, subscriber_id: str):
        self._subscribers.pop(subscriber_id, None)
        logger.info(
            "Subscriber '%s' detached, total: %d",
            subscriber_id, len(self._subscribers),
        )

    async def broadcast_system(self, content: str):
        await self.on_chunk({"type": "system", "content": content})

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
