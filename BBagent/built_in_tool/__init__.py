"""
Tools package - File system and shell operation tools.
"""
from ..core.tool import Tool
from .policy import Policy

from .bash import create_bash_tool
from .edit import create_edit_tool
from .find import create_find_tool
from .grep import create_grep_tool
from .ls import create_ls_tool
from .read import create_read_tool
from .write import create_write_tool
from .sub_agent import create_sub_agent_tool


TOOL_CREATOR = {
    "read": create_read_tool,
    "write": create_write_tool,
    "edit": create_edit_tool,
    "bash": create_bash_tool,
    "find": create_find_tool,
    "grep": create_grep_tool,
    "ls": create_ls_tool,
    "sub_agent": create_sub_agent_tool,
}


async def create_all_tools(policy: Policy = None) -> dict[str, Tool]:
    return {
        "read": create_read_tool(policy),
        "write": create_write_tool(policy),
        "edit": create_edit_tool(policy),
        "bash": await create_bash_tool(policy),
        "grep": create_grep_tool(policy),
        "find": create_find_tool(policy),
        "ls": create_ls_tool(policy),
    }


async def create_coding_tools(policy: Policy = None) -> dict[str, Tool]:
    return {
        "read": create_read_tool(policy),
        "write": create_write_tool(policy),
        "edit": create_edit_tool(policy),
        "bash": await create_bash_tool(policy),
    }


def create_readonly_tools(policy: Policy = None) -> dict[str, Tool]:
    return {
        "read": create_read_tool(policy),
        "grep": create_grep_tool(policy),
        "find": create_find_tool(policy),
        "ls": create_ls_tool(policy),
    }


__all__ = [
    "Tool",
    "Policy",
    "TOOL_CREATOR",
    "create_read_tool",
    "create_write_tool",
    "create_edit_tool",
    "create_bash_tool",
    "create_grep_tool",
    "create_find_tool",
    "create_ls_tool",
    "create_sub_agent_tool",
    "create_all_tools",
    "create_coding_tools",
    "create_readonly_tools",
]
