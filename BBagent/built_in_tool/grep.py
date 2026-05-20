"""
Grep tool - Search for patterns in files using regular expressions.
"""
import fnmatch
import os
import re
from pathlib import Path
from typing import Optional

from ..core.tool import Tool
from .policy import Policy, resolve_and_check_path


class GrepOperations:
    def read_file(self, absolute_path: str) -> str:
        with open(absolute_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()


def create_grep_func(policy: Optional[Policy] = None):

    if policy is not None:
        cwd = policy.cwd
    else:
        cwd = "."

    operations = GrepOperations()

    def grep_func(
        pattern: str,
        path: str,
        context: int = 0,
        case_sensitive: bool = True,
        is_regex: bool = True,
        file_pattern: Optional[str] = None,
        max_results: int = 100,
    ) -> str:
        if not pattern:
            return "Error: pattern is required"
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

        if not os.path.exists(resolved_path):
            return f"Error: Path not found: {path}"

        try:
            files_to_search = []

            if os.path.isfile(resolved_path):
                files_to_search = [resolved_path]
            else:
                for root, dirs, files in os.walk(resolved_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if file_pattern:
                            basename = os.path.basename(file_path)
                            if not fnmatch.fnmatch(basename, file_pattern):
                                continue
                        files_to_search.append(file_path)

            flags = 0 if case_sensitive else re.IGNORECASE

            if is_regex:
                try:
                    compiled_pattern = re.compile(pattern, flags)
                except re.error as e:
                    return f"Error: Invalid regex pattern: {str(e)}"
            else:
                if case_sensitive:
                    compiled_pattern = re.compile(re.escape(pattern))
                else:
                    compiled_pattern = re.compile(re.escape(pattern), re.IGNORECASE)

            matches = []

            for file_path in files_to_search:
                if len(matches) >= max_results:
                    break

                try:
                    content = operations.read_file(file_path)
                    lines = content.splitlines()

                    for i, line in enumerate(lines):
                        if compiled_pattern.search(line):
                            context_before = []
                            context_after = []

                            if context > 0:
                                start_ctx = max(0, i - context)
                                end_ctx = min(len(lines), i + context + 1)
                                context_before = lines[start_ctx:i]
                                context_after = lines[i + 1 : end_ctx]

                            rel_path = os.path.relpath(file_path, cwd).replace("\\", "/")

                            if context > 0:
                                output_parts = [f"{rel_path}:{i + 1}"]
                                for ctx_line in context_before:
                                    output_parts.append(f"  {ctx_line}")
                                output_parts.append(f"> {line}")
                                for ctx_line in context_after:
                                    output_parts.append(f"  {ctx_line}")
                                matches.append("\n".join(output_parts))
                            else:
                                matches.append(f"{rel_path}:{i + 1}: {line.rstrip()}")

                            if len(matches) >= max_results:
                                break

                except (OSError, UnicodeDecodeError):
                    continue

            if not matches:
                return "No matches found"

            return "\n".join(matches)

        except Exception as e:
            return f"Error searching files: {str(e)}"

    return grep_func


def create_grep_tool(policy: Optional[Policy] = None) -> Tool:
    grep_func = create_grep_func(policy)

    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "The pattern to search for (regex or literal string)",
            },
            "path": {
                "type": "string",
                "description": "Path to search in (file or directory)",
            },
            "context": {
                "type": "number",
                "description": "Number of context lines before and after matches",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Whether the search is case sensitive",
            },
            "is_regex": {
                "type": "boolean",
                "description": "Whether the pattern is a regular expression",
            },
            "file_pattern": {
                "type": "string",
                "description": "Only search in files matching this pattern (e.g., *.py)",
            },
            "max_results": {
                "type": "number",
                "description": "Maximum number of results to return",
            },
        },
        "required": ["pattern", "path"],
    }

    return Tool(
        grep_func,
        name="Grep",
        description="Searches for a pattern in files using regular expressions.",
        input_schema=input_schema,
    )
