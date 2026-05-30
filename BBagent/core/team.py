from dataclasses import dataclass
from pathlib import Path

import yaml

from .agent import Agent
from .input import EventType
from .tool import Tool


@dataclass
class TeamConfig:
    name: str
    team_description: str
    agents: dict[str, Agent]
    contacts: dict[str, dict[str, str]]


class AgentTeam:
    def __init__(self, name: str, team_description: str = "", base_dir: str | Path = None):
        self.name = name
        self.team_description = team_description
        self.agents: dict[str, Agent] = {}
        self._contacts: dict[str, set[str]] = {}
        self.base_dir = Path(base_dir) if base_dir else None

    @classmethod
    def create(cls, config: TeamConfig) -> 'AgentTeam':
        team = cls(config.name, config.team_description)

        for agent_name, agent in config.agents.items():
            if agent.name != agent_name:
                agent.change_name(agent_name)

            agent.team_prompt = cls._build_team_prompt(config.team_description)

            contacts = config.contacts.get(agent_name, {})
            agent.teammate_prompt = cls._build_teammate_prompt(contacts)

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

    def _inject_team_tools(self, agent: Agent):
        team = self
        agent_name = agent.name

        visible = team._get_visible_contacts(agent_name)
        if not visible:
            return

        def send_message(to_agent: str, message: str) -> str:
            visible = team._get_visible_contacts(agent_name)
            if to_agent not in visible:
                return f"Error: '{to_agent}' is not in your contacts"
            team._send(agent_name, to_agent, message)
            return f"Message sent to {to_agent}"

        def broadcast(message: str) -> str:
            count = team._broadcast(agent_name, message)
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
            }
        )
        send_msg_tool.mark_team_managed()

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
            }
        )
        broadcast_tool.mark_team_managed()

        agent.add_tools([send_msg_tool, broadcast_tool])

    def _send(self, from_agent: str, to_agent: str, content: str):
        target = self.agents.get(to_agent)
        if target is None:
            raise ValueError(f"Agent '{to_agent}' not found in team")
        target.input.push(
            content,
            source_id=f"team:{from_agent}",
            event_type=EventType.AGENT_MESSAGE,
        )

    def _broadcast(self, from_agent: str, content: str) -> int:
        count = 0
        visible = self._get_visible_contacts(from_agent)
        for name in visible:
            agent = self.agents.get(name)
            if agent:
                agent.input.push(
                    content,
                    source_id=f"team:{from_agent}",
                    event_type=EventType.AGENT_MESSAGE,
                )
                count += 1
        return count

    async def start(self):
        for agent in self.agents.values():
            await agent.start()

    async def stop(self):
        for agent in self.agents.values():
            await agent.stop()

    def to_config_dict(self) -> dict:
        return {
            "version": 1,
            "name": self.name,
            "team_description": self.team_description,
            "agents": {
                name: {"config_path": str(agent.base_dir / "agent_config.yaml")}
                for name, agent in self.agents.items()
            },
            "contacts": {
                name: sorted(list(contacts))
                for name, contacts in self._contacts.items()
            },
        }

    def save(self, base_dir: str | Path = None):
        save_path = Path(base_dir) if base_dir else self.base_dir
        if save_path is None:
            raise ValueError("base_dir is required for saving team config")
        save_path.mkdir(parents=True, exist_ok=True)
        config_path = save_path / "team_config.yaml"
        config_dict = self.to_config_dict()
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        for agent in self.agents.values():
            agent.save()

    @classmethod
    def load(cls, base_dir: str | Path, *,
             extra_tool_builders: dict = None) -> 'AgentTeam':
        base_path = Path(base_dir)
        config_path = base_path / "team_config.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Team config not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)

        extra_tool_builders = extra_tool_builders or {}

        name = config_dict.get("name", "Team")
        team_description = config_dict.get("team_description", "")

        team = cls(name=name, team_description=team_description, base_dir=base_path)

        agents_config = config_dict.get("agents", {})
        for agent_name, agent_cfg in agents_config.items():
            config_path_str = agent_cfg.get("config_path")
            if config_path_str and Path(config_path_str).exists():
                agent = Agent.load(
                    Path(config_path_str).parent,
                    extra_tool_builders=extra_tool_builders,
                )
            else:
                continue

            if agent.name != agent_name:
                agent.change_name(agent_name)

            agent.team_prompt = cls._build_team_prompt(team_description)

            contacts_dict = {}
            contacts_from_config = config_dict.get("contacts", {}).get(agent_name, [])
            for contact_name in contacts_from_config:
                contacts_dict[contact_name] = ""
            team._contacts[agent_name] = set(contacts_dict.keys())
            agent.teammate_prompt = cls._build_teammate_prompt(contacts_dict)

            team.agents[agent_name] = agent
            team._inject_team_tools(agent)

        return team
