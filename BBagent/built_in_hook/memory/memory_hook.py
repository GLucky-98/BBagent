from typing import List
import hashlib
import logging
from datetime import datetime, timedelta

from ...core.hook import HookContext
from ...core.message import HumanMessage, TextBlock, Turn
from ...core.message import Message
from ...core.agent import SubAgent
from ...core.logger import AgentLogger
from ...core.model import Model

from .memory import MemoryManager
from .memory_tool import create_add_memory_tool, create_delete_memory_tool, inject_memory_context

HARD_CLEAN_STALE_DAYS = 30

EXTRACT_SYSTEM_PROMPT = """You are a memory extraction assistant. Your task is to analyze conversations and identify information worth preserving as long-term memories about the user.

## Efficiency Requirements

Complete the extraction task efficiently with minimal tool calls:
- Call `add_memory` exactly ONCE at the very end, with all final memories in a single batch.
- Call `write` ONLY when you have long memories (content exceeding 10KB) that need to be saved to files.
- Do NOT make unnecessary tool calls or iterate back and forth.

## What to Extract

Extract information that will remain valuable beyond the current conversation:

1. **User identity and facts** — name, occupation, skill background, technical expertise, etc.
2. **Long-term preferences and styles** — work habits, tool preferences, code style, communication style, etc.
3. **Actionable experiences** — problem-solving methods, pitfalls encountered, effective strategies, debugging techniques, etc.
4. **Conclusive results** — outcomes from multi-turn conversations or tool calls that produced substantial, reusable findings (e.g., a detailed analysis report, a complex code output, a dataset summary).

## Extraction Principles

### DO
- Combine related facts into single, comprehensive memories. Same entity or theme → one memory.
- Express each memory as a complete, self-contained sentence or paragraph.
- For conclusive results that exceed 10KB: save the full content to a file under `long_memory/` using the `write` tool, then store a concise index entry via `add_memory` referencing the file path.

### DO NOT
- Extract fragmented, single-attribute facts (e.g., "user knows Python" alone — merge with related facts or skip).
- Extract temporary or one-time information (e.g., "user has a meeting at 3pm").
- Extract common knowledge (e.g., "Python is a programming language").
- Extract content only relevant to the current task with no lasting value.
- Extract greetings, social pleasantries, or questions that don't reveal personal information.
- Extract anything that cannot form a full, meaningful sentence on its own.

**Rule of thumb:** If a fact is too small to stand alone as a valuable long-term memory, merge it with related facts or skip it. Aim for 3-8 memories per typical conversation.

## Long Memory Handling

When a memory's content exceeds 10KB (e.g., a large analysis report, complex code output):

1. Use the `write` tool to save the full content to `long_memory/<descriptive_filename>.txt`.
2. Use `add_memory` to save a concise index entry describing the file and referencing its path.
   Example: "User performed a database migration analysis; full output saved at long_memory/migration_analysis_2026.txt — key finding: connection pool size was the root cause."
3. Only do this for genuinely substantial and reusable results.

## Workflow

Follow these steps in order:

1. **Extract candidate facts** from the conversation (fragmentation allowed at this stage).
2. **Group by entity or theme** (e.g., user identity, tech stack, work habits, debugging patterns).
3. **Merge each group** into ONE comprehensive, self-contained memory.
4. **Discard trivial or narrow memories** that cannot form a full meaningful sentence.
5. **(Optional) For memories over 10KB**, use `write` to save to `long_memory/` and prepare an index entry.
6. **Call `add_memory` once** with all final memories (including index entries for long memories) in a single batch.

## Example

**Conversation:**
User: "My name is Alice. I'm a backend engineer. I use Python and FastAPI daily."
User: "I prefer dark mode in all my IDEs."
User: "Last week I debugged a production outage caused by a connection pool leak."

**Step 1 — Candidate facts:**
- Name: Alice
- Job: backend engineer
- Tech: Python, FastAPI
- Preference: dark mode
- Experience: connection pool leak caused outage

**Step 2 — Group by theme:**
- Group A (identity): Alice, backend engineer, Python, FastAPI
- Group B (preference): dark mode
- Group C (experience): connection pool leak, production outage

**Step 3 — Merge:**
- "User Alice is a backend engineer whose daily tech stack includes Python and FastAPI."
- "User prefers dark mode in all IDEs."
- "User's debugging experience: a production outage was traced to a connection pool leak."

**Step 4 — Check quality:**
All three are full sentences with lasting value. None are trivial or temporary. Keep all.

**Step 5 — Long memory check:**
None exceed 10KB. Skip this step.

**Step 6 — Batch save:**
Call `add_memory` once with:
[
  "User Alice is a backend engineer whose daily tech stack includes Python and FastAPI.",
  "User prefers dark mode in all IDEs.",
  "User's debugging experience: a production outage was traced to a connection pool leak."
]

## Output Instructions

- If no valuable memories remain after aggregation, respond with: "No valuable memories found."
- Never fabricate or force extraction.
- Each final memory must be complete, independent, and understandable without the current conversation context."""

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


