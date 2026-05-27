"""
Read tool - Read file contents with optional truncation and offset/limit support.
"""
import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from ..core.tool import Tool
from .policy import Policy, resolve_and_check_path


DEFAULT_MAX_BYTES = 500_000
DEFAULT_MAX_LINES = 10_000


def create_read_func(policy: Optional[Policy] = None):

    if policy is not None:
        cwd = policy.cwd
        max_bytes = policy.max_read_size
        max_lines = policy.max_read_lines
    else:
        cwd = "."
        max_bytes = DEFAULT_MAX_BYTES
        max_lines = DEFAULT_MAX_LINES

    def read_func(
        path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> str:
        if not path:
            return "Error: path is required"

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

        if not os.access(resolved_path, os.R_OK):
            return f"Error: Cannot read file: {resolved_path}"

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

            truncation_type = None
            truncated = False

            if len(selected_lines) > max_lines:
                truncated = True
                truncation_type = "lines"
                selected_lines = selected_lines[:max_lines]

            result_content = "\n".join(selected_lines)

            encoded = result_content.encode("utf-8")
            if len(encoded) > max_bytes:
                truncated = True
                truncation_type = "bytes"
                result_content = encoded[:max_bytes].decode("utf-8", errors="ignore")

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


def create_read_tool(policy: Optional[Policy] = None) -> Tool:
    read_func = create_read_func(policy)

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
        source="built_in.read",
        config={"policy": asdict(policy)} if policy else {},
    )
