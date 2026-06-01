"""
Write tool - Write content to a file, creating directories as needed.
"""
import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from ..core.tool import Tool
from .policy import Policy


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


def create_write_tool(
    policy_or_config: Policy | dict | None = None,
) -> Tool:
    if isinstance(policy_or_config, Policy):
        policy = policy_or_config
    elif isinstance(policy_or_config, dict):
        policy = Policy(**policy_or_config.get("policy", {})) if policy_or_config.get("policy") else None
    else:
        policy = None

    if policy is not None:
        cwd = policy.cwd
        max_write_size = policy.max_write_size
        create_directories = policy.write_create_directories
    else:
        cwd = "."
        max_write_size = 5 * 1024 * 1024
        create_directories = True

    operations = WriteOperations()

    def write_func(
        path: str,
        content: str,
    ) -> str:
        if not path:
            return "Error: path is required"

        if policy is not None:
            p = Path(path)
            resolved_path = str(p if p.is_absolute() else (Path(policy.cwd) / p).resolve())

            size = len(content.encode("utf-8"))
            if size > max_write_size:
                return f"Error: write content exceeds maximum size ({size} > {max_write_size} bytes)"
        else:
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
        source="built_in.write",
        config={"policy": asdict(policy)} if policy else {},
    )
