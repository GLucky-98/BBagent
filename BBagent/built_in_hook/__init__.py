from .memory import (
    MemoryManager,
    Embedding,
    OllamaEmbedding,
    create_add_memory_tool,
    create_search_memory_tool,
    create_memory_hook,
    extract_memories)
from .ctx_compress_hook import create_ctx_compress_hook, compress_session

from ..core import Agent, Model, HookContext, HookType

KEEP_RECENT_MSG = 20
KEEP_RECENT_TIME = 60 * 60
COMPRESSION_THRESHOLD = 0.8

N_RESULTS = 5
RRF_K = 60
BM25_WEIGHT = 0.5
VECTOR_WEIGHT = 0.5

DEFAULT_MEMORY_SYSTEM_PROMPT = """
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


def setup_agent_hook(agent: Agent,
                     memory_system_prompt: str = None,
                     add_memory_tool_prompt: str = None,
                     search_memory_tool_prompt: str = None,
                     search_memory_subagent_prompt: str = None,
                     extract_prompt: str = None,
                     clean_prompt: str = None,
                     extract_subagent_add_memory_tool_prompt: str = None,
                     extract_user_prompt: str = None,
                     clean_user_prompt: str = None,
                     compress_prompt: str = None,
                     compress_prefix: str = None,
                     auto_search: bool = True,
                     search_prompt: str = None,
                     search_user_prompt: str = None,
                     submodel: Model = None,
                     embedding_model: Embedding = None,
                     ):
    submodel = submodel or agent.model
    embedding_model = embedding_model or OllamaEmbedding()

    memory_manager = MemoryManager(
        name=agent.name + '_memory',
        memory_dir=agent.base_dir / 'memory',
        logger=agent.logger,
        embedding=embedding_model,
    )

    add_tool = create_add_memory_tool(
        memory_manager,
        lambda: agent.session.id,
        prompt=add_memory_tool_prompt,
    )
    agent.add_tools([add_tool])

    search_tool = create_search_memory_tool(
        memory_manager,
        submodel,
        lambda: agent.base_dir,
        N_RESULTS, RRF_K, BM25_WEIGHT, VECTOR_WEIGHT,
        subagent_prompt=search_memory_subagent_prompt,
        tool_prompt=search_memory_tool_prompt,
        logger=agent.logger,
    )

    check_compress, do_compress = create_ctx_compress_hook(
        KEEP_RECENT_MSG, KEEP_RECENT_TIME, COMPRESSION_THRESHOLD,
        compress_prompt=compress_prompt,
        compress_user_prefix=compress_prefix,
    )

    extract_memory_hook, clean_memory_hook, search_memory_hook = create_memory_hook(
        memory_manager, submodel,
        extract_prompt=extract_prompt,
        clean_prompt=clean_prompt,
        subagent_add_memory_tool_prompt=extract_subagent_add_memory_tool_prompt,
        extract_user_prompt=extract_user_prompt,
        clean_user_prompt=clean_user_prompt,
        search_prompt=search_prompt,
        search_user_prompt=search_user_prompt,
        search_n_results=N_RESULTS,
        search_rrf_k=RRF_K,
        search_bm25_weight=BM25_WEIGHT,
        search_vector_weight=VECTOR_WEIGHT,
    )

    async def extract_memory_before_compress(ctx: HookContext):
        if ctx.get('compression_needed'):
            await extract_memory_hook(ctx)

    hook = agent.hook
    hook.register(func=search_memory_hook, hook_type=HookType.BEFORE_STREAM, priority=99)
    hook.register(func=check_compress, hook_type=HookType.BEFORE_STREAM, priority=100)
    hook.register(func=extract_memory_before_compress, hook_type=HookType.BEFORE_STREAM, priority=101)
    hook.register(func=do_compress, hook_type=HookType.BEFORE_STREAM, priority=102)
    hook.register(func=extract_memory_hook, hook_type=HookType.NEW_SESSION, priority=100)
    hook.register(func=clean_memory_hook, hook_type=HookType.NEW_SESSION, priority=101)

    prompt = memory_system_prompt or DEFAULT_MEMORY_SYSTEM_PROMPT
    prompt = prompt.format(
        memory_dir=memory_manager.memory_dir,
        add_tool_name=add_tool.name,
    )
    agent.change_system_prompt(agent.system_prompt + prompt)


__all__ = [
    "setup_agent_hook",
    "compress_session",
    "extract_memories",
    "DEFAULT_MEMORY_SYSTEM_PROMPT",
]
