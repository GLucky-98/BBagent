from typing import List
import hashlib

from ...core.agenthook import AgentHook, HookType, HookContext
from ...core.message import HumanMessage, TextBlock
from ...core.message import Message, ModelMessage, Session
from ...core.agent import SubAgent
from ...core.logger import AgentLogger
from ...core.model import Model

from .memory import MemoryManager
from .memory_tool import create_add_memory_tool, create_delete_memory_tool, search_memory_context

EXTRACT_SYSTEM_PROMPT = """You are a memory extraction assistant. Your task is to analyze conversations and identify information worth preserving as long-term memories about the user.

## Memory Types

When extracting memories, consider three categories of information:

1. **user_profile**: User identity and factual information — name, occupation, identity, skill background, technical expertise, etc.
2. **preference**: Long-term preferences and styles — work habits, tool preferences, code style preferences, communication style, etc.
3. **experience**: Actionable experiences — problem-solving methods, pitfalls encountered, effective strategies, debugging techniques, etc.

## CRITICAL: Aggregation & Deduplication (MANDATORY)

You MUST combine related pieces of information into single, comprehensive memories. Do NOT extract fragmented facts.

### 1. Within-session Aggregation (MANDATORY)

Before finalizing any memories, group related candidate facts by entity or theme, then merge them into ONE memory.

**Examples of BAD (fragmented) extraction:**
- "User uses Python"
- "User uses FastAPI"
- "User uses SQLAlchemy"
- "User's name is Alice"
- "Alice is a backend engineer"

**Examples of GOOD (aggregated) extraction:**
- "User's name is Alice, a backend engineer whose tech stack includes Python, FastAPI, and SQLAlchemy."
- "User prefers dark mode in all IDEs and terminals, and uses VS Code with Vim keybindings."

**Merging rules:**
- Same entity (person, tool, project, company) → merge
- Same theme (tech stack, work habits, debugging patterns) → merge
- Same memory type with related content → merge
- Express the combined information as a single, self-contained sentence or paragraph.

### 2. Cross-session Deduplication

Use the `grep` tool to search `memories.json` for similar memories before adding:
- Search for key terms from your aggregated memory (e.g., if the memory mentions "FastAPI", grep for "FastAPI")
- If a similar memory already exists, DO NOT add a duplicate. Instead, consider whether to update the existing memory with new information (this requires a separate update operation, not `add_memory`).
- If no similar memory is found, proceed with adding.

### 3. Quality Threshold – When to Skip Extraction

Do NOT extract if any of the following is true:
- The information is trivial or atomic without context (e.g., "user's name is X" alone, with no other related facts)
- The information is temporary (e.g., "user has a meeting at 3pm")
- The information is common knowledge (e.g., "Python is a programming language")
- The information is purely about the current task and has no lasting value
- The information would result in a memory that is too narrow to be useful on its own

**Rule of thumb:** If a piece of information is so small that it cannot stand alone as a valuable long-term memory, either merge it with related facts or skip it entirely. Aim for 3-8 memories per typical conversation, not dozens.

## Extracting Large Tool Results as Files

When the conversation involves many rounds of tool calls that produced a substantial, valuable result (e.g., a complex code output, a detailed analysis report, a large dataset summary), the tool output itself may be worth preserving. In such cases:

1. Use the `write_to_file` tool to save the full result to a file under `extracted_data/` in the memory directory. Use descriptive filenames (e.g., `extracted_data/database_migration_analysis.txt`).
2. Use the `add_memory` tool to save a concise index entry that describes what the file contains and references it by path. Example index entry: "User performed a complex database migration analysis; full output saved at extracted_data/migration_analysis_2026.txt — key finding: connection pool size was the root cause."
3. Only do this for results that are genuinely substantial and reusable — avoid saving trivial or one-line outputs.
4. Use the `ls` tool to check what files already exist in `extracted_data/` before writing new ones to avoid duplication.

## What to Extract — Complete Criteria

Extract ONLY information that meets ALL of the following:
- Will remain valuable beyond the current conversation.
- Is specific, concrete, and aggregated with related facts (not fragmented).
- Represents a lasting fact, preference, or reusable experience about the user.
- Cannot be inferred from common knowledge.
- Is not a trivial atomic fact that would be useless alone.

## What NOT to Extract (Reinforced)

- Fragmented, single-attribute facts (e.g., "user knows Python" by itself – merge with other tech stack info or skip)
- Temporary or one-time information
- Common knowledge
- Content only relevant to the current task
- Greetings and social pleasantries
- Questions the user asked that don't reveal personal information
- Any information already stored in a similar memory (check with grep)

## Examples of Good vs. Bad Extraction

### Example 1: Fragmented vs. Aggregated

**User says:** "My name is John. I'm a data engineer. I use Spark and Flink daily. I found that repartitioning before a join reduces shuffle in Spark."

**BAD (fragmented):**
- User name is John
- User is a data engineer
- User uses Spark
- User uses Flink
- User had experience with Spark join performance, solution is repartitioning before join

**GOOD (aggregated):**
- "User John is a data engineer whose daily tech stack includes Apache Spark and Apache Flink."
- "User learned that in Spark, repartitioning before a join reduces shuffle overhead, improving performance."

### Example 2: Trivial Atomic Fact

**User says:** "I like VS Code."

**BAD:** Extract "User likes VS Code" as a standalone memory (too narrow).

**GOOD:** Either (a) merge with other editor/preference facts if available, or (b) skip extraction until more context emerges.

### Example 3: Merging Across Memory Types

**User says:** "I'm a backend engineer at CloudScale. I prefer minimalist code. My biggest debugging win was finding that a connection pool leak caused intermittent timeouts."

**GOOD (single memory merging identity, preference, and experience when appropriate?):**
- Separate memories are fine here because they cover different categories, but each is still aggregated:
  - "User is a backend engineer at CloudScale Inc."
  - "User prefers minimalist code with clear naming over verbose comments."
  - "User's past debugging experience: intermittent timeout issues were traced to a connection pool leak; fixing the leak resolved the problem."

## Mandatory Workflow Before Adding Memories

You MUST follow these steps in order:

1. **Extract candidate facts** from the conversation (allow fragmentation at this stage).
2. **Group them** by entity (e.g., user identity, tech stack, tools) and by theme (e.g., debugging patterns, work habits).
3. **Merge** each group into ONE comprehensive memory written in natural, self-contained language.
4. **Check against existing memories** using `grep` on `memories.json` for key terms from each merged memory.
5. **Discard duplicates** and any merged memory that is still too trivial or narrow (less than a full sentence of meaningful information).
6. **Call `add_memory`** once with all final, aggregated memories (batch call).

## Output Instructions

- If no valuable memories are found after aggregation, respond with: "No valuable memories found."
- Never fabricate or force extraction.
- Each final memory must be complete, independent, and understandable without the current conversation context.

## Summary of Anti-Fragmentation Rules

| Rule | Explanation |
|------|-------------|
| Merge related facts | Same entity/theme → one memory |
| No atomic trivia | A single attribute (e.g., "uses Python") is not enough unless merged |
| Quality over quantity | Aim for 3-8 memories per conversation maximum |
| Skip if too narrow | If you can't write a full meaningful sentence, don't extract |
| Batch add after merging | Only call `add_memory` once per conversation with all aggregated memories |"""

ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT = (
    "Save one or more memories to the agent's long-term memory in batch. "
    "You can add multiple memories in a single call.\n\n"
    "Parameters:\n"
    "- memories (List[str]): A list of memory content strings to save. Each content "
    "should be self-contained and understandable without additional context.\n\n"
    "Examples:\n"
    '- ["User prefers dark mode in all code editors"]\n'
    '- ["User is a senior backend engineer at Google"]\n'
    '- ["User once fixed a deadlock by switching from threading to asyncio"]\n'
    '- Combine multiple memories in one call: ["...", "..."]'
)