EXTRACT_USER_PROMPT = """Please analyze the following conversation and extract any valuable long-term memories.

## Conversation
{messages_text}

Review the conversation above carefully. Identify information that is worth preserving for future interactions. Use the `add_memory` tool to save all discovered memories at once in a single batch call. If there is nothing worth remembering, simply respond with "No valuable memories found.\""""


async def extract_memories(
    submodel: Model,
    turns: List[Turn],
    memory_manager: MemoryManager,
    session_id: str,
    extract_prompt: str = EXTRACT_SYSTEM_PROMPT,
    subagent_add_memory_tool_prompt: str = ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT,
    extract_user_prompt: str = EXTRACT_USER_PROMPT,
    logger: AgentLogger = None,
):
    from ...built_in_tool import create_write_tool, Policy

    if logger:
        logger.info(
            "Memory extraction SubAgent started (%d turns)",
            len(turns),
            context={"turn_count": len(turns)},
        )

    long_memory_dir = memory_manager.memory_dir / "long_memory"
    long_memory_dir.mkdir(parents=True, exist_ok=True)

    add_memory_tool = create_add_memory_tool(
        memory_manager, lambda: session_id,
        prompt=subagent_add_memory_tool_prompt,
    )
    policy = Policy(cwd=str(memory_manager.memory_dir))
    write_tool = create_write_tool(policy)

    subagent = SubAgent(
        model=submodel,
        system_prompt=extract_prompt,
        tools=[add_memory_tool, write_tool],
        logger=logger,
        name="MemoryExtractor",
    )

    all_messages = []
    for turn in turns:
        all_messages.extend(turn.messages)

    messages_text = _format_messages_for_extraction(all_messages)
    prompt = extract_user_prompt.format(messages_text=messages_text)

    try:
        await subagent.run(HumanMessage(content=prompt))
    except Exception as e:
        if logger:
            logger.warning(
                "Memory extraction SubAgent failed: %s",
                e,
                context={"error": str(e)},
            )
        return

    if logger:
        logger.info("Memory extraction SubAgent completed")
    return


def _group_turns_for_extraction(
    turns: List[Turn],
    small_turn_threshold: int,
    merge_threshold: int,
) -> List[List[Turn]]:
    groups = []
    current_group = []
    current_group_tokens = 0

    for turn in turns:
        t = turn.token_count
        if t < small_turn_threshold:
            if current_group_tokens + t <= merge_threshold:
                current_group.append(turn)
                current_group_tokens += t
            else:
                if current_group:
                    groups.append(current_group)
                current_group = [turn]
                current_group_tokens = t
        else:
            if current_group:
                groups.append(current_group)
            groups.append([turn])
            current_group = []
            current_group_tokens = 0

    if current_group:
        groups.append(current_group)

    return groups


