import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional
from uuid import uuid4 as uuid

from .message import ContentBlock, HumanMessage


class EventType(Enum):
    USER_MESSAGE = "user_message"
    TIMER_TRIGGER = "timer_trigger"
    AGENT_MESSAGE = "agent_message"


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
        self._timers: list[tuple[str, asyncio.Task]] = []

    async def start(self, output_queue: asyncio.Queue):
        self._queue = output_queue
        self._running = True
        self._timers = []
        for seconds, name, hint in self._timer_configs:
            task = self._create_timer_task(seconds, name, hint)
            self._timers.append((name, task))

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
        for _, task in self._timers:
            task.cancel()
        self._timers.clear()
        self._queue = None

    def push(self, content: str | List[ContentBlock], source_id: str = "user",
             event_type: EventType = EventType.USER_MESSAGE):
        if self._queue is None:
            return
        event = AgentEvent(
            type=event_type,
            source_id=source_id,
            payload=HumanMessage(content=content),
        )
        self._queue.put_nowait(event)

    def every(self, seconds: float, name: str = "", hint: str = "") -> 'InputChannel':
        # upsert: if name exists, update config and restart
        for i, (s, n, h) in enumerate(self._timer_configs):
            if n == name:
                self._timer_configs[i] = (seconds, name, hint)
                self._stop_timer_task(name)
                if self._running:
                    task = self._create_timer_task(seconds, name, hint)
                    self._timers.append((name, task))
                return self
        self._timer_configs.append((seconds, name, hint))
        if self._running:
            task = self._create_timer_task(seconds, name, hint)
            self._timers.append((name, task))
        return self

    def _stop_timer_task(self, name: str):
        for i in range(len(self._timers) - 1, -1, -1):
            tname, task = self._timers[i]
            if tname == name:
                task.cancel()
                del self._timers[i]

    def cancel(self, name: str) -> bool:
        """按 name 取消一个 timer（删除配置 + 停止任务）。返回是否实际取消了一个。"""
        removed = False
        for i in range(len(self._timer_configs) - 1, -1, -1):
            if self._timer_configs[i][1] == name:
                del self._timer_configs[i]
                removed = True
        self._stop_timer_task(name)
        return removed

    def start_timer(self, name: str) -> bool:
        """从已有配置启动任务（不删除配置）。返回是否成功启动。"""
        config = None
        for s, n, h in self._timer_configs:
            if n == name:
                config = (s, n, h)
                break
        if config is None:
            return False
        # already running?
        for tname, _ in self._timers:
            if tname == name:
                return False
        if self._running:
            task = self._create_timer_task(config[0], config[1], config[2])
            self._timers.append((name, task))
            return True
        return False

    def stop_timer(self, name: str) -> bool:
        """停止任务但保留配置。返回是否成功停止。"""
        found = False
        for tname, _ in self._timers:
            if tname == name:
                found = True
                break
        if not found:
            return False
        self._stop_timer_task(name)
        return True

    def list_timers(self) -> list[dict]:
        """返回当前所有 timer 配置及运行状态的快照。"""
        running_names = {name for name, _ in self._timers}
        return [
            {"seconds": seconds, "name": name, "hint": hint, "running": name in running_names}
            for seconds, name, hint in self._timer_configs
        ]

    def clear_timers(self) -> None:
        """清空所有 timer 配置并取消所有任务。"""
        for _, task in self._timers:
            task.cancel()
        self._timers.clear()
        self._timer_configs.clear()