def _format_message_content(msg: Message) -> str:
    content = msg.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [block.text for block in content if isinstance(block, TextBlock)]
        return " ".join(texts)
    return str(content)


def _format_messages_for_extraction(messages: List[Message]) -> str:
    lines = []
    for msg in messages:
        role = getattr(msg, "role", "unknown")
        text = _format_message_content(msg)
        if not text.strip():
            continue
        if role == "user":
            lines.append(f"User: {text}")
        elif role == "model":
            lines.append(f"Assistant: {text}")
        elif role == "tool":
            tool_name = getattr(msg, "name", "tool")
            lines.append(f"[Tool Result ({tool_name})]: {text}")
    return "\n\n".join(lines)


DEFAULT_EXTRACT_USER_PROMPT = """Please analyze the following conversation and extract any valuable long-term memories.

## Conversation
{messages_text}

Review the conversation above carefully. Identify information about the user that is worth preserving for future interactions. Use the `add_memory` tool to save all discovered memories at once in a single batch call. If there is nothing worth remembering, simply respond with "No valuable memories found.\""""


async def extract_memories(
    submodel: Model,
    session: Session,
    memory_manager: MemoryManager,
    extract_prompt: str = EXTRACT_SYSTEM_PROMPT,
    subagent_add_memory_tool_prompt: str = ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT,
    extract_user_prompt: str = DEFAULT_EXTRACT_USER_PROMPT,
    logger: AgentLogger = None,
):
    from ...built_in_tool import create_write_tool, create_ls_tool, create_read_tool, create_grep_tool, create_find_tool

    extracted_data_dir = memory_manager.memory_dir / "extracted_data"
    extracted_data_dir.mkdir(parents=True, exist_ok=True)

    add_memory_tool = create_add_memory_tool(
        memory_manager, lambda: session.id,
        prompt=subagent_add_memory_tool_prompt,
    )
    write_tool = create_write_tool(cwd=str(memory_manager.memory_dir))
    ls_tool = create_ls_tool(cwd=str(memory_manager.memory_dir))
    read_tool = create_read_tool(cwd=str(memory_manager.memory_dir))
    grep_tool = create_grep_tool(cwd=str(memory_manager.memory_dir))
    find_tool = create_find_tool(cwd=str(memory_manager.memory_dir))

    subagent = SubAgent(
        model=submodel,
        system_prompt=extract_prompt,
        tools=[add_memory_tool, write_tool, ls_tool, read_tool, grep_tool, find_tool],
        logger=logger,
    )

    messages_text = _format_messages_for_extraction(session.messages)
    prompt = extract_user_prompt.format(messages_text=messages_text)

    await subagent.run(HumanMessage(content=prompt))
    return


