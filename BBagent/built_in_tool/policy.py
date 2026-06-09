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

    # ── Read limits ──
    max_read_size: int = 30_000

    # ── Bash limits ──
    bash_max_output_size: int = 50_000
    bash_default_timeout: int = 60

    # ── SubAgent config ──
    sub_agent_model: Optional[dict] = None
    sub_agent_blocked_tools: Optional[list[str]] = None
