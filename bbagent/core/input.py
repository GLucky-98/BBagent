import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from datetime import time as dt_time
from enum import Enum
from typing import Any

from .message import ContentBlock, HumanMessage


class InputType(Enum):
    USER_INPUT = "user_input"
    TIMER_INPUT = "timer_input"
    AGENT_INPUT = "agent_input"


@dataclass
class InputEvent:
    type: InputType
    source_id: str
    payload: Any
    timestamp: float = field(default_factory=time.time)

    def to_human_message(self) -> HumanMessage:
        if isinstance(self.payload, HumanMessage):
            return self.payload
        if isinstance(self.payload, str):
            return HumanMessage(content=self.payload)
        return HumanMessage(content=str(self.payload))


def _parse_time(time_str: str) -> dt_time:
    """解析时间字符串, 支持 HH:MM 或 HH:MM:SS 格式"""
    parts = time_str.strip().split(":")
    if len(parts) == 2:
        return dt_time(int(parts[0]), int(parts[1]))
    elif len(parts) == 3:
        return dt_time(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        raise ValueError(f"Invalid time format: {time_str}. Expected HH:MM or HH:MM:SS")


def _seconds_until(target_time: dt_time) -> float:
    """计算从现在到目标时间的秒数(如果目标时间已过, 则计算到明天)"""
    now = datetime.now()
    target = datetime.combine(now.date(), target_time)

    if target <= now:
        target += timedelta(days=1)

    return (target - now).total_seconds()


class InputChannel:
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._interval_configs: list[tuple[float, str, str]] = []
        self._at_configs: list[tuple[str, str, str]] = []
        self._timers: list[tuple[str, asyncio.Task]] = []

    @property
    def queue(self) -> asyncio.Queue:
        return self._queue

    async def start(self):
        self._running = True
        self._timers = []
        # 启动间隔触发任务
        for seconds, name, hint in self._interval_configs:
            task = self._create_interval_task(seconds, name, hint)
            self._timers.append((name, task))
        # 启动时间点触发任务
        for time_str, name, hint in self._at_configs:
            task = self._create_at_task(time_str, name, hint)
            self._timers.append((name, task))

    def _create_interval_task(self, seconds: float, name: str, hint: str) -> asyncio.Task:
        """创建间隔触发任务"""
        async def _loop():
            while self._running:
                await asyncio.sleep(seconds)
                if not self._running:
                    break
                prompt = f"[Scheduled task: {name}]\n{hint}" if name else hint
                self.push(
                    prompt,
                    source_id=f"timer:{name}",
                    event_type=InputType.TIMER_INPUT,
                )

        return asyncio.create_task(_loop())

    def _create_at_task(self, time_str: str, name: str, hint: str) -> asyncio.Task:
        """创建时间点触发任务"""
        async def _loop():
            while self._running:
                target_time = _parse_time(time_str)
                wait_seconds = _seconds_until(target_time)
                await asyncio.sleep(wait_seconds)
                if not self._running:
                    break
                prompt = f"[Scheduled task: {name}]\n{hint}" if name else hint
                self.push(
                    prompt,
                    source_id=f"timer:{name}",
                    event_type=InputType.TIMER_INPUT,
                )

        return asyncio.create_task(_loop())

    async def stop(self):
        self._running = False
        for _, task in self._timers:
            task.cancel()
        self._timers.clear()
        self._drain_queue()
        self._queue = asyncio.Queue()

    def _drain_queue(self):
        while True:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def push(self, content: str | list[ContentBlock], source_id: str = "user",
             event_type: InputType = InputType.USER_INPUT):
        if not self._running:
            return
        event = InputEvent(
            type=event_type,
            source_id=source_id,
            payload=HumanMessage(content=content),
        )
        self._queue.put_nowait(event)

    def every(self, seconds: float, name: str = "", hint: str = "") -> 'InputChannel':
        """创建间隔触发任务"""
        # upsert: if name exists, update config and restart
        for i, (_, n, _) in enumerate(self._interval_configs):
            if n == name:
                self._interval_configs[i] = (seconds, name, hint)
                self._stop_timer_task(name)
                if self._running:
                    task = self._create_interval_task(seconds, name, hint)
                    self._timers.append((name, task))
                return self
        self._interval_configs.append((seconds, name, hint))
        if self._running:
            task = self._create_interval_task(seconds, name, hint)
            self._timers.append((name, task))
        return self

    def at(self, time_str: str, name: str = "", hint: str = "") -> 'InputChannel':
        """创建时间点触发任务

        Args:
            time_str: 时间字符串, 格式为 "HH:MM" 或 "HH:MM:SS"
            name: 任务名称
            hint: 任务提示
        """
        # 验证时间格式
        _parse_time(time_str)

        # upsert: if name exists, update config and restart
        for i, (_, n, _) in enumerate(self._at_configs):
            if n == name:
                self._at_configs[i] = (time_str, name, hint)
                self._stop_timer_task(name)
                if self._running:
                    task = self._create_at_task(time_str, name, hint)
                    self._timers.append((name, task))
                return self
        self._at_configs.append((time_str, name, hint))
        if self._running:
            task = self._create_at_task(time_str, name, hint)
            self._timers.append((name, task))
        return self

    def _stop_timer_task(self, name: str):
        for i in range(len(self._timers) - 1, -1, -1):
            tname, task = self._timers[i]
            if tname == name:
                task.cancel()
                del self._timers[i]

    def cancel(self, name: str) -> bool:
        """按 name 取消一个 timer(删除配置 + 停止任务). 返回是否实际取消了一个."""
        removed = False
        # 从间隔配置中删除
        for i in range(len(self._interval_configs) - 1, -1, -1):
            if self._interval_configs[i][1] == name:
                del self._interval_configs[i]
                removed = True
        # 从时间点配置中删除
        for i in range(len(self._at_configs) - 1, -1, -1):
            if self._at_configs[i][1] == name:
                del self._at_configs[i]
                removed = True
        self._stop_timer_task(name)
        return removed

    def start_timer(self, name: str) -> bool:
        """从已有配置启动任务(不删除配置). 返回是否成功启动."""
        config = None
        config_type = None

        # 查找间隔配置
        for s, n, h in self._interval_configs:
            if n == name:
                config = (s, n, h)
                config_type = "interval"
                break

        # 查找时间点配置
        if config is None:
            for t, n, h in self._at_configs:
                if n == name:
                    config = (t, n, h)
                    config_type = "at"
                    break

        if config is None:
            return False

        # already running?
        for tname, _ in self._timers:
            if tname == name:
                return False

        if self._running:
            if config_type == "interval":
                task = self._create_interval_task(config[0], config[1], config[2])
            else:
                task = self._create_at_task(config[0], config[1], config[2])
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
        result = []

        # 间隔触发任务
        for seconds, name, hint in self._interval_configs:
            result.append({
                "type": "interval",
                "seconds": seconds,
                "name": name,
                "hint": hint,
                "running": name in running_names
            })

        # 时间点触发任务
        for time_str, name, hint in self._at_configs:
            result.append({
                "type": "at",
                "time": time_str,
                "name": name,
                "hint": hint,
                "running": name in running_names
            })

        return result

    def clear_timers(self) -> None:
        """清空所有 timer 配置并取消所有任务。"""
        for _, task in self._timers:
            task.cancel()
        self._timers.clear()
        self._interval_configs.clear()
        self._at_configs.clear()
