"""
SubAgent tool - Delegate tasks to a sub-agent with its own model and tools.
"""
import inspect
from uuid import uuid4 as uuid

from ..core.tool import Tool
from ..core.agent import SubAgent
from ..core.model import Model
from .policy import Policy


async def create_sub_agent_tool(
    policy_or_config: Policy | dict | None = None,
) -> Tool:
    if isinstance(policy_or_config, Policy):
        policy = policy_or_config
    elif isinstance(policy_or_config, dict):
        policy = Policy(**policy_or_config.get("policy", {})) if policy_or_config.get("policy") else None
    else:
        policy = None

    if policy is not None:
        sub_agent_model = policy.sub_agent_model
        blocked_tools: list[str] = list(policy.sub_agent_blocked_tools or [])
    else:
        sub_agent_model = None
        blocked_tools = []

    if "sub_agent" not in blocked_tools:
        blocked_tools.append("sub_agent")

    from . import TOOL_CREATOR

    all_sub_tools: dict[str, Tool] = {}
    for creator_key, creator in TOOL_CREATOR.items():
        if creator_key == "sub_agent":
            continue
        base_name = creator_key
        try:
            sig = inspect.signature(creator)
            accepts_policy = len(sig.parameters) > 0
            if accepts_policy:
                tool = creator(policy) if not inspect.iscoroutinefunction(creator) else await creator(policy)
            else:
                tool = creator()
            all_sub_tools[base_name] = tool
        except Exception:
            continue

    blocked_set = set(blocked_tools)

    desc_lines = [
        "Delegate a task to a sub-agent with its own model. The sub-agent works autonomously and returns a single result. Specify which tools the sub-agent can use via the allowed_tools parameter.",
        "",
        "Available built-in tools:",
    ]
    for key in sorted(all_sub_tools.keys()):
        tool = all_sub_tools[key]
        tag = " [BLOCKED]" if key in blocked_set else ""
        desc_lines.append(f"- {key}{tag}: {tool.description}")

    description = "\n".join(desc_lines)

    async def sub_agent_func(task: str, system_prompt: str, allowed_tools: list[str]) -> str:
        if not sub_agent_model:
            return "Error: No sub-agent model configured. Set sub_agent_model in Policy."

        effective = [t for t in allowed_tools if t in all_sub_tools and t not in blocked_set]
        sub_tools = [all_sub_tools[t] for t in effective]

        try:
            model = Model.from_config_dict(sub_agent_model)
        except Exception as e:
            return f"Error: Failed to create sub-agent model: {e}"

        sub = SubAgent(
            model=model,
            tools=sub_tools,
            system_prompt=system_prompt,
            name=f"sub_{uuid().hex[:8]}",
        )
        return await sub.run(task)

    input_schema = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Task description for the sub-agent",
            },
            "system_prompt": {
                "type": "string",
                "description": "System prompt guiding the sub-agent's behavior",
            },
            "allowed_tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tool names the sub-agent is allowed to use (e.g. read, grep, bash)",
            },
        },
        "required": ["task", "system_prompt", "allowed_tools"],
    }

    return Tool(
        sub_agent_func,
        name="sub_agent",
        description=description,
        input_schema=input_schema,
        source="built_in",
    )
