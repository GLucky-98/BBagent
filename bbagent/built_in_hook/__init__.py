from dataclasses import dataclass

from ..core import Agent, HookContext, HookType, Model
from .ctx_compress_hook import COMPRESS_PREFIX, COMPRESS_PROMPT, compress_session, create_ctx_compress_hook
from .memory import (
    ADD_MEMORY_TOOL_DESCRIPTION,
    ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT,
    CLEAN_SYSTEM_PROMPT,
    CLEAN_USER_PROMPT,
    EXTRACT_SYSTEM_PROMPT,
    EXTRACT_USER_PROMPT,
    Embedding,
    MemoryManager,
    MemoryRuntime,
    OllamaEmbedding,
    create_add_memory_tool,
    create_memory_hook,
    extract_memories,
)
from .todo import (
    TodoManager,
    TodoRuntime,
    create_todo_hook,
    create_todo_tools,
)

KEEP_RECENT_TURNS = 3
COMPRESSION_THRESHOLD = 0.8
MERGE_RATIO = 0.2
RRF_K = 60
BM25_WEIGHT = 0.5
VECTOR_WEIGHT = 0.5
TODO_STREAM_INJECT_INTERVAL = 3

MAX_INJECT = 5
MAX_CANDIDATES = 50
EXTRACT_TURN_INTERVAL = 5
INJECT_OVERSAMPLE_FACTOR = 3
INJECT_OVERSAMPLE_CAP = 200

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

