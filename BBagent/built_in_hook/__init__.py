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

# compression hook config
KEEP_RECENT_MSG = 20
KEEP_RECENT_TIME = 60 * 60
COMPRESSION_THRESHOLD = 0.8

# memory hook config
N_RESULTS = 5
RRF_K = 60
BM25_WEIGHT = 0.5
VECTOR_WEIGHT = 0.5

def setup_agent_hook(agent: Agent,
                     max_context_tokens: int,
                     submodel: Model = None,
                     embedding_model: Embedding = None,
                     ):
    if submodel is None:
        submodel = agent.model
    if embedding_model is None:
        embedding_model = OllamaEmbedding()

    name = agent.name + '_memory'
    memory_dir = agent.base_dir / 'memory'
    logger = agent.logger
    memory_manager = MemoryManager(name=name, memory_dir=memory_dir, logger=logger)

    add_memory_tool = create_add_memory_tool(memory_manager, lambda: agent.session.id)
    search_memory_tool = create_search_memory_tool(memory_manager,
                                                   submodel,
                                                   lambda: agent.base_dir,
                                                   N_RESULTS,
                                                   RRF_K,
                                                   BM25_WEIGHT,
                                                   VECTOR_WEIGHT)
    agent.add_tools([add_memory_tool, search_memory_tool])

    check_compression_needed, execute_compression = create_ctx_compress_hook(submodel,
                                                                             max_context_tokens,
                                                                             KEEP_RECENT_MSG,
                                                                             KEEP_RECENT_TIME,
                                                                             COMPRESSION_THRESHOLD)
    memory_extract_hook, clean_memory_hook = create_memory_hook(memory_manager, submodel)

    async def memory_extract_after_compress(ctx: HookContext):
        if ctx.get('compression_needed'):
            await memory_extract_hook(ctx)
            return

    hook = agent.hook
    hook.register(func=check_compression_needed,
                  hook_type=HookType.BEFORE_STREAM,
                  priority=100,
                  )
    hook.register(func=memory_extract_after_compress,
                  hook_type=HookType.BEFORE_STREAM,
                  priority=101,
                  )
    hook.register(func=execute_compression,
                  hook_type=HookType.BEFORE_STREAM,
                  priority=102,
                  )
    hook.register(func=memory_extract_hook,
                  hook_type=HookType.NEW_SESSION,
                  priority=100,
                  )
    hook.register(func=clean_memory_hook,
                  hook_type=HookType.NEW_SESSION,
                  priority=101,
                  )
    return 


__all__ = [
    "setup_agent_hook",
    "compress_session",
    "extract_memories",
]
