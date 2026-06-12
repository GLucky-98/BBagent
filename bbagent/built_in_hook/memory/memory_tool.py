from collections.abc import Callable
from typing import TYPE_CHECKING

from ...core.agent import SubAgent
from ...core.logger import AgentLogger
from ...core.message import HumanMessage
from ...core.model import Model
from ...core.tool import Tool
from .fingerprint import format_memory_for_injection, memory_fingerprint
from .memory import Memory, MemoryManager

if TYPE_CHECKING:
    from .runtime import MemoryRuntime


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

def create_add_memory_tool(
    memory_manager: MemoryManager,
    session_id_getter,
    prompt: str = ADD_MEMORY_TOOL_DESCRIPTION,
    runtime: "MemoryRuntime" = None,
    mark_current_turn_extracted: Callable[[], None] | None = None,
) -> Tool:

    async def add_memory(memories: list[str]) -> str:
        valid_memories = []
        for content in memories:
            memory = Memory.create(
                content=content,
                session_id=session_id_getter(),
            )
            valid_memories.append(memory)

        if valid_memories:
            if runtime is not None:
                async with runtime.store_lock:
                    result = await memory_manager.add_memories(valid_memories)
            else:
                result = await memory_manager.add_memories(valid_memories)
            result = result or {}
            added_count = int(result.get("added_count", 0))
            skipped_count = int(result.get("skipped_duplicates", 0))
            if mark_current_turn_extracted is not None and (added_count > 0 or skipped_count > 0):
                mark_current_turn_extracted()
            saved_list = "\n".join(f"  - {m.content}" for m in valid_memories)
            return f"Saved {len(valid_memories)} memories:\n{saved_list}"

        return "No memories provided."

    return Tool(add_memory,
                name="add_memory",
                description=prompt if prompt else ADD_MEMORY_TOOL_DESCRIPTION,
                source="hook")


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

def create_delete_memory_tool(memory_manager: MemoryManager, runtime: "MemoryRuntime" = None) -> Tool:

    async def delete_memory(memory_ids: list[str]) -> str:
        if not memory_ids:
            return "No memory IDs provided."

        deleted = []
        not_found = []

        async def _delete():
            for mid in memory_ids:
                data = memory_manager.collection.get(ids=[mid], include=["documents"])
                if data.get("ids"):
                    content = data["documents"][0] if data.get("documents") else "(unknown)"
                    memory_manager.delete_memory(mid)
                    deleted.append(f"  - [{mid[:12]}...] {content}")
                else:
                    not_found.append(f"  - [{mid[:12]}...]")

        if runtime is not None:
            async with runtime.store_lock:
                await _delete()
        else:
            await _delete()

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
    "- memory_ids (List[str]): A list of memory ID strings to select. Maximum {max_inject} IDs. "
    "Each ID must be wrapped in quotes as a string (e.g., ['1', '5'] not [1, 5]). "
    "Use an empty list when nothing is relevant.\n\n"
    "Your mission is complete once you call this tool. Do not produce any further response."
)

INJECT_MEMORIES_SUBAGENT_PROMPT = """You are a memory selector. Your ONLY job is to read the user's query and the candidate memories, then call the `inject_memories` tool with the IDs of the most relevant memories (up to {max_inject}).

## Critical Rules
- Your entire purpose is to produce the input for the `inject_memories` tool call.
- You MUST always call `inject_memories`, even if nothing is relevant — in that case call it with an empty list (memory_ids=[]).
- Once you call `inject_memories`, your mission is complete. Do NOT produce any further response.
- Select only memories that are genuinely helpful for answering the user's query.
- At most {max_inject} IDs. Less is fine if fewer are relevant.
- IDs are strings: pass them quoted like ['1', '5'], never as bare numbers like [1, 5]."""