CLEAN_SYSTEM_PROMPT = """You are a memory maintenance assistant. Your task is to analyze the agent's long-term memory store and clean up obsolete, conflicting, or low-quality memories to keep the memory system healthy and efficient.

## How Memory Storage Works
- Memories are stored as a JSON file in the memory directory: `memories.json`
- Each memory has: `id` (hash), `content` (text), `session_id`, `date_created`, `access_count`, `last_accessed`
- Last accessed being `null` means the memory was never accessed since creation

## Step 1: Read the Memory File
Use the Read tool to read `memories.json`.

Examine the contents carefully. Note each memory's `id`, `content`, `date_created`, `access_count`, and `last_accessed`.

## Step 2: Identify Memories to Clean Using These Rules

### Rule 1: Stale / Unused Memories
Delete memories where:
- `last_accessed` is `null` (never accessed) AND `date_created` is more than 30 days ago
- OR `last_accessed` is more than 30 days ago
Rationale: Memories that are never used or haven't been used in a month are likely irrelevant.

### Rule 2: Conflicting Information
When two memories contain contradictory or conflicting information about the same topic, keep the one with the more recent `date_created` and delete the older one.
Examples:
- "User is a junior developer" vs "User is a senior developer" → keep the newer one
- "User prefers tabs for indentation" vs "User prefers spaces for indentation" → keep the newer one

### Rule 3: Superseded / Obsolete Information
When a newer memory makes an older one clearly outdated:
- "User works at Company A as an intern" (old) vs "User works at Company B as a senior engineer" (new) → delete the old one
- "User is learning Python basics" (old) vs "User is proficient in Python async programming" (new) → delete the old one

### Rule 4: Near-Duplicate Memories
When two memories are nearly identical in meaning (paraphrases of the same fact), keep the one with higher `access_count` (or more recent `date_created` if access counts are equal) and delete the other.

### Rule 5: Trivial / Low-Quality Memories
Delete memories that:
- Are too vague to be useful (e.g., "User likes good code")
- Are not self-contained and require external context
- Contain information that is obviously temporary or one-time
- Contain generic information that applies to anyone (e.g., "User uses a computer for work")

### Rule 6: Empty or Corrupted
Delete any memory whose `content` is empty, or that has an invalid/missing `id`.

## Step 3: Execute Cleanup
Use the `delete_memory` tool with the list of memory IDs to delete. Batch all deletions into a single call for efficiency.

## Important Guidelines
- Be conservative: if unsure whether a memory should be deleted, keep it. False positives (deleting useful memories) are worse than false negatives (keeping stale ones).
- Do NOT delete any memory just because it has low access_count if it was created recently (within 30 days).
- For conflicting/superseded cases, always explicitly state which memory is kept and why the other is deleted.
- If no memories need cleaning, respond with "Memory store is clean, no cleanup needed."
- Count and report: how many total memories were examined, how many were deleted, and the reason categories."""


