from .agent import Agent
from .input import EventType
from .tool import Tool


class AgentTeam:
    def __init__(self, name: str):
        self.name = name
        self.agents: dict[str, Agent] = {}

    def add_agent(self, agent: Agent) -> 'AgentTeam':
        self.agents[agent.name] = agent
        self._inject_team_tools(agent)
        return self

    def _inject_team_tools(self, agent: Agent):
        team = self
        agent_name = agent.name

        def send_message(to_agent: str, message: str) -> str:
            team._send(agent_name, to_agent, message)
            return f"Message sent to {to_agent}"

        def broadcast(message: str) -> str:
            count = team._broadcast(agent_name, message)
            return f"Broadcast sent to {count} agents"

        agent.add_tools([
            Tool(
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
            ),
            Tool(
                func=broadcast,
                name="broadcast",
                description="Broadcast a message to all other agents in the team",
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
            ),
        ])

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
        for name, agent in self.agents.items():
            if name != from_agent:
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