def create_inject_memories_tool(max_inject: int = 5, sub_agent=None):
    captured_ids: list[str] = []

    async def inject_memories(memory_ids: list) -> str:
        memory_ids = [str(mid) for mid in memory_ids]
        captured_ids.clear()
        if memory_ids:
            captured_ids.extend(memory_ids[:max_inject])
        if sub_agent is not None:
            sub_agent.stop()
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
    seen_memory_keys: set[bytes] | None = None,
    selected_memory_keys: list[bytes] | None = None,
    oversample_factor: int = 3,
    oversample_cap: int = 200,
    logger: AgentLogger = None,
    runtime: "MemoryRuntime" = None,
) -> str:
    seen_memory_keys = seen_memory_keys or set()
    candidate_fetch = max_candidates
    if seen_memory_keys:
        candidate_fetch = min(max_candidates * max(1, oversample_factor), oversample_cap)

    async def _collect_candidates() -> list[dict] | None:
        count = memory_manager.count
        if count == 0:
            if logger:
                logger.debug("Memory store is empty, skipping injection")
            return None

        if count <= candidate_fetch:
            all_candidates = memory_manager.get_all()
            if logger:
                logger.debug(
                    f"Using all {count} memories as candidates (small store)",
                    context={"total_count": count},
                )
            return all_candidates

        hybrid_result = await memory_manager.hybrid_search(
            query=query,
            n_results=candidate_fetch,
            rrf_k=rrf_k,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
        )
        if not hybrid_result.get("ids"):
            if logger:
                logger.debug(
                    f"Hybrid search returned no candidates for query: {query[:50]}",
                    context={"query_preview": query[:50]},
                )
            return None
        hybrid_candidates = [
            {"id": hybrid_result["ids"][i], "content": hybrid_result["documents"][i]}
            for i in range(len(hybrid_result["ids"]))
        ]
        if logger:
            logger.info(
                f"Hybrid search returned {len(hybrid_candidates)} candidates for query: {query[:50]}",
                context={"candidate_count": len(hybrid_candidates), "query_preview": query[:50]},
            )
        return hybrid_candidates

    if runtime is not None:
        async with runtime.store_lock:
            candidates = await _collect_candidates()
    else:
        candidates = await _collect_candidates()

    if not candidates:
        return None

    id_to_key = {}
    filtered_candidates = []
    for candidate in candidates:
        key = memory_fingerprint(candidate["content"])
        if key in seen_memory_keys:
            continue
        id_to_key[candidate["id"]] = key
        filtered_candidates.append(candidate)

    candidates = filtered_candidates[:max_candidates]

    if not candidates:
        if logger:
            logger.debug(
                "Memory injection skipped (all candidates already seen in session)",
                context={"seen_count": len(seen_memory_keys)},
            )
        return None

    candidates_text = "\n\n".join(
        f"[ID: {c['id']}]\n{c['content']}" for c in candidates
    )

    sub_agent = SubAgent(
        model=submodel,
        system_prompt=INJECT_MEMORIES_SUBAGENT_PROMPT.format(max_inject=max_inject),
        tools=[],
        logger=logger,
        name="MemoryInjector",
    )

    select_tool, captured_ids = create_inject_memories_tool(
        max_inject=max_inject, sub_agent=sub_agent
    )
    sub_agent.add_tools([select_tool])

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
                f"Memory selector chose 0/{len(candidates)} memories",
                context={"candidate_count": len(candidates), "selected_count": 0},
            )
        return None

    if logger:
        logger.info(
            f"Memory selector chose {len(valid_ids)}/{len(candidates)} memories",
            context={"selected_count": len(valid_ids), "candidate_count": len(candidates)},
        )

    def _resolve_selected() -> list[tuple[str, str]]:
        current = memory_manager.get_by_ids(valid_ids)
        current_map = {c["id"]: c["content"] for c in current}
        selected = []
        for mid in valid_ids:
            if mid in current_map:
                selected.append((mid, current_map[mid]))
                memory_manager.increment_access(mid)
        return selected

    if runtime is not None:
        async with runtime.store_lock:
            selected = _resolve_selected()
    else:
        selected = _resolve_selected()

    if not selected:
        return None

    selected_keys = [id_to_key[mid] for mid, _ in selected if mid in id_to_key]
    if selected_memory_keys is not None:
        selected_memory_keys.extend(selected_keys)

    return "\n".join(f"- {format_memory_for_injection(content)}" for _, content in selected)
