import asyncio

from backend.logging import get_backend_logger

logger = get_backend_logger("dispatcher")

_MAX_BUFFER_ENTRIES = 500
_MAX_BUFFER_BYTES = 500 * 1024  # 500 KB


def _make_serializable(obj):
    """Recursively convert dataclass objects to plain dicts via to_dict()."""
    if hasattr(obj, "to_dict"):
        return _make_serializable(obj.to_dict())
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    return obj


class AgentOutputDispatcher:
    def __init__(self):
        self._subscribers: dict[str, asyncio.Queue] = {}
        self._round_buffer: list[dict] = []
        self._buffer_bytes = 0

    async def on_chunk(self, chunk):
        # Serialize dataclass content to plain dicts so downstream
        # consumers (WebSocket send_json, etc.) never see non-JSON types.
        serializable = _make_serializable(chunk)

        # Cache for replay
        self._round_buffer.append(serializable)
        self._buffer_bytes += len(str(serializable))

        # Evict oldest if over capacity (entries or bytes)
        while (
            len(self._round_buffer) > _MAX_BUFFER_ENTRIES
            or self._buffer_bytes > _MAX_BUFFER_BYTES
        ):
            evicted = self._round_buffer.pop(0)
            self._buffer_bytes -= len(str(evicted))

        # Clear buffer when round completes or is terminated abnormally
        if serializable.get("type") == "completed_message":
            self._round_buffer.clear()
            self._buffer_bytes = 0
        elif serializable.get("type") == "interrupted":
            self._round_buffer.clear()
            self._buffer_bytes = 0
        elif (
            serializable.get("type") == "agent_state"
            and serializable.get("state") == "error"
        ):
            self._round_buffer.clear()
            self._buffer_bytes = 0

        # Broadcast to existing subscribers
        for q in list(self._subscribers.values()):
            try:
                await q.put(serializable)
            except Exception as e:
                logger.warning(f"Failed to forward chunk to subscriber: {e}")

    def subscribe(self, subscriber_id: str, replay: bool = False) -> asyncio.Queue:
        q = asyncio.Queue()
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
