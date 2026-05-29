"""
Debug script for extract_memories test failure.
Uses the exact same conversation as the test, with response diagnostics.
Usage: python test/_debug_extract.py
"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from BBagent.core.model import AnthropicModel, Model_Input
from BBagent.core.message import HumanMessage, ModelMessage, Session
from BBagent.core.agent import SubAgent
from BBagent.built_in_hook.memory import MemoryManager, OllamaEmbedding
from BBagent.built_in_hook.memory.memory_tool import create_add_memory_tool
from BBagent.built_in_hook.memory.memory_hook import (
    _format_messages_for_extraction,
    EXTRACT_SYSTEM_PROMPT,
    DEFAULT_EXTRACT_USER_PROMPT,
    ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT,
)
from BBagent.built_in_tool import create_write_tool

API_KEY = os.environ["API_KEY"]
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
MODEL_NAME = os.environ.get("MODEL", "MiniMax-M2.7-highspeed")

DEBUG_DIR = Path(__file__).parent / "test_data" / "debug_extract"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

# Exactly the same as the test's MULTI_TURN_CONVERSATION
CONVERSATION = [
    ("user", "Hi, my name is Alice Chen. I'm a senior DevOps engineer at CloudScale Inc."),
    ("model", "Hello Alice! Great to meet you. As a DevOps engineer at CloudScale, you must work with some interesting infrastructure."),
    ("user", "Yeah, we manage about 500 Kubernetes clusters. I specialize in observability — mostly Prometheus and Grafana. I prefer using Helm charts over Kustomize for deployments."),
    ("model", "That's a massive scale! Helm charts definitely make template management easier at that size. What kind of monitoring challenges do you face?"),
    ("user", "The biggest one is alert fatigue. We get thousands of alerts daily. I solved it by building a custom alert aggregation pipeline that groups related alerts and only pages on-call for critical clusters. Took me three weeks to get right, but it cut our alert volume by 80%."),
    ("model", "An 80% reduction is impressive! That's a really valuable experience. You mentioned you prefer Python for automation — do you use it for the alert pipeline too?"),
    ("user", "Yes, the aggregation pipeline is all Python, using asyncio and Kafka. I also prefer dark mode in all my IDEs and terminals — I find light mode strains my eyes during long on-call shifts."),
    ("model", "Makes total sense. Dark mode is much easier on the eyes, especially at 3am during an incident."),
]


async def run_debug():
    model = AnthropicModel(
        model=MODEL_NAME, api_key=API_KEY, base_url=ANTHROPIC_BASE_URL,
        max_tokens=4096, temperature=0.7,
    )
    embedding = OllamaEmbedding(base_url="http://localhost:11434")
    memory_manager = MemoryManager(
        name="debug_extract", embedding=embedding,
        memory_dir=str(DEBUG_DIR / "memory"),
    )

    session = Session.create(str(DEBUG_DIR / "session"))
    for role, content in CONVERSATION:
        if role == "user":
            session.add_message(HumanMessage(content=content))
        else:
            session.add_message(ModelMessage(
                id=f"m{len(session.messages)}",
                content=content, stop_reason="end_turn",
                usage_data={}, output_tokens=len(content) // 4,
            ))

    # ===== Diagnostic wrapper =====
    original_invoke = model.async_invoke

    async def diagnostic_invoke(model_input: Model_Input):
        print(f"\n[DIAG] model_input: {len(model_input.messages)} msgs, {len(model_input.prompt)} prompt chars")
        print(f"[DIAG] tools: {[t.name for t in model_input.tools]}")

        result = await original_invoke(model_input)

        if result.tool_calls:
            print(result.tool_calls[0])
        print(f"[DIAG] stop_reason={result.stop_reason!r} tool_calls={len(result.tool_calls)}")
        if isinstance(result.content, list):
            for b in result.content:
                t = getattr(b, 'type', '?')
                if t == 'tool_use':
                    print(f"[DIAG]   TOOL_USE: name={getattr(b,'name','?')}")
                elif t == 'text':
                    print(f"[DIAG]   TEXT: {getattr(b,'text','')[:200]}")
        else:
            print(f"[DIAG]   TEXT: {str(result.content)[:200]}")
        return result

    model.async_invoke = diagnostic_invoke
    # ==============================

    long_memory_dir = memory_manager.memory_dir / "long_memory"
    long_memory_dir.mkdir(parents=True, exist_ok=True)

    add_memory_tool = create_add_memory_tool(
        memory_manager, lambda: session.id,
        prompt=ADD_MEMORY_TOOL_DESCRIPTION_SUBAGENT,
    )
    write_tool = create_write_tool(cwd=str(memory_manager.memory_dir))

    subagent = SubAgent(
        model=model,
        system_prompt=EXTRACT_SYSTEM_PROMPT,
        tools=[add_memory_tool, write_tool],
    )

    messages_text = _format_messages_for_extraction(session.messages)
    prompt = DEFAULT_EXTRACT_USER_PROMPT.format(messages_text=messages_text)

    print(f"[DIAG] Formatted conversation ({len(messages_text)} chars):")
    print(messages_text[:500] + "..." if len(messages_text) > 500 else messages_text)
    print(f"[DIAG] Total prompt chars: {len(EXTRACT_SYSTEM_PROMPT) + len(prompt)}")

    result = await subagent.run(HumanMessage(content=prompt))

    all_data = memory_manager.collection.get()
    docs = all_data.get("documents", [])
    print(f"\n[RESULT] {len(docs)} memories extracted")
    for d in docs:
        print(f"  - {d}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_debug())
