"""
Memory system - long-term memory for agents.

Provides memory storage, retrieval (hybrid search: vector + BM25),
extraction from conversations, and maintenance (cleanup).
Exposes tool factories for agent integration and hook factories
for automatic lifecycle management.
"""

from .memory import Memory, MemoryManager
from .embedding import Embedding, OllamaEmbedding
from .memory_tool import (
    create_add_memory_tool,
    create_delete_memory_tool,
    create_search_memory_tool,
)
from .memory_hook import create_memory_hook,extract_memories

# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "Memory", "MemoryManager",
    "Embedding", "OllamaEmbedding",
    "create_add_memory_tool", "create_delete_memory_tool", "create_search_memory_tool",
    "create_memory_hook",
    "extract_memories",
]

