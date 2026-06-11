from .memory import (
    MemoryManager,
    MemoryRuntime,
    Embedding,
    OllamaEmbedding,
    create_add_memory_tool,
    create_memory_hook,
    extract_memories,
    EXTRACT_SYSTEM_PROMPT,
    EXTRACT_USER_PROMPT,
    CLEAN_SYSTEM_PROMPT,
    CLEAN_USER_PROMPT,
    ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT,
    ADD_MEMORY_TOOL_DESCRIPTION,
)
from .ctx_compress_hook import create_ctx_compress_hook, compress_session, COMPRESS_PROMPT, COMPRESS_PREFIX

from dataclasses import dataclass

from ..core import Agent, Model, HookContext, HookType

KEEP_RECENT_TURNS = 3
COMPRESSION_THRESHOLD = 0.8
MERGE_RATIO = 0.2
SMALL_TURN_CAP = 5000
RRF_K = 60
BM25_WEIGHT = 0.5
VECTOR_WEIGHT = 0.5

MAX_INJECT = 5
MAX_CANDIDATES = 50

MEMORY_SYSTEM_PROMPT = """
## Long-Term Memory System

You have access to a long-term memory system that stores important information about the user across conversations. This allows you to remember user details, preferences, and past experiences.

### Memory Storage
- Memory data is persisted at: {memory_dir}
- The memory system uses hybrid search (semantic vectors + keyword matching) to find relevant memories.

### Automatic Memory Retrieval
Before you receive each user message, the system automatically searches the memory store for relevant information. When found, memory context will be prepended to the user's message under a "[Relevant memories from past conversations]" section. Simply read it and use the provided context when it helps answer the user's question — you do not need to search for memories yourself.

### Available Memory Tool

**`{add_tool_name}`**: Use this to save important information about the user. Call it when:
- The user explicitly asks you to remember something
- You discover personal facts, preferences, or experiences about the user that will be useful in future conversations
- Save only things with lasting value — avoid trivial or temporary information

### Best Practices
- Proactively save discoveries about the user when they share meaningful new information
- Read the automatically provided memory context carefully — it may contain answers the user is asking for
- Do not overuse add_memory — only save genuinely useful, lasting information
"""


@dataclass
class BuiltinHookConfig:
    """Unified configuration for built-in hook builders in HOOK_CREATOR.
    Each builder reads only the fields relevant to its own subsystem."""

    # === Memory subsystem (consumed by _setup_memory) ===
    # System prompt template appended to agent.system_prompt after memory setup.
    memory_system_prompt: str = MEMORY_SYSTEM_PROMPT
    # Description shown on the add_memory tool that the memory builder injects.
    add_memory_tool_prompt: str = ADD_MEMORY_TOOL_DESCRIPTION
    # System prompt for the memory-extraction subagent.
    extract_prompt: str = EXTRACT_SYSTEM_PROMPT
    # Tool description used inside the extraction subagent.
    extract_subagent_add_memory_tool_prompt: str = ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT
    # User-side prompt for the extraction subagent.
    extract_user_prompt: str = EXTRACT_USER_PROMPT
    # System prompt for the memory-cleaning pass.
    clean_prompt: str = CLEAN_SYSTEM_PROMPT
    # User-side prompt for the memory-cleaning pass.
    clean_user_prompt: str = CLEAN_USER_PROMPT
    # When accumulated mutation count exceeds this, the cleaning pass runs.
    clean_mutation_threshold: int = 50
    # Max number of memories injected before a user message.
    max_inject: int = MAX_INJECT
    # Max candidate memories retrieved before reranking.
    max_candidates: int = MAX_CANDIDATES
    # RRF k used to fuse BM25 and vector retrieval scores.
    rrf_k: int = RRF_K
    # BM25 weight in the fused retrieval score.
    bm25_weight: float = BM25_WEIGHT
    # Vector weight in the fused retrieval score.
    vector_weight: float = VECTOR_WEIGHT
    # Model used by the memory subsystem; defaults to the agent's own model.
    submodel: Model = None
    # Embedding model used by the memory subsystem; defaults to OllamaEmbedding().
    embedding_model: Embedding = None

    # === Compress subsystem (consumed by _setup_compress) ===
    # System prompt for the context-compression step.
    compress_prompt: str = COMPRESS_PROMPT
    # Prefix prepended to compressed turns in the session.
    compress_prefix: str = COMPRESS_PREFIX
    # Number of recent turns kept verbatim and never compressed.
    keep_recent_turns: int = KEEP_RECENT_TURNS
    # Token-ratio threshold (0..1) at which compression is triggered.
    compression_threshold: float = COMPRESSION_THRESHOLD

    # === Shared by both memory and compress ===
    # Memory merge ratio; also used by compress to size the target token count.
    merge_ratio: float = MERGE_RATIO
    # Token cap for "small" turns; used by both extraction and compression heuristics.
    small_turn_cap: int = SMALL_TURN_CAP


