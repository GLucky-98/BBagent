"""
Policy module - Centralized configuration for all built-in tools.
Aggregates every tool's closure parameters (cwd, limits)
into a single Policy dataclass. Each tool extracts what it needs.
"""
from dataclasses import dataclass


@dataclass
class Policy:
    cwd: str = "."

    # ── Read limits ──
    max_read_size: int = 30_000
    uploaded_file_root: str | None = None
    uploaded_file_owner_id: str | None = None

    # ── Bash limits ──
    bash_max_output_size: int = 50_000
    bash_default_timeout: int = 60

    # ── Web limits ──
    web_timeout: float = 10.0
    web_max_response_size: int = 200_000
    web_max_output_size: int = 20_000
    web_search_max_results: int = 5
    web_allowed_domains: list[str] | None = None
    web_user_agent: str = "BBagent/0.1"

    # ── SubAgent config ──
    sub_agent_model: dict | None = None
    sub_agent_blocked_tools: list[str] | None = None
