import asyncio
from abc import ABC, abstractmethod
from typing import Optional

from .events import AgentEvent, EventType
from .message import HumanMessage


class EventSource(ABC):

    @abstractmethod
    async def start(self, output_queue: asyncio.Queue):
        ...

    @abstractmethod
    async def stop(self):
        ...


class UserInputSource(EventSource):
    def __init__(self, user_id: str = "user"):
        self._user_id = user_id
        self._queue: Optional[asyncio.Queue] = None

    async def start(self, output_queue: asyncio.Queue):
        self._queue = output_queue

    async def stop(self):
        self._queue = None

    def push(self, text: str):
        if self._queue is None:
            return
        event = AgentEvent(
            type=EventType.USER_MESSAGE,
            source_id=self._user_id,
            payload=HumanMessage(content=text),
        )
        self._queue.put_nowait(event)


class TimerSource(EventSource):
    def __init__(self):
        self._queue: Optional[asyncio.Queue] = None
        self._timers: list[asyncio.Task] = []
        self._running = False

    async def start(self, output_queue: asyncio.Queue):
        self._queue = output_queue
        self._running = True

    async def stop(self):
        self._running = False
        for task in self._timers:
            task.cancel()
        self._timers.clear()
        self._queue = None

    def _create_timer_task(self, interval_seconds: float, name: str, hint: str):
        async def _loop():
            while self._running:
                await asyncio.sleep(interval_seconds)
                if not self._running or self._queue is None:
                    break
                prompt = f"[定时任务: {name}]\n{hint}"
                event = AgentEvent(
                    type=EventType.TIMER_TRIGGER,
                    source_id=f"timer:{name}",
                    payload=HumanMessage(content=prompt),
                )
                self._queue.put_nowait(event)

        task = asyncio.create_task(_loop())
        self._timers.append(task)
        return self

    def every(self, seconds: float, name: str = "", hint: str = ""):
        return self._create_timer_task(seconds, name, hint)


class MessageBusSource(EventSource):
    def __init__(self, message_bus, agent_name: str):
        self._bus = message_bus
        self._agent_name = agent_name
        self._queue: Optional[asyncio.Queue] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self, output_queue: asyncio.Queue):
        self._queue = output_queue
        self._running = True
        self._task = asyncio.create_task(self._poll())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        self._queue = None

    async def _poll(self):
        while self._running:
            msg = await self._bus.receive(self._agent_name, timeout=0.5)
            if msg is None:
                continue
            event = AgentEvent(
                type=EventType.AGENT_MESSAGE,
                source_id=f"agent:{msg.get('from', 'unknown')}",
                payload=HumanMessage(content=msg.get('content', '')),
            )
            if self._queue:
                self._queue.put_nowait(event)
