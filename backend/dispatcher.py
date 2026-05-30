import asyncio
import logging

logger = logging.getLogger("bbagent.dispatcher")


class AgentOutputDispatcher:
    def __init__(self):
        self._subscribers: dict[str, asyncio.Queue] = {}

    async def on_chunk(self, chunk):
        for q in list(self._subscribers.values()):
            try:
                await q.put(chunk)
            except Exception as e:
                logger.warning(f"Failed to forward chunk to subscriber: {e}")

    def subscribe(self, subscriber_id: str) -> asyncio.Queue:
        q = asyncio.Queue()
        self._subscribers[subscriber_id] = q
        logger.info(f"Subscriber '{subscriber_id}' attached, total: {len(self._subscribers)}")
        return q

    def unsubscribe(self, subscriber_id: str):
        self._subscribers.pop(subscriber_id, None)
        logger.info(f"Subscriber '{subscriber_id}' detached, total: {len(self._subscribers)}")

    async def broadcast_system(self, content: str):
        await self.on_chunk({"type": "system", "content": content})

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
