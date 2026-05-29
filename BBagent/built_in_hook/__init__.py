from .memory import (
    MemoryManager,
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

from dataclasses import dataclass, asdict

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
class MemoryCompressConfig:
    """Configuration for memory and context compression hooks."""

    memory_system_prompt: str = MEMORY_SYSTEM_PROMPT
    add_memory_tool_prompt: str = ADD_MEMORY_TOOL_DESCRIPTION
    compress_prompt: str = COMPRESS_PROMPT
    compress_prefix: str = COMPRESS_PREFIX
    keep_recent_turns: int = KEEP_RECENT_TURNS
    compression_threshold: float = COMPRESSION_THRESHOLD
    small_turn_cap: int = SMALL_TURN_CAP
    merge_ratio: float = MERGE_RATIO
    max_inject: int = MAX_INJECT
    max_candidates: int = MAX_CANDIDATES
    rrf_k: int = RRF_K
    bm25_weight: float = BM25_WEIGHT
    vector_weight: float = VECTOR_WEIGHT
    extract_prompt: str = EXTRACT_SYSTEM_PROMPT
    extract_subagent_add_memory_tool_prompt: str = ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT
    extract_user_prompt: str = EXTRACT_USER_PROMPT
    clean_prompt: str = CLEAN_SYSTEM_PROMPT
    clean_user_prompt: str = CLEAN_USER_PROMPT
    clean_mutation_threshold: int = 50
    submodel: Model = None
    embedding_model: Embedding = None


def setup_agent_hook(agent: Agent, config: MemoryCompressConfig = None):
    return create_memory_compress_hook(agent, config)


def create_memory_compress_hook(agent: Agent, config: MemoryCompressConfig | dict = None):
    if config is None:
        config = MemoryCompressConfig()
    elif isinstance(config, dict):
        config = MemoryCompressConfig(**config)

    agent.hook.bind("built_in.memory_compress", asdict(config))
    agent.hook_config = config

    submodel = config.submodel or agent.model
    embedding_model = config.embedding_model or OllamaEmbedding()

    memory_manager = MemoryManager(
        name=agent.name + '_memory',
        memory_dir=agent.base_dir / 'memory',
        logger=agent.logger,
        embedding=embedding_model,
    )

    add_tool = create_add_memory_tool(
        memory_manager,
        lambda: agent.session.id,
        prompt=config.add_memory_tool_prompt,
    )
    add_tool.mark_hook_managed()
    agent.add_tools([add_tool])

    check_compress, do_compress = create_ctx_compress_hook(
        config.compression_threshold,
        config.merge_ratio,
        config.small_turn_cap,
        config.keep_recent_turns,
        compress_prompt=config.compress_prompt,
        compress_prefix=config.compress_prefix,
    )

    (extract_memory_before_compress,
     extract_memory_before_new_session,
     clean_memory_hook,
     inject_memory_hook) = create_memory_hook(
        memory_manager, submodel,
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
    hook.register(func=check_compress, hook_type=HookType.BEFORE_STREAM, priority=100)
    hook.register(func=extract_memory_before_compress, hook_type=HookType.BEFORE_STREAM, priority=101)
    hook.register(func=do_compress, hook_type=HookType.BEFORE_STREAM, priority=102)
    hook.register(func=extract_memory_before_new_session, hook_type=HookType.NEW_SESSION, priority=100)
    hook.register(func=clean_memory_hook, hook_type=HookType.NEW_SESSION, priority=101)

    prompt = config.memory_system_prompt
    prompt = prompt.format(
        memory_dir=memory_manager.memory_dir,
        add_tool_name=add_tool.name,
    )
    agent.change_system_prompt(agent.system_prompt + prompt)


HOOK_CREATOR = {
    "built_in.memory_compress": create_memory_compress_hook,
}


__all__ = [
    "create_memory_compress_hook",
    "setup_agent_hook",
    "HOOK_CREATOR",
    "compress_session",
    "extract_memories",
    "MEMORY_SYSTEM_PROMPT",
    "MemoryCompressConfig",
]