CLEAN_SYSTEM_PROMPT = """You are a memory maintenance assistant. Your task is to analyze the agent's long-term memory store and clean up obsolete, conflicting, or low-quality memories. Execute this task quickly with minimal tool calls — read the file once, analyze, then call delete_memory in a single batch. Do not engage in prolonged thinking or repeated tool calls.

## Steps

1. Use the Read tool to read `memories.json`. Examine each memory's `id`, `content`, `date_created`, `access_count`, and `last_accessed`.
2. Apply the rules below to identify memories to delete.
3. Call `delete_memory` once with all IDs to delete in a single batch.

## Cleanup Rules

### Rule A: Conflicting Information
When two memories contain contradictory information about the same topic, keep the one with the more recent `date_created` and delete the older one.
Examples: "User is a junior developer" vs "User is a senior developer" → keep newer.

### Rule B: Superseded / Obsolete Information
When a newer memory makes an older one clearly outdated, delete the older one.
Examples: "User works at Company A" (old) vs "User works at Company B" (new) → delete old.

### Rule C: Near-Duplicate Memories
When two memories are nearly identical in meaning, keep the one with higher `access_count` (or more recent `date_created` if access counts are equal) and delete the other.

### Rule D: Trivial / Low-Quality Memories
Delete memories that are too vague to be useful, not self-contained, contain temporary/one-time information, or are generic facts that apply to anyone (e.g., "User uses a computer for work").

## Guidelines
- Be conservative: if unsure, keep it. False positives are worse than false negatives.
- Do not delete recently created memories (within 30 days) just because they have low access_count.
- For conflicting/superseded cases, explicitly state which memory is kept and why.
- If nothing needs cleaning, respond with "Memory store is clean, no cleanup needed."
- Report: total memories examined, how many deleted, and per-category counts."""


CLEAN_USER_PROMPT = """Analyze the memories at {memory_dir}/memories.json and clean up obsolete, conflicting, or low-quality ones. Read the file once, apply the cleanup rules, then call delete_memory with all IDs in a single batch. Execute quickly — no prolonged analysis or repeated tool calls."""


async def clean_memory(
    submodel: Model,
    memory_manager: MemoryManager,
    clean_prompt: str = CLEAN_SYSTEM_PROMPT,
    clean_user_prompt: str = CLEAN_USER_PROMPT,
    logger: AgentLogger = None,
):
    from ...built_in_tool import create_read_tool, Policy

    delete_tool = create_delete_memory_tool(memory_manager)
    policy = Policy(cwd=str(memory_manager.memory_dir))
    read_tool = create_read_tool(policy)

    subagent = SubAgent(
        model=submodel,
        system_prompt=clean_prompt,
        tools=[read_tool, delete_tool],
        logger=logger,
        name="MemoryCleaner",
    )

    if logger:
        logger.info("Memory clean SubAgent started")

    prompt = clean_user_prompt.format(memory_dir=memory_manager.memory_dir)

    try:
        await subagent.run(HumanMessage(content=prompt))
    except Exception as e:
        if logger:
            logger.warning(
                "Memory clean SubAgent failed: %s",
                e,
                context={"error": str(e)},
            )
        return

    if logger:
        logger.info("Memory clean SubAgent completed")
    return


