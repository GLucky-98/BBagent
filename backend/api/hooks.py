"""GET /api/hooks — hook descriptor endpoint.

Returns metadata about each available built-in hook (name, displayName,
defaultEnabled, per-hook field sections) plus a list of "sharedSections"
(fields consumed by multiple hooks).

The frontend uses this descriptor to render the hook configuration dialog
dynamically, without hardcoding field names. Default values are read from
the canonical BuiltinHookConfig dataclass so they stay in sync.
"""
from fastapi import APIRouter

from bbagent.built_in_hook import HOOK_CREATOR, BuiltinHookConfig

from backend.schemas import (
    HookDescriptor,
    HookFieldSchema,
    HookListResponse,
    HookSection,
)
from backend.logging import get_backend_logger

logger = get_backend_logger("api.hooks")
router = APIRouter()


# Field type hints per BuiltinHookConfig field. Drives the frontend input
# renderer. New BuiltinHookConfig fields are ignored by the schema unless
# added here.
_FIELD_TYPES: dict[str, str] = {
    # Memory subsystem
    "memory_system_prompt": "text",
    "add_memory_tool_prompt": "text",
    "extract_prompt": "text",
    "extract_subagent_add_memory_tool_prompt": "text",
    "extract_user_prompt": "text",
    "clean_prompt": "text",
    "clean_user_prompt": "text",
    "clean_mutation_threshold": "number",
    "max_inject": "number",
    "max_candidates": "number",
    "extract_turn_interval": "number",
    "rrf_k": "number",
    "bm25_weight": "float",
    "vector_weight": "float",
    "inject_oversample_factor": "number",
    "inject_oversample_cap": "number",
    # Compress subsystem
    "compress_prompt": "text",
    "compress_prefix": "string",
    "keep_recent_turns": "number",
    "compression_threshold": "float",
    # Shared
    "merge_ratio": "float",
    "small_turn_cap": "number",
}


def _make_field(key: str, label: str, description: str = "") -> HookFieldSchema:
    """Build a HookFieldSchema from a BuiltinHookConfig field, using its
    dataclass default as the frontend default value."""
    default = getattr(BuiltinHookConfig(), key, None)
    return HookFieldSchema(
        key=key,
        type=_FIELD_TYPES.get(key, "string"),
        label=label,
        default=default,
        description=description,
    )


# Per-hook field sections. Add a new entry here to expose a new hook.
_HOOK_DEFINITIONS: list[dict] = [
    {
        "name": "built_in.memory",
        "displayName": "Memory",
        "description": (
            "Long-term memory system. Stores user-related facts across "
            "conversations and injects relevant context before each turn."
        ),
        "defaultEnabled": True,
        "fieldSections": [
            {
                "title": "Memory",
                "fields": [
                    _make_field("memory_system_prompt", "Memory System Prompt"),
                    _make_field("add_memory_tool_prompt", "Add Memory Tool Prompt"),
                    _make_field("extract_prompt", "Extract Prompt"),
                    _make_field(
                        "extract_subagent_add_memory_tool_prompt",
                        "Subagent Tool Prompt",
                    ),
                    _make_field("extract_user_prompt", "Extract User Prompt"),
                    _make_field("clean_prompt", "Clean Prompt"),
                    _make_field("clean_user_prompt", "Clean User Prompt"),
                    _make_field("clean_mutation_threshold", "Clean Mutation Threshold"),
                    _make_field("max_inject", "Max Inject"),
                    _make_field("max_candidates", "Max Candidates"),
                    _make_field("extract_turn_interval", "Extract Turn Interval"),
                    _make_field("rrf_k", "RRF K"),
                    _make_field("bm25_weight", "BM25 Weight"),
                    _make_field("vector_weight", "Vector Weight"),
                    _make_field("inject_oversample_factor", "Inject Oversample Factor"),
                    _make_field("inject_oversample_cap", "Inject Oversample Cap"),
                ],
            }
        ],
    },
    {
        "name": "built_in.compress",
        "displayName": "Context Compression",
        "description": (
            "Compresses older turns to control context window size. "
            "Triggers when token usage exceeds compression_threshold."
        ),
        "defaultEnabled": True,
        "fieldSections": [
            {
                "title": "Compression",
                "fields": [
                    _make_field("compress_prompt", "Compress Prompt"),
                    _make_field("compress_prefix", "Compress Prefix"),
                    _make_field("keep_recent_turns", "Keep Recent Turns"),
                    _make_field("compression_threshold", "Compression Threshold"),
                ],
            }
        ],
    },
]


# Shared fields used by multiple hooks. Exposed as a separate "Shared" section
# in the frontend so the user sees a single place to edit them.
_SHARED_SECTIONS: list[dict] = [
    {
        "title": "Shared",
        "fields": [
            HookFieldSchema(
                key="submodelId",
                type="modelId",
                label="Sub-model",
                default="",
                description=(
                    "Model used by the memory subsystem. "
                    "Empty = use the agent's main model."
                ),
            ),
            _make_field("merge_ratio", "Merge Ratio"),
            _make_field("small_turn_cap", "Small Turn Cap"),
        ],
    }
]


@router.get("", response_model=HookListResponse)
async def list_hooks():
    """Return the descriptor for all available built-in hooks.

    Each hook carries:
      - name, displayName, description, defaultEnabled
      - fieldSections: per-hook field groups

    Plus a top-level `sharedSections` for fields consumed by multiple hooks.
    """
    # Filter hook definitions by what's actually registered in HOOK_CREATOR.
    # This guards against typos and stale definitions.
    hooks = []
    for hd in _HOOK_DEFINITIONS:
        if hd["name"] not in HOOK_CREATOR:
            logger.warning(
                f"Hook '{hd['name']}' in descriptor not found in HOOK_CREATOR, skipping"
            )
            continue
        hooks.append(HookDescriptor(**hd))

    shared = [HookSection(**s) for s in _SHARED_SECTIONS]
    return HookListResponse(hooks=hooks, sharedSections=shared)
