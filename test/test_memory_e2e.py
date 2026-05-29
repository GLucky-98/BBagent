"""
End-to-end test for the complete memory system pipeline.

Covers:
1. Multi-turn conversation → memory extraction via extract_memories()
2. Search context injection via search_memory_context()
3. Memory cleanup via clean_memory()

Test data stored in test/test_data/memory_e2e/

Run: pytest test/test_memory_e2e.py -v -s
"""

import os
import sys
import shutil
from pathlib import Path

import pytest

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

from BBagent.core.model import AnthropicModel
from BBagent.core.message import HumanMessage, ModelMessage, Session
from BBagent.built_in_hook.memory import (
    Memory,
    MemoryManager,
    OllamaEmbedding,
    create_memory_hook,
    extract_memories,
    search_memory_context,
)
from BBagent.built_in_hook.memory.memory_hook import clean_memory

API_KEY = os.environ["API_KEY"]
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
MODEL_NAME = os.environ.get("MODEL", "MiniMax-M2.7-highspeed")

TEST_DATA_DIR = Path(__file__).parent / "test_data" / "memory_e2e"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def test_base_dir():
    d = TEST_DATA_DIR
    d.mkdir(parents=True, exist_ok=True)
    yield d


@pytest.fixture
def run_dir(test_base_dir):
    d = test_base_dir / f"run_{_run_counter()}"
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


_run_seq = 0

def _run_counter():
    global _run_seq
    _run_seq += 1
    return str(_run_seq)


@pytest.fixture
def model():
    return AnthropicModel(
        model=MODEL_NAME,
        api_key=API_KEY,
        base_url=ANTHROPIC_BASE_URL,
        max_tokens=4096,
        temperature=0.7,
    )


@pytest.fixture
def embedding():
    return OllamaEmbedding(
        base_url="http://localhost:11434",
        model="bge-m3",
    )


@pytest.fixture
def memory_manager(run_dir, embedding):
    manager = MemoryManager(
        name="e2e_memories",
        embedding=embedding,
        memory_dir=str(run_dir / "memory"),
    )
    yield manager


# ============================================================================
# Helpers
# ============================================================================

def build_session(session_dir: Path, messages: list[tuple[str, str]]) -> Session:
    """Build a Session from a list of (role, content) tuples."""
    session = Session.create(str(session_dir))
    for role, content in messages:
        if role == "user":
            session.add_message(HumanMessage(content=content))
        elif role == "model":
            session.add_message(ModelMessage(
                id=f"msg_{len(session.messages)}",
                content=content,
                stop_reason="end_turn",
                usage_data={},
                output_tokens=len(content) // 4,
            ))
    return session


async def drain_agent_run(agent_run):
    """Collect text chunks from an agent.run() async generator."""
    text_parts = []
    try:
        async for chunk in agent_run:
            if isinstance(chunk, dict) and chunk.get("type") == "text":
                text_parts.append(chunk["content"])
    except Exception:
        pass
    return "".join(text_parts)


# ============================================================================
# 1. Full Memory Extraction Pipeline
# ============================================================================

