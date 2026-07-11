"""
Read uploaded file tool - read user-uploaded files by managed file_id.
"""
import re
from pathlib import Path

from ..core.tool import Tool
from .policy import Policy

DEFAULT_MAX_BYTES = 30_000
_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_path_segment(value: str) -> str:
    segment = _SAFE_SEGMENT_RE.sub("_", value.strip()).strip("._-")
    return segment or "unknown"


def _resolve_uploaded_file(policy: Policy | None, file_id: str) -> Path | None:
    if policy is None or not policy.uploaded_file_root or not policy.uploaded_file_owner_id:
        return None

    safe_owner = _safe_path_segment(policy.uploaded_file_owner_id)
    safe_file_id = _safe_path_segment(file_id)
    owner_root = (Path(policy.uploaded_file_root) / safe_owner).resolve()
    file_dir = (owner_root / safe_file_id).resolve()

    try:
        if not file_dir.is_dir() or not file_dir.is_relative_to(owner_root):
            return None
        files = [item for item in file_dir.iterdir() if item.is_file()]
    except OSError:
        return None

    if len(files) != 1:
        return None
    return files[0].resolve()


def create_read_file_tool(
    policy_or_config: Policy | dict | None = None,
) -> Tool:
    policy: Policy | None
    if isinstance(policy_or_config, Policy):
        policy = policy_or_config
    elif isinstance(policy_or_config, dict):
        policy = Policy(**policy_or_config.get("policy", {})) if policy_or_config.get("policy") else None
    else:
        policy = None

    max_bytes = policy.max_read_size if policy is not None else DEFAULT_MAX_BYTES

    def read_file_func(
        file_id: str,
        offset: int | None = None,
        limit: int | None = None,
    ) -> str:
        if not file_id:
            return "Error: file_id is required"

        resolved_path = _resolve_uploaded_file(policy, file_id)
        if resolved_path is None:
            return f"Error: File not found or not accessible: {file_id}"

        try:
            with resolved_path.open("rb") as f:
                head = f.read(8192)
                if head and head.count(b"\x00") > len(head) * 0.01:
                    return (
                        f"Error: File appears to be binary and cannot be read as text: {file_id}. "
                        "If this is an image, it may already be included directly in the user message."
                    )
                f.seek(0)
                raw_content = f.read()

            try:
                content = raw_content.decode("utf-8")
            except UnicodeDecodeError:
                return f"Error: File is not valid UTF-8 text: {file_id}"

            lines = content.splitlines()
            total_lines = len(lines)
            start = max(0, offset - 1) if offset is not None else 0
            end = min(start + limit, total_lines) if limit is not None else total_lines
            selected_lines = lines[start:end]
            result_content = "\n".join(selected_lines)

            truncated = False
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
                f"\n[File ID: {file_id} | Name: {resolved_path.name} "
                f"| Lines: {window_start}-{window_end}/{total_lines} "
                f"| Returned: {lines_read} lines | Size: {bytes_read} bytes]"
            )
            return "\n".join(output_parts)

        except Exception as e:
            return f"Error reading file: {e!s}"

    input_schema = {
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "Managed uploaded file id shown in the user's [Files] list.",
            },
            "offset": {
                "type": "number",
                "description": "Line number to start reading from (1-indexed).",
            },
            "limit": {
                "type": "number",
                "description": "Maximum number of lines to read.",
            },
        },
        "required": ["file_id"],
    }

    return Tool(
        read_file_func,
        name="read_file",
        description=(
            "Read a user-uploaded file by file_id from managed local storage. "
            "Use this for uploaded text files instead of bash or raw filesystem paths."
        ),
        input_schema=input_schema,
        source="built_in",
    )
