#!/usr/bin/env python3
"""
test_agent_stream.py - Agent streaming output tests

Test Agent streaming response handling.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BBAGENT_PKG = PROJECT_ROOT / "BBagent"
TEST_DIR = PROJECT_ROOT / "test"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BBAGENT_PKG))
sys.path.insert(0, str(TEST_DIR))

from env import get_env
ENV = get_env()

from BBagent.core.agent import Agent, AgentConfig
from BBagent.core.model import AnthropicModel
from BBagent.core.message import HumanMessage, Session


def create_test_agent():
    """Create a test agent."""
    model = AnthropicModel(
        model=ENV["model"],
        api_key=ENV["api_key"],
        base_url=ENV["base_url"],
        max_tokens=1000
    )

    session_dir = Path(__file__).parent.parent / "temp" / "test_agent_stream_session"
    session_dir.mkdir(parents=True, exist_ok=True)
    session = Session.create(session_dir)

    config = AgentConfig(
        model=model,
        name="TestAgent_Stream",
        session=session,
        tools=[],
        skills=[],
    )

    return Agent(config)


def test_agent_stream_text_chunks():
    """Test text chunk streaming."""
    print("[TEST] test_agent_stream_text_chunks")
    try:
        agent = create_test_agent()

        async def run_test():
            chunks = []
            async for chunk in agent.run(HumanMessage(content="Count from 1 to 3")):
                chunks.append(chunk)
                if hasattr(chunk, 'text'):
                    print(f"[CHUNK] text: {chunk.text[:30]}...")
            return chunks

        import asyncio
        chunks = asyncio.run(run_test())
        assert len(chunks) > 0
        print(f"[PASS] Received {len(chunks)} chunks")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_agent_stream_thinking_chunks():
    """Test thinking chunk streaming."""
    print("[TEST] test_agent_stream_thinking_chunks")
    try:
        agent = create_test_agent()

        async def run_test():
            thinking_chunks = 0
            text_chunks = 0
            async for chunk in agent.run(HumanMessage(content="What is 2 + 2? Think step by step.")):
                if hasattr(chunk, 'thinking') and chunk.thinking:
                    thinking_chunks += 1
                if hasattr(chunk, 'text'):
                    text_chunks += 1
            return thinking_chunks, text_chunks

        import asyncio
        thinking, text = asyncio.run(run_test())
        print(f"[PASS] Received {thinking} thinking chunks, {text} text chunks")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_agent_stream_text_chunks,
        test_agent_stream_thinking_chunks,
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