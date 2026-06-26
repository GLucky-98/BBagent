"""
Read tool - Read file contents with optional truncation and offset/limit support.
"""
import os
from pathlib import Path

from ..core.tool import Tool
from .policy import Policy

DEFAULT_MAX_BYTES = 30_000


def create_read_tool(
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
        max_bytes = policy.max_read_size
    else:
        cwd = "."
        max_bytes = DEFAULT_MAX_BYTES

    def read_func(
        path: str,
        offset: int | None = None,
        limit: int | None = None,
    ) -> str:
        if not path:
            return "Error: path is required"

        if policy is not None:
            p = Path(path)
            resolved_path = str(p if p.is_absolute() else (Path(policy.cwd) / p).resolve())
        else:
            resolved_path = path if os.path.isabs(path) else os.path.join(cwd, path)

        if not os.access(resolved_path, os.R_OK):
            return f"Error: Cannot read file: {resolved_path}"

        try:
            with open(resolved_path, "rb") as f:
                head = f.read(8192)
                if head and head.count(b"\x00") > len(head) * 0.01:
                    return f"Error: File appears to be binary: {path}"
                f.seek(0)
                raw_content = f.read()

            try:
                content = raw_content.decode("utf-8")
            except UnicodeDecodeError:
                return f"Error: File is not a valid text file: {path}"

            lines = content.splitlines()
            total_lines = len(lines)

            start = max(0, offset - 1) if offset is not None else 0

            end = min(start + limit, total_lines) if limit is not None else total_lines

            selected_lines = lines[start:end]

            truncated = False
            result_content = "\n".join(selected_lines)

            encoded = result_content.encode("utf-8")
            if len(encoded) > max_bytes:
                truncated = True
                result_content = encoded[:max_bytes].decode("utf-8", errors="ignore")

            lines_read = len(selected_lines)
            bytes_read = len(result_content.encode("utf-8"))

            window_start = (start + 1) if offset is not None else 1
            window_end = start + lines_read

            output_parts = [result_content]

            if truncated:
                output_parts.append("\n[truncated]")

            output_parts.append(
                f"\n[File: {path} | Lines: {window_start}-{window_end}/{total_lines}"
                f" | Returned: {lines_read} lines | Size: {bytes_read} bytes]"
            )

            return "\n".join(output_parts)

        except Exception as e:
            return f"Error reading file: {e!s}"

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
        name="read",
        description="Read the complete contents of a file.",
        input_schema=input_schema,
        source="built_in",
    )
