from typing import List

from ...core.tool import Tool
from ...core.message import HumanMessage
from ...core.agent import SubAgent
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
) # for main agent only , not for memory extractor subagent

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

def create_delete_memory_tool(memory_manager: MemoryManager, prompt: str = DELETE_MEMORY_TOOL_DESCRIPTION) -> Tool:

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
                description=prompt)



SEARCH_MEMORY_TOOL_DESCRIPTION = (
    "Search the agent's long-term memory for relevant information to complete the user's task. "
    "This tool performs a deep search combining both semantic understanding and "
    "keyword matching, then analyzes the results to find the most useful memories.\n\n"
    "When to use this tool:\n"
    "- The user explicitly asks about something you should remember (e.g. \"do you remember...\", \"have I told you...\", \"what do you know about...\").\n"
    "- The user's question involves their personal information, preferences, past experiences, or history that may have been saved in memory.\n"
    "- You need context from previous conversations to answer the user's question accurately.\n\n"
    "Parameters:\n"
    "- query (str): Ask a question in natural language as if you were asking a person. "
    "Use complete questions rather than keywords. For example, \"What coding preferences does the user have?\" "
    "instead of \"user coding preferences\".\n\n"
    "Examples of when and how to use this tool:\n"
    '- User asks "do you remember what my favorite programming language is?" → query="What is the user\'s favorite programming language?"\n'
    '- User says "tell me what you know about my work" → query="Where does the user work and what is their job?"\n'
    '- User asks "have I mentioned any health issues before?" → query="What health issues has the user mentioned?"\n'
    '- User asks "what was that bug I told you about last time?" → query="What bugs did the user report or fix recently?"\n'
)

def create_search_memory_tool(memory_manager: MemoryManager, submodel: Model, agent_dir_getter, n_results: int , rrf_k: int, bm25_weight: float, vector_weight: float, subagent_prompt: str = None, tool_prompt: str = SEARCH_MEMORY_TOOL_DESCRIPTION) -> Tool:
    
    async def search_memory(query: str) -> str:
        from ...built_in_tool import create_read_tool, create_find_tool, create_grep_tool

        preliminary = await memory_manager.hybrid_search(
            query=query,
            n_results=n_results,
            rrf_k=rrf_k,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
        )

        preliminary_text = ""
        if preliminary.get("documents"):
            preliminary_text = "\n".join(preliminary["documents"])

        cwd = str(agent_dir_getter())
        read_tool = create_read_tool(cwd=cwd)
        glob_tool = create_find_tool(cwd=cwd)
        grep_tool = create_grep_tool(cwd=cwd)

        MEMSEARCH_SUBAGENT_PROMPT = f"""You are a memory search assistant. Your task is to retrieve relevant memory information from the memory store based on the user's query, to help answer their question.

## Efficiency First (Critical)
- First, carefully analyze the automatic search results to determine if they are already sufficient to answer the question.
- Only perform additional tool-based searches if the automatic results are clearly insufficient, and limit to 1-3 supplementary searches at most.
- If the search results are irrelevant or only weakly related to the user's question, honestly report "no relevant memories found" — do not keep searching repeatedly.
- Do not repeatedly try different search strategies for the same query. Keep it concise and efficient.
- If relevant memories are found, concisely extract the most valuable content. Do not pile up irrelevant information.

## Available Tools
- Read: Read file contents
- Glob: Search for files by pattern
- Grep: Search for text within files

## Search Paths
- Memory store: {memory_manager.memory_dir}
- Chat history: {str(agent_dir_getter()/'session')}

## Response Guidelines
- Relevant memories found: Concisely list the key information. No fluff.
- No relevant memories: Directly say "no relevant memories found". Do not fabricate or over-explain."""

        subagent_prompt = subagent_prompt if subagent_prompt else MEMSEARCH_SUBAGENT_PROMPT

        sub_agent = SubAgent(
            model=submodel,
            system_prompt=subagent_prompt,
            tools=[read_tool, glob_tool, grep_tool],
        )

        prompt = f"User query: {query}"
        if preliminary_text:
            prompt += f"\n\nautomatic search results:\n{preliminary_text}"

        result = await sub_agent.run([HumanMessage(content=prompt)])
        return result

    return Tool(search_memory,
                name="search_memory",
                description=tool_prompt)