def _hard_clean_memories(memory_manager: MemoryManager, logger: logging.Logger = None) -> int:
    all_data = memory_manager.collection.get(include=["documents", "metadatas"])
    ids = all_data.get("ids", [])
    if not ids:
        return 0

    documents = all_data.get("documents", [])
    metadatas = all_data.get("metadatas", [])
    cutoff = datetime.now() - timedelta(days=HARD_CLEAN_STALE_DAYS)

    to_delete = []

    for i, doc_id in enumerate(ids):
        content = documents[i] if i < len(documents) else ""
        if not content or not content.strip():
            to_delete.append(doc_id)
            continue

        if not doc_id:
            to_delete.append(doc_id)
            continue

        metadata = metadatas[i] if i < len(metadatas) else {}
        date_created_str = metadata.get("date_created", "")
        last_accessed_str = metadata.get("last_accessed", "")

        try:
            date_created = datetime.fromisoformat(date_created_str)
        except (ValueError, TypeError):
            date_created = datetime.now()

        if last_accessed_str:
            try:
                last_accessed = datetime.fromisoformat(last_accessed_str)
            except (ValueError, TypeError):
                last_accessed = None
        else:
            last_accessed = None

        if last_accessed is None:
            if date_created < cutoff:
                to_delete.append(doc_id)
        else:
            if last_accessed < cutoff:
                to_delete.append(doc_id)

    for doc_id in to_delete:
        memory_manager.delete_memory(doc_id)

    if logger:
        if to_delete:
            logger.info(
                "Hard clean: examined %d memories, deleted %d (stale/empty/corrupted)",
                len(ids), len(to_delete),
                context={"total_checked": len(ids), "deleted_count": len(to_delete)},
            )
        else:
            logger.debug(
                "Hard clean: examined %d memories, no stale memories found",
                len(ids),
                context={"total_checked": len(ids), "deleted_count": 0},
            )

    return len(to_delete)


INJECT_USER_PREFIX = "[Relevant memories from past messages]\n{search_context}"


async def do_extract_turns(
    turns: List[Turn],
    session_id: str,
    max_context_tokens: int,
    merge_ratio: float,
    small_turn_cap: int,
    submodel: Model,
    memory_manager: MemoryManager,
    extract_prompt: str,
    subagent_add_memory_tool_prompt: str,
    extract_user_prompt: str,
    logger: AgentLogger = None,
):
    merge_threshold = int(max_context_tokens * merge_ratio)
    small_threshold = min(int(merge_threshold / 3), small_turn_cap)
    groups = _group_turns_for_extraction(turns, small_threshold, merge_threshold)

    if logger:
        logger.debug(
            "Extraction: %d turns grouped into %d groups",
            len(turns), len(groups),
            context={"total_turns": len(turns), "group_count": len(groups)},
        )

    for idx, group in enumerate(groups):
        await extract_memories(
            submodel, group, memory_manager, session_id,
            extract_prompt=extract_prompt,
            subagent_add_memory_tool_prompt=subagent_add_memory_tool_prompt,
            extract_user_prompt=extract_user_prompt,
            logger=logger,
        )
        if logger:
            logger.info(
                "Extraction group %d/%d completed",
                idx + 1, len(groups),
                context={"group_index": idx + 1, "total_groups": len(groups), "turn_count": len(group)},
            )
        for turn in group:
            turn.memory_extracted = True


