from typing import List

from ...core.agenthook import AgentHook, HookType, HookContext
from ...core.message import HumanMessage, TextBlock
from ...core.message import Message, ModelMessage, Session
from ...core.agent import SubAgent
from ...core.model import Model

from .memory import MemoryManager
from .memory_tool import create_add_memory_tool, create_delete_memory_tool

EXTRACT_SYSTEM_PROMPT = """You are a memory extraction assistant. Your task is to analyze conversations and identify information worth preserving as long-term memories about the user.

## Memory Types
You can extract three types of memories:

1. **user_profile**: User identity and factual information — name, occupation, identity, skill background, technical expertise, etc.
2. **preference**: Long-term preferences and styles — work habits, tool preferences, code style preferences, communication style, etc.
3. **experience**: Actionable experiences — problem-solving methods, pitfalls encountered, effective strategies, debugging techniques, etc.

## How to Extract Memories
- Use the `add_memory` tool to save all discovered memories at once in a single batch call.
- Each memory must be self-contained and understandable without additional context from the current conversation.
- Assign the correct `memory_type` to each memory.

## What to Extract — Criteria
Extract ONLY information that meets ALL of the following:
- Will remain valuable beyond the current conversation
- Is specific and concrete (not vague or generic)
- Represents a lasting fact, preference, or reusable experience about the user
- Cannot be inferred from common knowledge

## What NOT to Extract
- Temporary or one-time information (e.g., "the user has a meeting at 3pm today")
- Common knowledge that anyone would know (e.g., "Python is a programming language")
- Content that is only relevant to the current task at hand
- Greetings, social pleasantries, or trivial exchanges
- General questions the user asked that don't reveal personal information

## Examples

Good memories worth extracting:
- "User is a Python backend engineer specializing in FastAPI and SQLAlchemy" → memory_type="user_profile"
- "User prefers concise code with minimal comments, values readability through good naming" → memory_type="preference"
- "When debugging async database issues, the user found that checking the connection pool configuration first saved hours of troubleshooting" → memory_type="experience"
- "User works at Google as a Senior Software Engineer on the Cloud Storage team" → memory_type="user_profile"
- "User strongly prefers dark theme in all development tools and IDEs" → memory_type="preference"

NOT worth extracting:
- "User asked about Python list comprehensions" → too generic, no personal info revealed
- "Assistant explained how asyncio.gather() works" → common knowledge
- "User said hello and thanked the assistant" → trivial

## Extraction Rules
1. Each memory must be complete and independently understandable.
2. Do not extract temporary or one-time information.
3. Do not duplicate common knowledge or generic facts.
4. If the conversation contains no memorable information, simply respond with "No valuable memories found." — do NOT force extraction or fabricate memories.
5. Avoid extracting near-duplicate memories within the same extraction session.
6. Focus on information that reveals something specific and lasting about the user."""

ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT = (
    "Save one or more memories to the agent's long-term memory in batch. "
    "You can add multiple memories in a single call.\n\n"
    "Parameters:\n"
    "- memories (List[MemoryItem]): A list of memory items to save. Each item has:\n"
    "  - content (str): The memory content to save. Make it self-contained and "
    "understandable without additional context.\n"
    "  - memory_type (str): One of 'user_profile', 'preference', or 'experience'.\n\n"
    "Examples:\n"
    '- [{"content": "User prefers dark mode in all code editors", "memory_type": "preference"}]\n'
    '- [{"content": "User is a senior backend engineer at Google", "memory_type": "user_profile"}]\n'
    '- [{"content": "User once fixed a deadlock by switching from threading to asyncio", "memory_type": "experience"}]\n'
    '- Combine multiple memories in one call: [{"content": "...", "memory_type": "..."}, {"content": "...", "memory_type": "..."}]'
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


async def extract_memories(submodel: Model, session: Session, memory_manager: MemoryManager):
    add_memory_tool = create_add_memory_tool(
        memory_manager, lambda: session.id,
        prompt=ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT,
    )

    subagent = SubAgent(
        model=submodel,
        system_prompt=EXTRACT_SYSTEM_PROMPT,
        tools=[add_memory_tool],
    )

    messages_text = _format_messages_for_extraction(session.messages)

    prompt = f"""Please analyze the following conversation and extract any valuable long-term memories.

## Conversation
{messages_text}

Review the conversation above carefully. Identify information about the user that is worth preserving for future interactions. Use the `add_memory` tool to save all discovered memories at once in a single batch call. If there is nothing worth remembering, simply respond with "No valuable memories found.\""""

    await subagent.run(HumanMessage(content=prompt))
    return 


CLEAN_SYSTEM_PROMPT = """You are a memory maintenance assistant. Your task is to analyze the agent's long-term memory store and clean up obsolete, conflicting, or low-quality memories to keep the memory system healthy and efficient.

## How Memory Storage Works
- Memories are stored as JSON files in the memory directory, one file per memory_type: `user_profile.json`, `preference.json`, `experience.json`
- Each memory has: `id` (hash), `content` (text), `type`, `session_id`, `date_created`, `access_count`, `last_accessed`
- Last accessed being `null` means the memory was never accessed since creation

## Step 1: Read the Memory Files
Use the Read tool to read each JSON file:
- `user_profile.json`
- `preference.json`
- `experience.json`

Examine the contents carefully. Note each memory's `id`, `content`, `type`, `date_created`, `access_count`, and `last_accessed`.

## Step 2: Identify Memories to Clean Using These Rules

### Rule 1: Stale / Unused Memories
Delete memories where:
- `last_accessed` is `null` (never accessed) AND `date_created` is more than 30 days ago
- OR `last_accessed` is more than 30 days ago
Rationale: Memories that are never used or haven't been used in a month are likely irrelevant.

### Rule 2: Conflicting Information
When two memories within the same memory_type contain contradictory or conflicting information about the same topic, keep the one with the more recent `date_created` and delete the older one.
Examples:
- "User is a junior developer" vs "User is a senior developer" → keep the newer one
- "User prefers tabs for indentation" vs "User prefers spaces for indentation" → keep the newer one

### Rule 3: Superseded / Obsolete Information
When a newer memory makes an older one clearly outdated:
- "User works at Company A as an intern" (old) vs "User works at Company B as a senior engineer" (new) → delete the old one
- "User is learning Python basics" (old) vs "User is proficient in Python async programming" (new) → delete the old one

### Rule 4: Near-Duplicate Memories
When two memories in the same type are nearly identical in meaning (paraphrases of the same fact), keep the one with higher `access_count` (or more recent `date_created` if access counts are equal) and delete the other.

### Rule 5: Trivial / Low-Quality Memories
Delete memories that:
- Are too vague to be useful (e.g., "User likes good code")
- Are not self-contained and require external context
- Contain information that is obviously temporary or one-time
- Contain generic information that applies to anyone (e.g., "User uses a computer for work")

### Rule 6: Empty or Corrupted
Delete any memory whose `content` is empty, or that has an invalid/missing type.

## Step 3: Execute Cleanup
Use the `delete_memory` tool with the list of memory IDs to delete. Batch all deletions into a single call for efficiency.

## Important Guidelines
- Be conservative: if unsure whether a memory should be deleted, keep it. False positives (deleting useful memories) are worse than false negatives (keeping stale ones).
- Do NOT delete any memory just because it has low access_count if it was created recently (within 30 days).
- For conflicting/superseded cases, always explicitly state which memory is kept and why the other is deleted.
- If no memories need cleaning, respond with "Memory store is clean, no cleanup needed."
- Count and report: how many total memories were examined, how many were deleted, and the reason categories."""


async def clean_memory(submodel: Model, memory_manager: MemoryManager):
    from ...built_in_tool import create_read_tool, create_find_tool, create_grep_tool

    delete_tool = create_delete_memory_tool(memory_manager)
    read_tool = create_read_tool(cwd=str(memory_manager.memory_dir))
    glob_tool = create_find_tool(cwd=str(memory_manager.memory_dir))
    grep_tool = create_grep_tool(cwd=str(memory_manager.memory_dir))

    subagent = SubAgent(
        model=submodel,
        system_prompt=CLEAN_SYSTEM_PROMPT,
        tools=[read_tool, glob_tool, grep_tool, delete_tool],
    )

    prompt = f"""Please perform a thorough cleanup of the agent's long-term memory.

Memory directory: {memory_manager.memory_dir}
Available memory type files: user_profile.json, preference.json, experience.json

Read each JSON file, analyze the memories against the cleanup rules in your system prompt, and delete any memories that should be removed. Use the delete_memory tool with all IDs to delete in one batch call."""

    await subagent.run(HumanMessage(content=prompt))
    return


def create_memory_hook(memory_manager: MemoryManager, submodel: Model) -> AgentHook:
    async def memory_extract_hook(ctx: HookContext):
        agent = ctx.agent
        if not agent or not agent.session:
            return

        await extract_memories(submodel, agent.session, memory_manager)
    
    async def clean_memory_hook(ctx: HookContext):
        await clean_memory(submodel, memory_manager)
    
    return memory_extract_hook, clean_memory_hook
