"""
Edit tool - Edit file contents by replacing specific text.
"""
import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from ..core.tool import Tool
from .policy import Policy, resolve_and_check_path


class EditOperations:
    def read_file(self, absolute_path: str) -> str:
        with open(absolute_path, "r", encoding="utf-8") as f:
            return f.read()

    def write_file(self, absolute_path: str, content: str) -> None:
        with open(absolute_path, "w", encoding="utf-8") as f:
            f.write(content)

    def access(self, absolute_path: str) -> bool:
        return os.access(absolute_path, os.W_OK)


def create_edit_func(policy: Optional[Policy] = None):

    if policy is not None:
        cwd = policy.cwd
    else:
        cwd = "."

    operations = EditOperations()

    def edit_func(
        path: str,
        old_string: str,
        new_string: str,
        partial_match: bool = False,
    ) -> str:
        if not path:
            return "Error: path is required"
        if old_string == "":
            return "Error: old_string is required"

        if policy is not None:
            resolved, err = resolve_and_check_path(path, policy)
            if err:
                return f"Error: {err}"
            resolved_path = resolved
        else:
            if os.path.isabs(path):
                resolved_path = path
            else:
                resolved_path = os.path.join(cwd, path)

        if not os.path.exists(resolved_path):
            return f"Error: File not found: {path}"

        if not operations.access(resolved_path):
            return f"Error: Cannot write to file (permission denied): {path}"

        try:
            content = operations.read_file(resolved_path)

            if partial_match:
                if old_string not in content:
                    return f"Error: old_string not found in file: {path}"
                new_content = content.replace(old_string, new_string, 1)
            else:
                count = content.count(old_string)
                if count == 0:
                    return f"Error: old_string not found in file: {path}"
                if count > 1:
                    return f"Error: old_string appears {count} times. Use partial_match=true to replace first occurrence."
                new_content = content.replace(old_string, new_string, 1)

            if new_content == content:
                return "Error: No changes made (old_string and new_string are identical)"

            operations.write_file(resolved_path, new_content)

            old_lines = old_string.count("\n")
            new_lines = new_string.count("\n")
            lines_changed = abs(new_lines - old_lines) + 1

            return f"Applied edit to {path} ({lines_changed} lines changed)"

        except Exception as e:
            return f"Error editing file: {str(e)}"

    return edit_func


def create_edit_tool(policy: Optional[Policy] = None) -> Tool:
    edit_func = create_edit_func(policy)

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to edit (relative or absolute)",
            },
            "old_string": {
                "type": "string",
                "description": "The exact text to replace. Must match existing content exactly.",
            },
            "new_string": {
                "type": "string",
                "description": "The replacement text",
            },
            "partial_match": {
                "type": "boolean",
                "description": "If true, replaces the first occurrence even if other occurrences exist. Default: false",
            },
        },
        "required": ["path", "old_string", "new_string"],
    }

    return Tool(
        edit_func,
        name="Edit",
        description="Makes a precise edit to a file. old_string must match the existing content exactly.",
        input_schema=input_schema,
        source="built_in.edit",
        config={"policy": asdict(policy)} if policy else {},
    )