class TestMemoryExtractionPipeline:

    MULTI_TURN_CONVERSATION = [
        ("user", "Hi, my name is Alice Chen. I'm a senior DevOps engineer at CloudScale Inc."),
        ("model", "Hello Alice! Great to meet you. As a DevOps engineer at CloudScale, you must work with some interesting infrastructure."),
        ("user", "Yeah, we manage about 500 Kubernetes clusters. I specialize in observability — mostly Prometheus and Grafana. I prefer using Helm charts over Kustomize for deployments."),
        ("model", "That's a massive scale! Helm charts definitely make template management easier at that size. What kind of monitoring challenges do you face?"),
        ("user", "The biggest one is alert fatigue. We get thousands of alerts daily. I solved it by building a custom alert aggregation pipeline that groups related alerts and only pages on-call for critical clusters. Took me three weeks to get right, but it cut our alert volume by 80%."),
        ("model", "An 80% reduction is impressive! That's a really valuable experience. You mentioned you prefer Python for automation — do you use it for the alert pipeline too?"),
        ("user", "Yes, the aggregation pipeline is all Python, using asyncio and Kafka. I also prefer dark mode in all my IDEs and terminals — I find light mode strains my eyes during long on-call shifts."),
        ("model", "Makes total sense. Dark mode is much easier on the eyes, especially at 3am during an incident."),
    ]

    @pytest.mark.asyncio
    async def test_extract_memories_from_long_conversation(self, model, memory_manager, run_dir):
        """Phase 1: Build a multi-turn conversation and extract memories."""
        session = build_session(
            session_dir=run_dir / "session_extract",
            messages=self.MULTI_TURN_CONVERSATION,
        )

        original_invoke = model.async_invoke

        async def diag_invoke(model_input):
            result = await original_invoke(model_input)
            content_preview = ""
            if isinstance(result.content, list):
                texts = [b.text[:200] for b in result.content if hasattr(b, 'text')]
                content_preview = " | ".join(texts)
            else:
                content_preview = str(result.content)[:200]
            print(f"[DIAG] stop={result.stop_reason} tools={len(result.tool_calls)} "
                  f"in={result.input_tokens} out={result.output_tokens} "
                  f"text={content_preview}")
            return result

        model.async_invoke = diag_invoke

        await extract_memories(model, session, memory_manager)

        all_data = memory_manager.collection.get()
        ids = all_data.get("ids", [])
        docs = all_data.get("documents", [])

        print(f"\n[Extract] {len(ids)} memories extracted from {len(self.MULTI_TURN_CONVERSATION) // 2} turns:")
        for doc in docs:
            print(f"  - {doc[:100]}")

        assert len(ids) >= 1, (
            f"Expected at least 1 memory, got {len(ids)}: {docs}"
        )

        all_keywords = " ".join(docs)
        found_keywords = []
        for kw in ["Alice", "DevOps", "CloudScale", "dark", "Helm", "alert", "Kubernetes"]:
            if kw.lower() in all_keywords.lower():
                found_keywords.append(kw)
        print(f"[Extract] Keywords found: {found_keywords}")
        assert len(found_keywords) >= 2, (
            f"Should capture at least 2 key facts about the user, "
            f"found {len(found_keywords)}: {found_keywords}"
        )

    @pytest.mark.asyncio
    async def test_extract_memories_persisted_to_json(self, model, memory_manager, run_dir):
        """Verify memories.json is written after extraction."""
        session = build_session(
            session_dir=run_dir / "session_json",
            messages=[
                ("user", "My name is Bob, I'm a frontend developer who loves Tailwind CSS."),
                ("model", "Nice to meet you Bob! Tailwind is great for rapid prototyping."),
            ],
        )

        await extract_memories(model, session, memory_manager)

        json_path = memory_manager.memory_dir / "memories.json"
        assert json_path.exists(), f"memories.json should exist at {json_path}"

        import json
        with open(json_path, 'r') as f:
            data = json.load(f)
        assert len(data) >= 1, f"memories.json should have at least 1 entry"
        contents = [m["content"] for m in data]
        assert any("Bob" in c for c in contents), f"JSON should contain Bob's info"


# ============================================================================
# 2. Search & Injection Pipeline
# ============================================================================

