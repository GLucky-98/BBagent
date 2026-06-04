"""Factory pattern for State resource management.

Each factory is a singleton responsible for the full lifecycle of one
resource type (CRUD + persistence + runtime instances). The State class
acts as coordinator, initializing factories in dependency order and
injecting cross-factory references.
"""

import uuid

# --- Deterministic ID namespaces (stable after release) ---

_BUILTIN_TOOL_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
_MCP_TOOL_NS = uuid.UUID("5b3a6e29-2c47-4b71-8c5b-3b0c8f7d2e91")
_SKILL_NS = uuid.UUID("c2d3e4f5-6a7b-8c9d-0e1f-234567890abc")


def _next_id() -> str:
    """Generate a fresh UUID4 string for new entities."""
    return str(uuid.uuid4())


def _builtin_tool_id(short_name: str) -> str:
    """Stable builtin tool id derived from short_name."""
    return str(uuid.uuid5(_BUILTIN_TOOL_NS, f"builtin::{short_name}"))


def _mcp_tool_id(mcp_server_id: str, raw_name: str) -> str:
    """Stable MCP tool id derived from (server_id, raw_name)."""
    return str(uuid.uuid5(_MCP_TOOL_NS, f"{mcp_server_id}::{raw_name}"))


def _skill_id(skill_path: str) -> str:
    """Stable skill id derived from file path."""
    return str(uuid.uuid5(_SKILL_NS, skill_path))


def _safe_filename(s: str) -> str:
    """Sanitize a string for use in a filename."""
    return "".join(c for c in s if c.isalnum() or c in "._-") or "_"
