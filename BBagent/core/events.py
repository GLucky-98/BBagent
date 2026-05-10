import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
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
