from typing import List

from ...core.tool import Tool
from ...core.message import HumanMessage
from ...core.agent import SubAgent
from ...core.logger import AgentLogger
from ...core.model import Model
from .memory import Memory, MemoryManager


ADD_MEMORY_TOOL_DESCRIPTION = (
    "Save one or more memories to the agent's long-term memory in batch. "
    "Use this tool when the user explicitly asks you to remember something, "
    "or when you discover important information about the user that will be "
    "useful in future conversations. You can add multiple memories at once.\n\n"
    "Parameters:\n"
    "- memories (List[str]): A list of memory content strings to save. Each content "
    "should be self-contained and understandable without additional context.\n\n"
    "Examples of when to use this tool:\n"
    '- User says "remember that I prefer dark mode" → ["User prefers dark mode"]\n'
    '- User says "my name is Alice, I work at Google" → ["User name is Alice", "User works at Google"]\n'
    '- User says "I fixed that bug by restarting the service" → ["User fixed a bug by restarting the service"]\n'
    '- Multiple discoveries → combine into one call with a list of strings'
)

def create_add_memory_tool(memory_manager: MemoryManager, session_id_getter, prompt: str = ADD_MEMORY_TOOL_DESCRIPTION) -> Tool:

    async def add_memory(memories: List[str]) -> str:
        valid_memories = []
        for content in memories:
            memory = Memory.create(
                content=content,
                session_id=session_id_getter(),
            )
            valid_memories.append(memory)

        if valid_memories:
            await memory_manager.add_memories(valid_memories)
            saved_list = "\n".join(f"  - {m.content}" for m in valid_memories)
            return f"Saved {len(valid_memories)} memories:\n{saved_list}"

        return "No memories provided."

    return Tool(add_memory, 
                name="add_memory", 
                description=prompt if prompt else ADD_MEMORY_TOOL_DESCRIPTION)


DELETE_MEMORY_TOOL_DESCRIPTION = (
    "Delete one or more memories from the agent's long-term memory by their IDs. "
    "Use this tool to remove obsolete, conflicting, or low-quality memories "
    "during memory cleanup and maintenance.\n\n"
    "Parameters:\n"
    "- memory_ids (List[str]): A list of memory IDs to delete. Each ID is a "
    "unique hash string identifying a specific memory.\n\n"
    "Examples:\n"
    '- Delete a single stale memory: memory_ids=["a1b2c3d4..."]\n'
    '- Delete multiple conflicting memories at once: memory_ids=["a1b2c3d4...", "e5f6g7h8..."]'
)

def create_delete_memory_tool(memory_manager: MemoryManager) -> Tool:

    async def delete_memory(memory_ids: List[str]) -> str:
        if not memory_ids:
            return "No memory IDs provided."

        deleted = []
        not_found = []

        for mid in memory_ids:
            data = memory_manager.collection.get(ids=[mid], include=["documents"])
            if data.get("ids"):
                content = data["documents"][0] if data.get("documents") else "(unknown)"
                memory_manager.delete_memory(mid)
                deleted.append(f"  - [{mid[:12]}...] {content}")
            else:
                not_found.append(f"  - [{mid[:12]}...]")

        result_parts = []
        if deleted:
            result_parts.append(f"Deleted {len(deleted)} memories:\n" + "\n".join(deleted))
        if not_found:
            result_parts.append(f"Not found ({len(not_found)} IDs):\n" + "\n".join(not_found))

        return "\n\n".join(result_parts) if result_parts else "No memories deleted."

    return Tool(delete_memory,
                name="delete_memory",
                description=DELETE_MEMORY_TOOL_DESCRIPTION)


INJECT_MEMORIES_TOOL_DESCRIPTION = (
    "Select the most relevant memory IDs for answering the user's query. "
    "Call this tool with a list of up to {max_inject} memory IDs that are most relevant "
    "to the user's question. If no candidate memory is relevant, call with an "
    "empty list (memory_ids=[]).\n\n"
    "Parameters:\n"
    "- memory_ids (List[str]): A list of memory IDs to select. Maximum {max_inject} IDs. "
    "Use an empty list when nothing is relevant.\n\n"
    "Your mission is complete once you call this tool. Do not produce any further response."
)

