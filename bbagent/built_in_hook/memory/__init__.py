"""
Memory system - long-term memory for agents.

Provides memory storage, retrieval (hybrid search: vector + BM25),
extraction from conversations, and maintenance (cleanup).
Exposes tool factories for agent integration and hook factories
for automatic lifecycle management.
"""

from .embedding import Embedding, OllamaEmbedding
from .memory import Memory, MemoryManager
from .memory_hook import (
    ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT,
    CLEAN_SYSTEM_PROMPT,
    CLEAN_USER_PROMPT,
    EXTRACT_SYSTEM_PROMPT,
    EXTRACT_USER_PROMPT,
    create_memory_hook,
    extract_memories,
)
from .memory_tool import (
    ADD_MEMORY_TOOL_DESCRIPTION,
    create_add_memory_tool,
    create_delete_memory_tool,
    create_inject_memories_tool,
    inject_memory_context,
)
from .runtime import MemoryRuntime

__all__ = [
    "ADD_MEMORY_TOOL_DESCRIPTION",
    "ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT",
    "CLEAN_SYSTEM_PROMPT",
    "CLEAN_USER_PROMPT",
    "EXTRACT_SYSTEM_PROMPT",
    "EXTRACT_USER_PROMPT",
    "Embedding",
    "Memory",
    "MemoryManager",
    "MemoryRuntime",
    "OllamaEmbedding",
    "create_add_memory_tool",
    "create_delete_memory_tool",
    "create_inject_memories_tool",
    "create_memory_hook",
    "extract_memories",
    "inject_memory_context",
]
