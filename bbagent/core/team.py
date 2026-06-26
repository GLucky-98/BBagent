import json
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .agent import Agent, AgentState
from .input import EventType
from .message import ContentBlock, Message, TextBlock
from .tool import Tool


@dataclass
class TeamMessage:
    from_agent: str
    to_agent: str
    content: str | list[ContentBlock]
    type: str  # "direct" | "broadcast" | "user"
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))

    def to_dict(self) -> dict:
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "content": Message._serialize_content(self.content),
            "type": self.type,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'TeamMessage':
        return cls(
            from_agent=data['from_agent'],
            to_agent=data['to_agent'],
            content=Message._deserialize_content(data['content'], "user"),
            type=data['type'],
            timestamp=data.get('timestamp', 0),
        )


@dataclass
class TeamConfig:
    name: str
    team_description: str
    agents: dict[str, Agent]
    contacts: dict[str, dict[str, str]]


class AgentTeam:
    def __init__(self, name: str, team_description: str = "", base_dir: str | Path | None = None):
        self.name = name
        self.team_description = team_description
        self.agents: dict[str, Agent] = {}
        self._contacts: dict[str, set[str]] = {}
        self.base_dir = Path(base_dir) if base_dir else None
        self._team_messages: list[TeamMessage] = []
        self._on_team_message: Callable[[dict], Awaitable[None]] | None = None
        self.state = AgentState.Ready

    @classmethod
    def create(cls, config: TeamConfig) -> 'AgentTeam':
        team = cls(config.name, config.team_description)

        for agent_name, agent in config.agents.items():
            agent.set_runtime_prompt("team", cls._build_team_prompt(config.team_description), order=20)

            contacts = config.contacts.get(agent_name, {})
            agent.set_runtime_prompt("teammates", cls._build_teammate_prompt(contacts), order=30)

            team._contacts[agent_name] = set(contacts.keys())

            team.agents[agent_name] = agent
            team._inject_team_tools(agent)

        return team

    @staticmethod
    def _build_team_prompt(team_description: str) -> str:
        return f"""[Team Context]
You are part of a collaborative team.

{team_description}

You have access to team communication tools:
- send_message: Send a direct message to a specific teammate
- broadcast: Send a message to all visible teammates

Collaborate proactively - reach out to teammates when their expertise is needed.
"""

    @staticmethod
    def _build_teammate_prompt(contacts: dict[str, str]) -> str:
        if not contacts:
            return ""

        lines = ["[Your Teammates]"]
        for name, role in contacts.items():
            lines.append(f"- {name}: {role}")
        return "\n".join(lines) + "\n"

    def add_agent(self, agent: Agent) -> 'AgentTeam':
        self.agents[agent.name] = agent
        self._inject_team_tools(agent)
        return self

    def _get_visible_contacts(self, agent_name: str) -> set[str]:
        if agent_name in self._contacts:
            return self._contacts[agent_name]
        return {name for name in self.agents if name != agent_name}

    def _wrap_with_prefix(
        self,
        content: str | list[ContentBlock],
        from_agent: str,
        to_agent: str,
    ) -> str | list[ContentBlock]:
        """Add a sender prefix only when the receiver can see the sender."""
        receiver_contacts = self._get_visible_contacts(to_agent)
        if from_agent not in receiver_contacts:
            return content

        prefix = (
            f"[Message from teammate: {from_agent}]\n"
            f"You can use send_message or broadcast to reply.\n\n"
        )

        if isinstance(content, str):
            return prefix + content
        return [TextBlock(text=prefix, origin="system"), *content]

    def _inject_team_tools(self, agent: Agent):
        team = self
        agent_name = agent.name

        visible = team._get_visible_contacts(agent_name)
        if not visible:
            return

        async def send_message(to_agent: str, message: str) -> str:
            visible = team._get_visible_contacts(agent_name)
            if to_agent not in visible:
                return f"Error: '{to_agent}' is not in your contacts"
            await team._send(agent_name, to_agent, message)
            return f"Message sent to {to_agent}"

        async def broadcast(message: str) -> str:
            count = await team._broadcast(agent_name, message)
            return f"Broadcast sent to {count} agents"

        send_msg_tool = Tool(
            func=send_message,
            name="send_message",
            description="Send a message to another agent in the team by name",
            input_schema={
                "type": "object",
                "properties": {
                    "to_agent": {
                        "type": "string",
                        "description": "Name of the target agent to send the message to"
                    },
                    "message": {
                        "type": "string",
                        "description": "Content of the message to send"
                    }
                },
                "required": ["to_agent", "message"]
            },
            source="team",
        )

        broadcast_tool = Tool(
            func=broadcast,
            name="broadcast",
            description="Broadcast a message to all visible teammates",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Content of the message to broadcast"
                    }
                },
                "required": ["message"]
            },
            source="team",
        )

        agent.add_tools([send_msg_tool, broadcast_tool])

    async def push_to_agent(self, agent_name: str, content: str | list[ContentBlock], source: str = "user"):
        """Push external content to an agent and record it in team messages."""
        target = self.agents.get(agent_name)
        if target is None:
            raise ValueError(f"Agent '{agent_name}' not found in team")
        target.input.push(
            content,
            source_id=f"team:{source}",
            event_type=EventType.AGENT_MESSAGE,
        )
        await self._record_team_message(TeamMessage(
            from_agent=source, to_agent=agent_name,
            content=content,
            type="user",
        ))

    async def _send(self, from_agent: str, to_agent: str, content: str | list[ContentBlock]):
        target = self.agents.get(to_agent)
        if target is None:
            raise ValueError(f"Agent '{to_agent}' not found in team")
        wrapped = self._wrap_with_prefix(content, from_agent, to_agent)
        target.input.push(
            wrapped,
            source_id=f"team:{from_agent}",
            event_type=EventType.AGENT_MESSAGE,
        )
        await self._record_team_message(TeamMessage(
            from_agent=from_agent, to_agent=to_agent,
            content=content,
            type="direct",
        ))

    async def _broadcast(self, from_agent: str, content: str | list[ContentBlock]) -> int:
        count = 0
        visible = self._get_visible_contacts(from_agent)
        for name in visible:
            agent = self.agents.get(name)
            if agent:
                wrapped = self._wrap_with_prefix(content, from_agent, name)
                agent.input.push(
                    wrapped,
                    source_id=f"team:{from_agent}",
                    event_type=EventType.AGENT_MESSAGE,
                )
                count += 1
        await self._record_team_message(TeamMessage(
            from_agent=from_agent, to_agent=",".join(sorted(visible)),
            content=content,
            type="broadcast",
        ))
        return count

    async def _record_team_message(self, msg: TeamMessage):
        self._team_messages.append(msg)
        if self._on_team_message:
            with suppress(Exception):
                await self._on_team_message(msg.to_dict())

    async def start(self):
        for agent in self.agents.values():
            await agent.start()
        self.update_state()

    async def stop(self):
        for agent in self.agents.values():
            await agent.stop()
        self.update_state()

    def update_state(self):
        """Aggregate team state from member agent states."""
        if not self.agents:
            self.state = AgentState.Ready
            return
        member_states = [a.state for a in self.agents.values()]
        if any(s == AgentState.Error for s in member_states):
            self.state = AgentState.Error
        elif any(s == AgentState.Running for s in member_states):
            self.state = AgentState.Running
        elif any(s == AgentState.Waiting for s in member_states):
            self.state = AgentState.Waiting
        else:
            self.state = AgentState.Ready

    def get_team_messages(self) -> list[TeamMessage]:
        return list(self._team_messages)

    def load_team_messages(self, path: str | Path):
        target = Path(path)
        if not target.exists():
            return
        self._team_messages.clear()
        with open(target, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    self._team_messages.append(TeamMessage.from_dict(json.loads(line)))