TODO_SYSTEM_PROMPT = """
## Runtime Todo System

You have access to a runtime todo system for tracking the current multi-step task.

### Available Todo Tools
- `todo_create`: create a complete todo list before substantial multi-step work.
- `todo_update`: update an item when work starts, completes, is cancelled, or dependencies change.
- `todo_list`: inspect the current todo list.
- `todo_clear`: clear the current todo list.

### Best Practices
- Use todos for complex tasks that benefit from explicit progress tracking.
- Keep item ids short, stable, and unique within the list.
- `blocked_by` means dependencies between todo items, not external user or system blockers.
- `ready` is not a status. The system derives readiness from pending items whose dependencies are terminal.
- Todo is a short-lived runtime workspace, not long-term memory or session state.
- When every item is done or cancelled, the todo list is automatically cleared.
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
    # Complete unextracted turns needed before background interval extraction.
    extract_turn_interval: int = EXTRACT_TURN_INTERVAL
    # RRF k used to fuse BM25 and vector retrieval scores.
    rrf_k: int = RRF_K
    # BM25 weight in the fused retrieval score.
    bm25_weight: float = BM25_WEIGHT
    # Vector weight in the fused retrieval score.
    vector_weight: float = VECTOR_WEIGHT
    # Search wider than max_candidates before filtering memories already seen in a session.
    inject_oversample_factor: int = INJECT_OVERSAMPLE_FACTOR
    # Hard cap for the oversampled retrieval size.
    inject_oversample_cap: int = INJECT_OVERSAMPLE_CAP
    # Model used by the memory subsystem; defaults to the agent's own model.
    submodel: Model = None
    # Embedding model used by the memory subsystem; defaults to OllamaEmbedding().
    embedding_model: Embedding = None

    # === Todo subsystem (consumed by _setup_todo) ===
    # System prompt appended to agent.system_prompt after todo setup.
    todo_system_prompt: str = TODO_SYSTEM_PROMPT
    # Minimum stream iterations before reinjecting unchanged todo context.
    todo_stream_inject_interval: int = TODO_STREAM_INJECT_INTERVAL

    # === Compress subsystem (consumed by _setup_compress) ===
    # System prompt for the context-compression step.
    compress_prompt: str = COMPRESS_PROMPT
    # Prefix prepended to compressed turns in the session.
    compress_prefix: str = COMPRESS_PREFIX
    # Number of recent turns kept verbatim and never compressed.
    keep_recent_turns: int = KEEP_RECENT_TURNS
    # Token-ratio threshold (0..1) at which compression is triggered.
    compression_threshold: float = COMPRESSION_THRESHOLD

    # Shared by both memory and compress
    # Memory merge ratio; also used by compress to size the target token count.
    merge_ratio: float = MERGE_RATIO


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

    def mark_current_turn_memory_extracted() -> None:
        if agent.session is not None and agent.session.turns:
            agent.session.turns[-1].memory_extracted = True

    add_tool = create_add_memory_tool(
        memory_manager,
        lambda: agent.session.id,
        prompt=config.add_memory_tool_prompt,
        runtime=memory_runtime,
        mark_current_turn_extracted=mark_current_turn_memory_extracted,
    )
    agent.add_tools([add_tool])

    (extract_memory_before_compress,
     extract_memory_before_new_session,
     clean_memory_hook,
     inject_memory_hook,
     extract_memory_after_interval) = create_memory_hook(
        memory_manager, submodel,
        runtime=memory_runtime,
        extract_prompt=config.extract_prompt,
        clean_prompt=config.clean_prompt,
        subagent_add_memory_tool_prompt=config.extract_subagent_add_memory_tool_prompt,
        extract_user_prompt=config.extract_user_prompt,
        clean_user_prompt=config.clean_user_prompt,
        merge_ratio=config.merge_ratio,
        max_inject=config.max_inject,
        inject_rrf_k=config.rrf_k,
        inject_bm25_weight=config.bm25_weight,
        inject_vector_weight=config.vector_weight,
        max_candidates=config.max_candidates,
        extract_turn_interval=config.extract_turn_interval,
        inject_oversample_factor=config.inject_oversample_factor,
        inject_oversample_cap=config.inject_oversample_cap,
        clean_mutation_threshold=config.clean_mutation_threshold,
    )

    hook = agent.hook
    hook.register(func=inject_memory_hook, hook_type=HookType.AFTER_INPUT, priority=99)
    hook.register(func=extract_memory_before_compress, hook_type=HookType.BEFORE_STREAM, priority=101)
    hook.register(func=extract_memory_before_new_session, hook_type=HookType.NEW_SESSION, priority=100)
    hook.register(func=clean_memory_hook, hook_type=HookType.NEW_SESSION, priority=101)
    hook.register(func=extract_memory_after_interval, hook_type=HookType.AFTER_RUN, priority=100)

    prompt = config.memory_system_prompt.format(
        memory_dir=memory_manager.memory_dir,
        add_tool_name=add_tool.name,
    )
    agent.set_runtime_prompt("built_in.memory", prompt, order=100)


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
        config.keep_recent_turns,
        compress_prompt=config.compress_prompt,
        compress_prefix=config.compress_prefix,
    )

    hook = agent.hook
    hook.register(func=check_compress, hook_type=HookType.BEFORE_STREAM, priority=100)
    hook.register(func=do_compress, hook_type=HookType.BEFORE_STREAM, priority=102)


def _setup_todo(agent: Agent, config: BuiltinHookConfig | dict = None) -> None:
    """Register the runtime todo subsystem: tools + context/display/session hooks."""
    if config is None:
        config = BuiltinHookConfig()
    elif isinstance(config, dict):
        config = BuiltinHookConfig(**config)

    manager = TodoManager()
    runtime = TodoRuntime()
    agent.add_tools(create_todo_tools(manager, runtime))

    (
        remind_before_stream,
        emit_on_tool_result,
        clear_on_new_session,
        cleanup_after_run,
    ) = create_todo_hook(
        manager,
        runtime,
        stream_inject_interval=config.todo_stream_inject_interval,
    )

    hook = agent.hook
    hook.register(func=remind_before_stream, hook_type=HookType.BEFORE_STREAM, priority=110)
    hook.register(func=emit_on_tool_result, hook_type=HookType.ON_TOOL_RESULT, priority=100)
    hook.register(func=clear_on_new_session, hook_type=HookType.NEW_SESSION, priority=90)
    hook.register(func=cleanup_after_run, hook_type=HookType.AFTER_RUN, priority=110)

    agent.set_runtime_prompt("built_in.todo", config.todo_system_prompt, order=110)


HOOK_CREATOR = {
    "built_in.memory": _setup_memory,
    "built_in.compress": _setup_compress,
    "built_in.todo": _setup_todo,
}


__all__ = [
    "HOOK_CREATOR",
    "MEMORY_SYSTEM_PROMPT",
    "TODO_SYSTEM_PROMPT",
    "BuiltinHookConfig",
    "MemoryRuntime",
    "TodoRuntime",
    "_setup_compress",
    "_setup_memory",
    "_setup_todo",
    "compress_session",
    "extract_memories",
]