def _setup_memory(agent: Agent, config: BuiltinHookConfig | dict = None) -> None:
    """Register the memory subsystem: 4 hooks + add_memory tool + system_prompt extension.

    Soft-depends on _setup_compress: the extract_memories_before_compress hook
    reads ctx['compression_needed'], which is only set when the compress builder
    is also installed. With no compress builder, that hook is a no-op.
    """
    if config is None:
        config = BuiltinHookConfig()
    elif isinstance(config, dict):
        config = BuiltinHookConfig(**config)

    submodel = config.submodel or agent.model
    embedding_model = config.embedding_model or OllamaEmbedding()

    memory_manager = MemoryManager(
        name="memories",
        memory_dir=agent.base_dir / 'memory',
        logger=agent.logger,
        embedding=embedding_model,
    )
    memory_runtime = MemoryRuntime(logger=agent.logger)

    add_tool = create_add_memory_tool(
        memory_manager,
        lambda: agent.session.id,
        prompt=config.add_memory_tool_prompt,
        runtime=memory_runtime,
    )
    agent.add_tools([add_tool])

    (extract_memory_before_compress,
     extract_memory_before_new_session,
     clean_memory_hook,
     inject_memory_hook) = create_memory_hook(
        memory_manager, submodel,
        runtime=memory_runtime,
        extract_prompt=config.extract_prompt,
        clean_prompt=config.clean_prompt,
        subagent_add_memory_tool_prompt=config.extract_subagent_add_memory_tool_prompt,
        extract_user_prompt=config.extract_user_prompt,
        clean_user_prompt=config.clean_user_prompt,
        merge_ratio=config.merge_ratio,
        small_turn_cap=config.small_turn_cap,
        max_inject=config.max_inject,
        inject_rrf_k=config.rrf_k,
        inject_bm25_weight=config.bm25_weight,
        inject_vector_weight=config.vector_weight,
        max_candidates=config.max_candidates,
        clean_mutation_threshold=config.clean_mutation_threshold,
    )

    hook = agent.hook
    hook.register(func=inject_memory_hook, hook_type=HookType.AFTER_INPUT, priority=99)
    hook.register(func=extract_memory_before_compress, hook_type=HookType.BEFORE_STREAM, priority=101)
    hook.register(func=extract_memory_before_new_session, hook_type=HookType.NEW_SESSION, priority=100)
    hook.register(func=clean_memory_hook, hook_type=HookType.NEW_SESSION, priority=101)

    prompt = config.memory_system_prompt.format(
        memory_dir=memory_manager.memory_dir,
        add_tool_name=add_tool.name,
    )
    agent.change_system_prompt(agent.system_prompt + prompt)


def _setup_compress(agent: Agent, config: BuiltinHookConfig | dict = None) -> None:
    """Register the context-compression subsystem: 2 hooks.

    Side effect: sets ctx['compression_needed'] before each stream so that
    the memory builder's extract_memories_before_compress hook can react.
    """
    if config is None:
        config = BuiltinHookConfig()
    elif isinstance(config, dict):
        config = BuiltinHookConfig(**config)

    check_compress, do_compress = create_ctx_compress_hook(
        config.compression_threshold,
        config.merge_ratio,
        config.small_turn_cap,
        config.keep_recent_turns,
        compress_prompt=config.compress_prompt,
        compress_prefix=config.compress_prefix,
    )

    hook = agent.hook
    hook.register(func=check_compress, hook_type=HookType.BEFORE_STREAM, priority=100)
    hook.register(func=do_compress, hook_type=HookType.BEFORE_STREAM, priority=102)


HOOK_CREATOR = {
    "built_in.memory": _setup_memory,
    "built_in.compress": _setup_compress,
}


__all__ = [
    "_setup_memory",
    "_setup_compress",
    "HOOK_CREATOR",
    "compress_session",
    "extract_memories",
    "MEMORY_SYSTEM_PROMPT",
    "BuiltinHookConfig",
    "MemoryRuntime",
]
