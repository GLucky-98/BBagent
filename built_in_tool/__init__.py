"""
Tools package - File system and shell operation tools.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.tool import Tool

from .bash import create_bash_tool
from .edit import create_edit_tool
from .find import create_find_tool
from .grep import create_grep_tool
from .ls import create_ls_tool
from .read import create_read_tool
from .write import create_write_tool


def create_tool(func, name=None, description=None, input_schema=None):
    return Tool(func, name, description, input_schema)


async def create_all_tools(cwd: str = ".") -> dict[str, Tool]:
    return {
        "read": create_read_tool(cwd),
        "write": create_write_tool(cwd),
        "edit": create_edit_tool(cwd),
        "bash": await create_bash_tool(cwd),
        "grep": create_grep_tool(cwd),
        "find": create_find_tool(cwd),
        "ls": create_ls_tool(cwd),
    }


async def create_coding_tools(cwd: str = ".") -> dict[str, Tool]:
    return {
        "read": create_read_tool(cwd),
        "write": create_write_tool(cwd),
        "edit": create_edit_tool(cwd),
        "bash": await create_bash_tool(cwd),
    }


def create_readonly_tools(cwd: str = ".") -> dict[str, Tool]:
    return {
        "read": create_read_tool(cwd),
        "grep": create_grep_tool(cwd),
        "find": create_find_tool(cwd),
        "ls": create_ls_tool(cwd),
    }


__all__ = [
    "Tool",
    "create_tool",
    "ReadTool",
    "create_read_tool",
    "WriteTool",
    "create_write_tool",
    "EditTool",
    "create_edit_tool",
    "BashTool",
    "create_bash_tool",
    "GrepTool",
    "create_grep_tool",
    "FindTool",
    "create_find_tool",
    "LsTool",
    "create_ls_tool",
    "create_all_tools",
    "create_coding_tools",
    "create_readonly_tools",
]
