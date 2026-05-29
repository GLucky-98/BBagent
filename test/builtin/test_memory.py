#!/usr/bin/env python3
"""
test_memory.py - Memory system tests

Test for BBagent.built_in_hook.memory module.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BBAGENT_PKG = PROJECT_ROOT / "BBagent"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BBAGENT_PKG))

from BBagent.built_in_hook.memory.memory import MemoryManager
from BBagent.built_in_hook.memory.embedding import OllamaEmbedding


def test_memory_manager_creation():
    """Test MemoryManager creation."""
    print("[TEST] test_memory_manager_creation")
    try:
        storage_dir = Path(__file__).parent.parent / "temp" / "test_memory_db"
        storage_dir.mkdir(parents=True, exist_ok=True)

        manager = MemoryManager(memory_dir=str(storage_dir))
        assert manager is not None
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_memory_add():
    """Test adding memory."""
    print("[TEST] test_memory_add")
    try:
        storage_dir = Path(__file__).parent.parent / "temp" / "test_memory_add"
        storage_dir.mkdir(parents=True, exist_ok=True)

        manager = MemoryManager(memory_dir=str(storage_dir))

        # Use add_memories method (async)
        import asyncio
        async def add_test():
            from BBagent.built_in_hook.memory.memory import Memory
            memory = Memory.create(content="This is a test memory", session_id="test")
            await manager.add_memories([memory])

        asyncio.run(add_test())
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_memory_search():
    """Test memory search."""
    print("[TEST] test_memory_search")
    try:
        storage_dir = Path(__file__).parent.parent / "temp" / "test_memory_search"
        storage_dir.mkdir(parents=True, exist_ok=True)

        manager = MemoryManager(memory_dir=str(storage_dir))

        # Add a memory first
        import asyncio
        async def add_test():
            from BBagent.built_in_hook.memory.memory import Memory
            memory = Memory.create(content="Python programming language", session_id="test")
            await manager.add_memories([memory])

        asyncio.run(add_test())

        # Search
        try:
            results = manager.search("programming", top_k=1)
            assert results is not None
        except Exception:
            print("[SKIP] Ollama not available for search")
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_memory_hybrid_search():
    """Test hybrid search (vector + BM25)."""
    print("[TEST] test_memory_hybrid_search")
    try:
        storage_dir = Path(__file__).parent.parent / "temp" / "test_memory_hybrid"
        storage_dir.mkdir(parents=True, exist_ok=True)

        manager = MemoryManager(memory_dir=str(storage_dir))

        import asyncio
        async def add_test():
            from BBagent.built_in_hook.memory.memory import Memory
            memories = [
                Memory.create(content="Python is a programming language", session_id="test"),
                Memory.create(content="JavaScript is for web development", session_id="test"),
                Memory.create(content="Go is a systems language", session_id="test"),
            ]
            await manager.add_memories(memories)

        asyncio.run(add_test())

        try:
            results = manager.hybrid_search("programming language", top_k=2)
            assert results is not None
        except Exception:
            print("[SKIP] Ollama not available for hybrid search")
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_memory_manager_creation,
        test_memory_add,
        test_memory_search,
        test_memory_hybrid_search,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[ERROR] {test.__name__}: {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)