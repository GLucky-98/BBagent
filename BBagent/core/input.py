import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4 as uuid

from .message import HumanMessage


class EventType(Enum):
    USER_MESSAGE = "user_message"
    TIMER_TRIGGER = "timer_trigger"
    AGENT_MESSAGE = "agent_message"
    SYSTEM_EVENT = "system_event"


@dataclass
class AgentEvent:
    type: EventType
    source_id: str
    payload: Any
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = field(default_factory=lambda: uuid().hex[:12])

    def to_human_message(self) -> HumanMessage:
        if isinstance(self.payload, HumanMessage):
            return self.payload
        if isinstance(self.payload, str):
            return HumanMessage(content=self.payload)
        return HumanMessage(content=str(self.payload))


class InputChannel:
    def __init__(self):
        self._queue: Optional[asyncio.Queue] = None
        self._running = False
        self._timer_configs: list[tuple[float, str, str]] = []
        self._timers: list[asyncio.Task] = []

    async def start(self, output_queue: asyncio.Queue):
        self._queue = output_queue
        self._running = True
        self._timers = []
        for seconds, name, hint in self._timer_configs:
            task = self._create_timer_task(seconds, name, hint)
            self._timers.append(task)

    def _create_timer_task(self, seconds: float, name: str, hint: str) -> asyncio.Task:
        async def _loop():
            while self._running:
                await asyncio.sleep(seconds)
                if not self._running or self._queue is None:
                    break
                prompt = f"[Scheduled task: {name}]\n{hint}" if name else hint
                self.push(
                    prompt,
                    source_id=f"timer:{name}",
                    event_type=EventType.TIMER_TRIGGER,
                )

        return asyncio.create_task(_loop())

    async def stop(self):
        self._running = False
        for task in self._timers:
            task.cancel()
        self._timers.clear()
        self._queue = None

    def push(self, text: str, source_id: str = "user",
             event_type: EventType = EventType.USER_MESSAGE):
        if self._queue is None:
            return
        event = AgentEvent(
            type=event_type,
            source_id=source_id,
            payload=HumanMessage(content=text),
        )
        self._queue.put_nowait(event)

    def every(self, seconds: float, name: str = "", hint: str = ""):
        self._timer_configs.append((seconds, name, hint))
        task = self._create_timer_task(seconds, name, hint)
        self._timers.append(task)
        return self
