"""
LS tool - List directory contents.
"""
import os
from pathlib import Path
from typing import Optional

from ..core.tool import Tool


class LsOperations:
    def list_dir(self, absolute_path: str) -> list[str]:
        return os.listdir(absolute_path)

    def is_dir(self, absolute_path: str) -> bool:
        return os.path.isdir(absolute_path)

    def is_file(self, absolute_path: str) -> bool:
        return os.path.isfile(absolute_path)

    def get_size(self, absolute_path: str) -> int:
        if self.is_file(absolute_path):
            return os.path.getsize(absolute_path)
        return 0

    def exists(self, absolute_path: str) -> bool:
        return os.path.exists(absolute_path)


def create_ls_func(cwd: str = "."):
    operations = LsOperations()

    def format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"

    def ls_func(
        path: Optional[str] = None,
        show_hidden: bool = True,
    ) -> str:
        if path is None:
            resolved_path = cwd
        elif os.path.isabs(path):
            resolved_path = path
        else:
            resolved_path = os.path.join(cwd, path)

        if not operations.exists(resolved_path):
            return f"Error: Path not found: {path or cwd}"

        if not operations.is_dir(resolved_path):
            return f"Error: Path is not a directory: {path}"

        try:
            entries = operations.list_dir(resolved_path)

            if not show_hidden:
                entries = [e for e in entries if not e.startswith(".")]

            entries.sort(key=lambda x: (not operations.is_dir(os.path.join(resolved_path, x)), x.lower()))

            dirs = []
            files = []

            for entry_name in entries:
                entry_path = os.path.join(resolved_path, entry_name)
                if operations.is_dir(entry_path):
                    dirs.append(entry_name)
                else:
                    size = operations.get_size(entry_path)
                    size_str = format_size(size)
                    files.append((entry_name, size_str))

            output_lines = []
            for entry in dirs:
                output_lines.append(f"[DIR]  {entry}/")
            for entry_name, size_str in files:
                output_lines.append(f"[FILE] {entry_name} ({size_str})")

            if not output_lines:
                return "(empty directory)"

            return "\n".join(output_lines)

        except Exception as e:
            return f"Error listing directory: {str(e)}"

    return ls_func


def create_ls_tool(cwd: str = ".") -> Tool:
    ls_func = create_ls_func(cwd)

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory to list (defaults to current directory)",
            },
            "show_hidden": {
                "type": "boolean",
                "description": "Show hidden files (starting with .)",
            },
        },
        "required": [],
    }

    return Tool(
        ls_func,
        name="LS",
        description="Lists the contents of a directory.",
        input_schema=input_schema,
    )

