"""
Memory system - long-term memory for agents.

Provides memory storage, retrieval (hybrid search: vector + BM25),
extraction from conversations, and maintenance (cleanup).
Exposes tool factories for agent integration and hook factories
for automatic lifecycle management.
"""

from .memory import Memory, MemoryManager
from .runtime import MemoryRuntime
from .embedding import Embedding, OllamaEmbedding
from .memory_tool import (
    create_add_memory_tool,
    create_delete_memory_tool,
    create_inject_memories_tool,
    inject_memory_context,
    ADD_MEMORY_TOOL_DESCRIPTION,
)
from .memory_hook import (
    create_memory_hook,
    extract_memories,
    EXTRACT_SYSTEM_PROMPT,
    EXTRACT_USER_PROMPT,
    CLEAN_SYSTEM_PROMPT,
    CLEAN_USER_PROMPT,
    ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT,
)


__all__ = [
    "Memory", "MemoryManager", "MemoryRuntime",
    "Embedding", "OllamaEmbedding",
    "create_add_memory_tool", "create_delete_memory_tool", "create_inject_memories_tool",
    "inject_memory_context",
    "create_memory_hook",
    "extract_memories",
    "ADD_MEMORY_TOOL_DESCRIPTION",
    "ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT",
    "EXTRACT_SYSTEM_PROMPT",
    "EXTRACT_USER_PROMPT",
    "CLEAN_SYSTEM_PROMPT",
    "CLEAN_USER_PROMPT",
]