def create_memory_hook(
    memory_manager: MemoryManager,
    submodel: Model,
    extract_prompt: str = EXTRACT_SYSTEM_PROMPT,
    clean_prompt: str = CLEAN_SYSTEM_PROMPT,
    subagent_add_memory_tool_prompt: str = ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT,
    extract_user_prompt: str = EXTRACT_USER_PROMPT,
    clean_user_prompt: str = CLEAN_USER_PROMPT,
    merge_ratio: float = 0.2,
    small_turn_cap: int = 5000,
    max_inject: int = 5,
    max_candidates: int = 50,
    inject_rrf_k: int = 60,
    inject_bm25_weight: float = 0.5,
    inject_vector_weight: float = 0.5,
    inject_user_prompt: str = INJECT_USER_PREFIX,
    clean_mutation_threshold: int = 50,
):

    async def extract_memory_before_compress(ctx: HookContext):
        if not ctx.get('compression_needed', False):
            ctx.agent.logger.debug("Memory extraction skipped (compression not needed)")
            return

        agent = ctx.agent
        session = agent.session
        if not session:
            return

        completed_turns = [t for t in session.turns if t.is_complete and not t.memory_extracted]
        if not completed_turns:
            agent.logger.debug("No completed turns with unextracted memories")
            return

        agent.logger.info(
            "Extracting memories from %d completed turns (before compress)",
            len(completed_turns),
            context={"turn_count": len(completed_turns)},
        )

        await do_extract_turns(
            completed_turns, session.id,
            agent.model.max_context_tokens, merge_ratio, small_turn_cap,
            submodel, memory_manager,
            extract_prompt, subagent_add_memory_tool_prompt, extract_user_prompt,
            agent.logger,
        )

    async def extract_memory_before_new_session(ctx: HookContext):
        agent = ctx.agent
        session = agent.session
        if not session:
            return

        unextracted = [t for t in session.turns if not t.memory_extracted]
        if not unextracted:
            agent.logger.debug("No unextracted turns to extract for new session")
            return

        agent.logger.info(
            "Extracting memories from %d turns (new session)",
            len(unextracted),
            context={"turn_count": len(unextracted)},
        )

        try:
            await do_extract_turns(
                unextracted, session.id,
                agent.model.max_context_tokens, merge_ratio, small_turn_cap,
                submodel, memory_manager,
                extract_prompt, subagent_add_memory_tool_prompt, extract_user_prompt,
                agent.logger,
            )
        except Exception as e:
            agent.logger.warning(
                "Memory extraction on new session failed: %s",
                e,
                context={"error": str(e)},
            )

    async def clean_memory_hook(ctx: HookContext):
        logger = ctx.agent.logger
        hard_deleted = _hard_clean_memories(memory_manager, logger)
        if hard_deleted > 0:
            memory_manager.decrement_mutation_count(hard_deleted)

        mutation_state = memory_manager._load_cleanup_state()
        mutation_count = mutation_state.get("mutation_count", 0)
        if not memory_manager.check_and_reset_mutation(clean_mutation_threshold):
            logger.debug(
                "AI clean skipped: mutation count %d/%d",
                mutation_count, clean_mutation_threshold,
                context={"current_count": mutation_count, "threshold": clean_mutation_threshold},
            )
            return

        logger.info(
            "AI clean triggered: mutation count %d/%d",
            mutation_count, clean_mutation_threshold,
            context={"current_count": mutation_count, "threshold": clean_mutation_threshold},
        )

        try:
            await clean_memory(
                submodel, memory_manager,
                clean_prompt=clean_prompt,
                clean_user_prompt=clean_user_prompt,
                logger=logger,
            )
        except Exception as e:
            logger.warning(
                "AI memory clean SubAgent failed: %s",
                e,
                context={"error": str(e)},
            )

    _last_inject_hash: str = ""

    async def inject_memory_hook(ctx: HookContext):
        nonlocal _last_inject_hash

        agent = ctx.agent

        if not ctx.get('auto_inject', True):
            agent.logger.debug("Memory injection skipped (auto_inject disabled)")
            return

        session = agent.session
        if not session or not session.turns:
            return

        last_msg = session.turns[-1].messages[0]
        query = _format_message_content(last_msg)

        query_hash = hashlib.md5(query.encode()).hexdigest()
        if query_hash == _last_inject_hash:
            agent.logger.debug(
                "Memory injection skipped (duplicate query)",
                context={"query_hash": query_hash[:12]},
            )
            return
        _last_inject_hash = query_hash

        context = await inject_memory_context(
            query=query,
            memory_manager=memory_manager,
            submodel=submodel,
            max_inject=max_inject,
            rrf_k=inject_rrf_k,
            bm25_weight=inject_bm25_weight,
            vector_weight=inject_vector_weight,
            max_candidates=max_candidates,
            logger=agent.logger,
        )

        if not context:
            agent.logger.debug("No relevant memories found to inject")
            return

        memory_count = len(context.split("\n- "))
        agent.logger.info(
            "Injected %d memories into user message",
            memory_count,
            context={"memory_count": memory_count},
        )

        prefix = inject_user_prompt.format(search_context=context) + "\n\n"
        content = last_msg.content
        if isinstance(content, str):
            last_msg.content = prefix + content
        elif isinstance(content, list):
            last_msg.content = [TextBlock(text=prefix)] + content

    return extract_memory_before_compress, extract_memory_before_new_session, clean_memory_hook, inject_memory_hook