INJECT_MEMORIES_SUBAGENT_PROMPT = """You are a memory selector. Your ONLY job is to read the user's query and the candidate memories, then call the `inject_memories` tool with the IDs of the most relevant memories (up to {max_inject}).

## Critical Rules
- Your entire purpose is to produce the input for the `inject_memories` tool call.
- You MUST always call `inject_memories`, even if nothing is relevant — in that case call it with an empty list (memory_ids=[]).
- Once you call `inject_memories`, your mission is complete. Do NOT produce any further response.
- Select only memories that are genuinely helpful for answering the user's query.
- At most {max_inject} IDs. Less is fine if fewer are relevant."""


def create_inject_memories_tool(max_inject: int = 5):
    captured_ids: List[str] = []

    async def inject_memories(memory_ids: List[str]) -> str:
        captured_ids.clear()
        if memory_ids:
            captured_ids.extend(memory_ids[:max_inject])
        return "Mission complete."

    tool = Tool(
        inject_memories,
        name="inject_memories",
        description=INJECT_MEMORIES_TOOL_DESCRIPTION.format(max_inject=max_inject),
    )
    return tool, captured_ids


async def inject_memory_context(
    query: str,
    memory_manager: MemoryManager,
    submodel: Model,
    max_inject: int = 5,
    rrf_k: int = 60,
    bm25_weight: float = 0.5,
    vector_weight: float = 0.5,
    max_candidates: int = 50,
    logger: AgentLogger = None,
) -> str:
    if memory_manager.count == 0:
        if logger:
            logger.debug("Memory store is empty, skipping injection")
        return None

    if memory_manager.count <= max_candidates:
        candidates = memory_manager.get_all()
        if logger:
            logger.debug(
                "Using all %d memories as candidates (small store)",
                memory_manager.count,
                context={"total_count": memory_manager.count},
            )
    else:
        hybrid_result = await memory_manager.hybrid_search(
            query=query,
            n_results=max_candidates,
            rrf_k=rrf_k,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
        )
        if not hybrid_result.get("ids"):
            if logger:
                logger.debug(
                    "Hybrid search returned no candidates for query: %.50s",
                    query,
                    context={"query_preview": query[:50]},
                )
            return None
        candidates = [
            {"id": hybrid_result["ids"][i], "content": hybrid_result["documents"][i]}
            for i in range(len(hybrid_result["ids"]))
        ]
        if logger:
            logger.info(
                "Hybrid search returned %d candidates for query: %.50s",
                len(candidates), query,
                context={"candidate_count": len(candidates), "query_preview": query[:50]},
            )

    if not candidates:
        return None

    candidates_text = "\n\n".join(
        f"[ID: {c['id']}]\n{c['content']}" for c in candidates
    )

    select_tool, captured_ids = create_inject_memories_tool(max_inject=max_inject)

    sub_agent = SubAgent(
        model=submodel,
        system_prompt=INJECT_MEMORIES_SUBAGENT_PROMPT.format(max_inject=max_inject),
        tools=[select_tool],
        logger=logger,
        name="MemoryInjector",
    )

    prompt = f"User query: {query}\n\nCandidate memories:\n{candidates_text}"
    try:
        await sub_agent.run(HumanMessage(content=prompt))
    except Exception:
        if logger:
            logger.warning("Memory injection subagent failed, skipping memory injection")
        return None

    valid_ids = captured_ids.copy()
    captured_ids.clear()

    if not valid_ids:
        if logger:
            logger.debug(
                "Memory selector chose 0/%d memories",
                len(candidates),
                context={"candidate_count": len(candidates), "selected_count": 0},
            )
        return None

    if logger:
        logger.info(
            "Memory selector chose %d/%d memories",
            len(valid_ids), len(candidates),
            context={"selected_count": len(valid_ids), "candidate_count": len(candidates)},
        )

    candidate_map = {c["id"]: c["content"] for c in candidates}
    valid_contents = []
    for mid in valid_ids:
        if mid in candidate_map:
            valid_contents.append(candidate_map[mid])
            memory_manager.increment_access(mid)

    if not valid_contents:
        return None

    return "\n".join(f"- {c}" for c in valid_contents)
