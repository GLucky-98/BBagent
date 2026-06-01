"""
Policy module - Centralized configuration for all built-in tools.
Aggregates every tool's closure parameters (cwd, limits)
into a single Policy dataclass. Each tool extracts what it needs.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Policy:
    cwd: str = "."

    # ── Read/write limits ──
    max_read_size: int = 200_000
    max_read_lines: int = 3_000
    max_write_size: int = 5 * 1024 * 1024
    write_create_directories: bool = True

    # ── Bash limits ──
    bash_max_output_lines: int = 1000
    bash_default_timeout: int = 60

    # ── SubAgent config ──
    sub_agent_model: Optional[dict] = None
    sub_agent_blocked_tools: Optional[list[str]] = None
