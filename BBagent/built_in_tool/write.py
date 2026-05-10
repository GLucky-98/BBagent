"""
Write tool - Write content to a file, creating directories as needed.
"""
import os
from pathlib import Path

from ..core.tool import Tool


class WriteOperations:
    def write_file(self, absolute_path: str, content: str) -> None:
        with open(absolute_path, "w", encoding="utf-8") as f:
            f.write(content)

    def access(self, absolute_path: str) -> bool:
        if os.path.exists(absolute_path):
            return os.access(absolute_path, os.W_OK)
        parent = os.path.dirname(absolute_path)
        return os.access(parent, os.W_OK)

    def makedirs(self, absolute_path: str) -> None:
        os.makedirs(absolute_path, exist_ok=True)

    def exists(self, absolute_path: str) -> bool:
        return os.path.exists(absolute_path)


def create_write_func(cwd: str = ".", create_directories: bool = True):
    operations = WriteOperations()

    def write_func(
        path: str,
        content: str,
    ) -> str:
        if not path:
            return "Error: path is required"

        if os.path.isabs(path):
            resolved_path = path
        else:
            resolved_path = os.path.join(cwd, path)

        if create_directories:
            dir_path = os.path.dirname(resolved_path)
            if dir_path:
                try:
                    operations.makedirs(dir_path)
                except OSError as e:
                    return f"Error: Failed to create directory: {str(e)}"

        try:
            if os.path.exists(resolved_path) and not operations.access(resolved_path):
                return f"Error: Cannot write to file (permission denied): {path}"

            operations.write_file(resolved_path, content)

            file_size = os.path.getsize(resolved_path)
            line_count = content.count("\n") + 1

            return f"Wrote {line_count} lines ({file_size} bytes) to {path}"

        except Exception as e:
            return f"Error writing file: {str(e)}"

    return write_func


def create_write_tool(
    cwd: str = ".",
    create_directories: bool = True,
) -> Tool:
    write_func = create_write_func(cwd, create_directories)

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write (relative or absolute)",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["path", "content"],
    }

    return Tool(
        write_func,
        name="Write",
        description="Writes content to a file. Creates the file if it doesn't exist.",
        input_schema=input_schema,
    )

