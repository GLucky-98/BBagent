"""
Find tool - Find files by name pattern (glob matching).
"""
import os
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.tool import Tool


class FindOperations:
    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def is_dir(self, path: str) -> bool:
        return os.path.isdir(path)


def create_find_func(cwd: str = "."):
    operations = FindOperations()

    def match_glob(base_path: str, pattern: str) -> list[str]:
        base = Path(base_path)

        if "**" in pattern:
            if pattern.startswith("**/"):
                actual_pattern = pattern[3:]
            else:
                actual_pattern = pattern
            for match in base.rglob(actual_pattern):
                yield str(match)
        else:
            for match in base.glob(pattern):
                yield str(match)

    def find_func(
        pattern: str,
        path: Optional[str] = None,
        file_only: bool = True,
        dir_only: bool = False,
        max_results: int = 100,
    ) -> str:
        if not pattern:
            return "Error: pattern is required"

        if path is None:
            search_path = cwd
        elif os.path.isabs(path):
            search_path = path
        else:
            search_path = os.path.join(cwd, path)

        if not operations.exists(search_path):
            return f"Error: Path not found: {path or cwd}"

        if not operations.is_dir(search_path):
            return f"Error: Path is not a directory: {path}"

        try:
            matches = list(match_glob(search_path, pattern))

            filtered_matches = []
            for match in matches:
                if file_only and not dir_only:
                    if os.path.isfile(match):
                        filtered_matches.append(match)
                elif dir_only and not file_only:
                    if os.path.isdir(match):
                        filtered_matches.append(match)
                else:
                    filtered_matches.append(match)

            filtered_matches = sorted(filtered_matches)[:max_results]

            relative_matches = [
                os.path.relpath(m, cwd).replace("\\", "/")
                for m in filtered_matches
            ]

            if not relative_matches:
                return "No matches found"

            return "\n".join(relative_matches)

        except Exception as e:
            return f"Error finding files: {str(e)}"

    return find_func


def create_find_tool(cwd: str = ".") -> Tool:
    find_func = create_find_func(cwd)

    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match (e.g., *.py, **/*.ts, src/**/*.js)",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (defaults to cwd)",
            },
            "file_only": {
                "type": "boolean",
                "description": "Only return files (not directories)",
            },
            "dir_only": {
                "type": "boolean",
                "description": "Only return directories (not files)",
            },
            "max_results": {
                "type": "number",
                "description": "Maximum number of results to return",
            },
        },
        "required": ["pattern"],
    }

    return Tool(
        find_func,
        name="Glob",
        description="Finds files by name pattern using glob matching.",
        input_schema=input_schema,
    )