class TestSearchInjectionPipeline:

    @pytest.mark.asyncio
    async def test_search_finds_previously_stored_memories(self, model, memory_manager, run_dir):
        """Phase 2a: Store memories, then search with a related query."""
        session = build_session(
            session_dir=run_dir / "session_store",
            messages=[
                ("user", "I'm Carol, a data engineer at DataPipe. I work with Apache Spark and Airflow daily. I hate YAML configuration files."),
                ("model", "Interesting! Spark and Airflow are a powerful combination."),
                ("user", "Last month I debugged a Spark OOM issue that turned out to be caused by skewed partitions — one partition had 100x more data than the others."),
                ("model", "Skewed partitions are a classic Spark pitfall. Good catch."),
            ],
        )

        await extract_memories(model, session, memory_manager)

        context = await search_memory_context(
            query="What tools does Carol use and what does she dislike?",
            memory_manager=memory_manager,
            submodel=model,
            agent_dir=str(run_dir),
            n_results=5,
            rrf_k=60,
            bm25_weight=0.5,
            vector_weight=0.5,
        )

        print(f"\n[Search] Query: What tools does Carol use?\nResult: {context[:300]}")

        assert context, "Search should return results"
        assert "no relevant" not in context.lower(), (
            f"Search should find relevant memories, got: {context}"
        )
        assert ("Spark" in context or "Airflow" in context), (
            f"Should mention Carol's tools, got: {context}"
        )

    @pytest.mark.asyncio
    async def test_search_finds_experience_memory(self, model, memory_manager, run_dir):
        """Search for a specific problem-solving experience."""
        session = build_session(
            session_dir=run_dir / "session_exp",
            messages=[
                ("user", "I'm Dan. I once spent two days debugging a production deadlock caused by nested transactions in PostgreSQL. The fix was to switch from SERIALIZABLE to READ COMMITTED isolation level."),
                ("model", "That's a painful one. Deadlocks with SERIALIZABLE are notoriously hard to track down."),
            ],
        )

        await extract_memories(model, session, memory_manager)

        context = await search_memory_context(
            query="What database debugging experience does Dan have?",
            memory_manager=memory_manager,
            submodel=model,
            agent_dir=str(run_dir),
            n_results=5,
            rrf_k=60,
            bm25_weight=0.5,
            vector_weight=0.5,
        )

        print(f"\n[Search] Query: database debugging\nResult: {context[:300]}")

        assert "deadlock" in context.lower() or "postgresql" in context.lower(), (
            f"Should find the deadlock memory, got: {context}"
        )

    @pytest.mark.asyncio
    async def test_search_injection_via_hook(self, model, memory_manager, run_dir):
        """Phase 2b: Verify the search hook properly handles both shttps://github.com/SWE-bench/SWE-bench.gittr and list content types."""
        from BBagent.core.hook import HookContext
        from BBagent.core.message import TextBlock
        from unittest.mock import AsyncMock, patch

        from BBagent.built_in_hook.memory import Memory

        memory = Memory.create(
            content="User is Eve, a mobile developer who prefers Kotlin",
            session_id="sess_eve",
        )
        await memory_manager.add_memories([memory])

        _, _, search_hook_fn = create_memory_hook(
            memory_manager, model,
            search_n_results=3,
        )

        class FakeAgent:
            pass

        agent = FakeAgent()
        agent.base_dir = run_dir
        fake_session = type('FakeSession', (), {'messages': []})()
        fake_session.messages.append(HumanMessage(content="What language do I prefer?"))
        agent.session = fake_session

        ctx = HookContext()
        ctx.set('auto_search', True)
        ctx.agent = agent

        with patch(
            'BBagent.built_in_hook.memory.memory_hook.search_memory_context',
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = "User prefers Kotlin for mobile development"

            await search_hook_fn(ctx)

            content_after = fake_session.messages[-1].content
            print(f"\n[Injection-str] After: {content_after!r}")
            assert "Relevant memories" in content_after, (
                f"str content should have memory context injected"
            )
            assert "Kotlin" in content_after

            mock_search.reset_mock()
            mock_search.return_value = "User is Eve, mobile developer"

            fake_session.messages[-1].content = [TextBlock(text="What language?")]
            await search_hook_fn(ctx)

            list_content = fake_session.messages[-1].content
            print(f"[Injection-list] After: {list_content!r}")
            assert isinstance(list_content, list), "list content should remain a list"
            assert any("Relevant memories" in getattr(b, 'text', '') for b in list_content), (
                f"First block should contain memory context"
            )

    @pytest.mark.asyncio
    async def test_search_no_results_does_not_inject(self, model, memory_manager, run_dir):
        """When search finds nothing, the hook should preserve the message as-is."""
        from BBagent.core.hook import HookContext
        from unittest.mock import AsyncMock, patch

        _, _, search_hook_fn = create_memory_hook(
            memory_manager, model,
            search_n_results=3,
        )

        class FakeAgent:
            pass

        agent = FakeAgent()
        agent.base_dir = run_dir
        fake_session = type('FakeSession', (), {'messages': []})()
        fake_session.messages.append(HumanMessage(content="Bonjour le monde"))
        agent.session = fake_session

        ctx = HookContext()
        ctx.set('auto_search', True)
        ctx.agent = agent

        with patch(
            'BBagent.built_in_hook.memory.memory_hook.search_memory_context',
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = "no relevant memories found"

            await search_hook_fn(ctx)

        final = fake_session.messages[-1].content
        assert final == "Bonjour le monde", (
            f"Message should be unchanged when no relevant memories, got: {final!r}"
        )


# ============================================================================
# 3. Memory Cleanup Pipeline
# ============================================================================

class TestCleanupPipeline:

    STALE_MEMORY_CONTENT = "User used Internet Explorer 6 in 2005 for legacy intranet apps"

    @pytest.mark.asyncio
    async def test_cleanup_removes_stale_memories(self, model, memory_manager, run_dir):
        """Add a mix of fresh and stale memories, then run cleanup."""
        from BBagent.built_in_hook.memory import Memory
        from datetime import datetime, timedelta

        fresh_mem = Memory.create(
            content="User is a machine learning researcher focusing on transformers",
            session_id="sess_fresh",
        )
        fresh_mem.date_created = datetime.now().isoformat()
        fresh_mem.last_accessed = datetime.now().isoformat()

        stale_mem1 = Memory.create(
            content=self.STALE_MEMORY_CONTENT,
            session_id="sess_old",
        )
        stale_mem1.date_created = (datetime.now() - timedelta(days=60)).isoformat()
        stale_mem1.last_accessed = ""

        stale_mem2 = Memory.create(
            content="User used to prefer tabs but now uses spaces — this is a conflicting old entry about indentation",
            session_id="sess_old",
        )
        stale_mem2.date_created = (datetime.now() - timedelta(days=90)).isoformat()
        stale_mem2.last_accessed = ""

        fresh_mem2 = Memory.create(
            content="User prefers spaces for indentation in all Python projects",
            session_id="sess_fresh",
        )
        fresh_mem2.date_created = datetime.now().isoformat()
        fresh_mem2.last_accessed = datetime.now().isoformat()

        await memory_manager.add_memories([fresh_mem, stale_mem1, stale_mem2, fresh_mem2])

        all_before = memory_manager.collection.get()
        print(f"\n[Cleanup] Before: {len(all_before['ids'])} memories")
        for doc in all_before.get("documents", []):
            print(f"  - {doc[:80]}")

        assert len(all_before["ids"]) >= 3

        await clean_memory(model, memory_manager)

        all_after = memory_manager.collection.get()
        print(f"[Cleanup] After: {len(all_after['ids'])} memories")
        for doc in all_after.get("documents", []):
            print(f"  - {doc[:80]}")

        remaining_content = [d for d in all_after.get("documents", [])]
        assert self.STALE_MEMORY_CONTENT not in remaining_content, (
            f"Stale memory should be cleaned up, remaining: {remaining_content}"
        )

        assert len(all_after["ids"]) < len(all_before["ids"]), (
            "At least one stale/unused memory should have been deleted"
        )

        assert len(all_after["ids"]) <= 2, (
            f"Should keep 2 fresh memories, got {len(all_after['ids'])}: {remaining_content}"
        )

        count_after = memory_manager.collection.get()
        ids_after = count_after.get("ids", [])
        assert len(ids_after) >= 1, "At least one fresh memory should survive cleanup"

    @pytest.mark.asyncio
    async def test_cleanup_preserves_recently_accessed(self, model, memory_manager, run_dir):
        """Old but recently accessed memories should survive cleanup."""
        from BBagent.built_in_hook.memory import Memory
        from datetime import datetime, timedelta

        old_but_accessed = Memory.create(
            content="User configures PostgreSQL with max_connections=200 and shared_buffers=4GB",
            session_id="sess_old_active",
        )
        old_but_accessed.date_created = (datetime.now() - timedelta(days=60)).isoformat()
        old_but_accessed.last_accessed = (datetime.now() - timedelta(days=5)).isoformat()

        recent_mem = Memory.create(
            content="User recently started learning Rust for systems programming",
            session_id="sess_recent",
        )
        recent_mem.date_created = (datetime.now() - timedelta(days=1)).isoformat()
        recent_mem.last_accessed = datetime.now().isoformat()

        await memory_manager.add_memories([old_but_accessed, recent_mem])

        await clean_memory(model, memory_manager)

        all_after = memory_manager.collection.get()
        docs_after = all_after.get("documents", [])
        print(f"\n[Cleanup-Preserve] After: {docs_after}")

        assert any("PostgreSQL" in d for d in docs_after), (
            "Old but recently accessed memory should survive"
        )
        assert any("Rust" in d for d in docs_after), (
            "Recent memory should survive"
        )


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
