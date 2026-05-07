"""
Read tool - Read file contents with optional truncation and offset/limit support.
"""
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.tool import Tool


DEFAULT_MAX_BYTES = 500_000
DEFAULT_MAX_LINES = 10_000


class ReadOperations:
    def read_file(self, absolute_path: str) -> bytes:
        with open(absolute_path, "rb") as f:
            return f.read()

    def access(self, absolute_path: str) -> None:
        if not os.access(absolute_path, os.R_OK):
            raise PermissionError(f"Cannot read file: {absolute_path}")

    def exists(self, absolute_path: str) -> bool:
        return os.path.exists(absolute_path)


def create_read_func(cwd: str = ".", max_bytes: int = DEFAULT_MAX_BYTES, max_lines: int = DEFAULT_MAX_LINES):
    operations = ReadOperations()

    def read_func(
        path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> str:
        if not path:
            return "Error: path is required"

        if os.path.isabs(path):
            resolved_path = path
        else:
            resolved_path = os.path.join(cwd, path)

        try:
            operations.access(resolved_path)
        except PermissionError as e:
            return f"Error: {str(e)}"
        except FileNotFoundError:
            return f"Error: File not found: {path}"

        try:
            with open(resolved_path, "rb") as f:
                raw_content = f.read()

            try:
                content = raw_content.decode("utf-8")
            except UnicodeDecodeError:
                return f"Error: File is not a valid text file: {path}"

            lines = content.splitlines()
            total_lines = len(lines)

            if offset is not None:
                start = max(0, offset - 1)
            else:
                start = 0

            if limit is not None:
                end = min(start + limit, total_lines)
            else:
                end = total_lines

            selected_lines = lines[start:end]
            result_content = "\n".join(selected_lines)

            truncation_type = None
            truncated = False

            if len(result_content.encode("utf-8")) > max_bytes:
                truncated = True
                truncation_type = "bytes"
                result_content = result_content[:max_bytes]

            if len(selected_lines) > max_lines:
                truncated = True
                truncation_type = "lines"
                result_content = "\n".join(selected_lines[:max_lines])

            lines_read = len(selected_lines)
            bytes_read = len(result_content.encode("utf-8"))

            output_parts = [result_content]

            if truncated:
                output_parts.append(f"\n[truncated: {truncation_type}]")

            output_parts.append(f"\n[File: {path} | Lines: {lines_read}/{total_lines} | Size: {bytes_read} bytes]")

            return "\n".join(output_parts)

        except Exception as e:
            return f"Error reading file: {str(e)}"

    return read_func


def create_read_tool(
    cwd: str = ".",
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_lines: int = DEFAULT_MAX_LINES,
) -> Tool:
    read_func = create_read_func(cwd, max_bytes, max_lines)

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read (relative or absolute)",
            },
            "offset": {
                "type": "number",
                "description": "Line number to start reading from (1-indexed)",
            },
            "limit": {
                "type": "number",
                "description": "Maximum number of lines to read",
            },
        },
        "required": ["path"],
    }

    return Tool(
        read_func,
        name="Read",
        description="Read the complete contents of a file.",
        input_schema=input_schema,
    )


ReadTool = Tool