DEFAULT_CLEAN_USER_PROMPT = """Please perform a thorough cleanup of the agent's long-term memory.

Memory directory: {memory_dir}
Memory file: memories.json

Read the JSON file, analyze the memories against the cleanup rules in your system prompt, and delete any memories that should be removed. Use the delete_memory tool with all IDs to delete in one batch call."""


async def clean_memory(
    submodel: Model,
    memory_manager: MemoryManager,
    clean_prompt: str = CLEAN_SYSTEM_PROMPT,
    clean_user_prompt: str = DEFAULT_CLEAN_USER_PROMPT,
    logger: AgentLogger = None,
):
    from ...built_in_tool import create_read_tool, create_find_tool, create_grep_tool

    delete_tool = create_delete_memory_tool(memory_manager)
    read_tool = create_read_tool(cwd=str(memory_manager.memory_dir))
    glob_tool = create_find_tool(cwd=str(memory_manager.memory_dir))
    grep_tool = create_grep_tool(cwd=str(memory_manager.memory_dir))

    subagent = SubAgent(
        model=submodel,
        system_prompt=clean_prompt,
        tools=[read_tool, glob_tool, grep_tool, delete_tool],
        logger=logger,
    )

    prompt = clean_user_prompt.format(memory_dir=memory_manager.memory_dir)

    await subagent.run(HumanMessage(content=prompt))
    return


DEFAULT_SEARCH_USER_PREFIX = "[Relevant memories from past conversations]\n{search_context}"


def create_memory_hook(
    memory_manager: MemoryManager,
    submodel: Model,
    extract_prompt: str = None,
    clean_prompt: str = None,
    subagent_add_memory_tool_prompt: str = None,
    extract_user_prompt: str = None,
    clean_user_prompt: str = None,
    search_prompt: str = None,
    search_user_prompt: str = None,
    search_n_results: int = 5,
    search_rrf_k: int = 60,
    search_bm25_weight: float = 0.5,
    search_vector_weight: float = 0.5,
):
    extract_prompt = extract_prompt or EXTRACT_SYSTEM_PROMPT
    clean_prompt = clean_prompt or CLEAN_SYSTEM_PROMPT
    subagent_add_memory_tool_prompt = subagent_add_memory_tool_prompt or ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT
    extract_user_prompt = extract_user_prompt or DEFAULT_EXTRACT_USER_PROMPT
    clean_user_prompt = clean_user_prompt or DEFAULT_CLEAN_USER_PROMPT
    search_user_prompt = search_user_prompt or DEFAULT_SEARCH_USER_PREFIX

    async def extract_memory_hook(ctx: HookContext):
        nonlocal _last_search_hash
        _last_search_hash = ""

        agent = ctx.agent
        if not agent or not agent.session:
            return

        await extract_memories(
            submodel, agent.session, memory_manager,
            extract_prompt=extract_prompt,
            subagent_add_memory_tool_prompt=subagent_add_memory_tool_prompt,
            extract_user_prompt=extract_user_prompt,
            logger=agent.logger,
        )

    async def clean_memory_hook(ctx: HookContext):
        await clean_memory(
            submodel, memory_manager,
            clean_prompt=clean_prompt,
            clean_user_prompt=clean_user_prompt,
            logger=ctx.agent.logger,
        )

    _last_search_hash: str = ""

    async def search_memory_hook(ctx: HookContext):
        nonlocal _last_search_hash

        if not ctx.get('auto_search', True):
            return

        agent = ctx.agent
        session = agent.session
        if not session or not session.messages:
            return

        last_msg = session.messages[-1]
        if last_msg.role != "user":
            return

        query = _format_message_content(last_msg)

        query_hash = hashlib.md5(query.encode()).hexdigest()
        if query_hash == _last_search_hash:
            return
        _last_search_hash = query_hash

        context = await search_memory_context(
            query=query,
            memory_manager=memory_manager,
            submodel=submodel,
            agent_dir=str(agent.base_dir),
            n_results=search_n_results,
            rrf_k=search_rrf_k,
            bm25_weight=search_bm25_weight,
            vector_weight=search_vector_weight,
            subagent_prompt=search_prompt,
            logger=agent.logger,
        )

        if not context or "no relevant" in context.lower():
            return

        prefix = search_user_prompt.format(search_context=context) + "\n\n"
        content = last_msg.content
        if isinstance(content, str):
            last_msg.content = prefix + f"[Current message]\n{content}"
        elif isinstance(content, list):
            last_msg.content = [TextBlock(text=prefix)] + content

    return extract_memory_hook, clean_memory_hook, search_memory_hook
