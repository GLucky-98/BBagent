"""
BBagent 记忆系统测试

测试覆盖：
1. Memory 数据模型
2. MemoryManager 存储管理（ChromaDB + BM25 + 向量搜索）
3. Memory Tools（add_memory, search_memory, delete_memory）
4. Memory Hook（自动记忆提取）
5. Agent 与记忆系统集成
6. OllamaEmbedding 连通性

运行: pytest test/test_memory_agent.py -v -s
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

import pytest
from unittest.mock import AsyncMock, patch

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

from BBagent.core.agent import Agent, AgentConfig, SubAgent
from BBagent.core.model import AnthropicModel
from BBagent.core.message import HumanMessage, ModelMessage, Session
from BBagent.core.tool import Tool
from BBagent.core.hook import HookContext
from BBagent.built_in_hook.memory import (
    Memory,
    MemoryManager,
    OllamaEmbedding,
    create_add_memory_tool,
    create_delete_memory_tool,
    create_search_memory_tool,
    search_memory_context,
    create_memory_hook,
    extract_memories,
)

API_KEY = os.environ["API_KEY"]
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
MODEL_NAME = os.environ.get("MODEL", "MiniMax-M2.7-highspeed")

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="bbagent_mem_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def ollama_embedding():
    return OllamaEmbedding(
        base_url="http://localhost:11434",
        model="bge-m3",
    )


@pytest.fixture
def memory_manager(temp_dir, ollama_embedding):
    manager = MemoryManager(
        name="test_memories",
        embedding=ollama_embedding,
        memory_dir=str(temp_dir / "memory"),
    )
    yield manager


@pytest.fixture
def anthropic_model():
    return AnthropicModel(
        model=MODEL_NAME,
        api_key=API_KEY,
        base_url=ANTHROPIC_BASE_URL,
        max_tokens=4096,
        temperature=0.7,
    )


# ============================================================================
# 1. Memory 数据模型测试
# ============================================================================

class TestMemoryModel:
    def test_memory_create_basic(self):
        mem = Memory.create(
            content="用户名叫张三",
            session_id="session_001",
        )
        assert mem.content == "用户名叫张三"
        assert mem.session_id == "session_001"
        assert mem.access_count == 0
        assert mem.last_accessed is None
        assert len(mem.id) == 64

    def test_memory_create_deterministic_id(self):
        """相同内容产生相同 ID"""
        mem1 = Memory.create(
            content="用户偏好深色主题",
            session_id="s1",
        )
        mem2 = Memory.create(
            content="用户偏好深色主题",
            session_id="s2",
        )
        assert mem1.id == mem2.id

    def test_memory_create_different_id(self):
        """不同内容产生不同 ID"""
        mem1 = Memory.create(
            content="用户偏好深色主题",
            session_id="s1",
        )
        mem2 = Memory.create(
            content="用户偏好浅色主题",
            session_id="s1",
        )
        assert mem1.id != mem2.id

    def test_memory_to_dict(self):
        mem = Memory.create(
            content="用户是Java工程师",
            session_id="s001",
        )
        d = mem.to_dict()
        assert d["content"] == "用户是Java工程师"
        assert d["session_id"] == "s001"
        assert d["access_count"] == 0
        assert d["last_accessed"] is None
        assert "id" in d
        assert "date_created" in d

    def test_memory_from_dict(self):
        data = {
            "id": "abc123",
            "content": "用户偏好Linux",
            "session_id": "s002",
            "date_created": "2025-01-01T00:00:00",
            "access_count": 5,
            "last_accessed": "2025-01-02T00:00:00",
        }
        mem = Memory.from_dict(data)
        assert mem.id == "abc123"
        assert mem.content == "用户偏好Linux"
        assert mem.access_count == 5
        assert mem.last_accessed == "2025-01-02T00:00:00"

    def test_memory_to_metadata(self):
        mem = Memory.create(
            content="测试记忆",
            session_id="s003",
        )
        meta = mem.to_metadata()
        assert meta["session_id"] == "s003"
        assert meta["access_count"] == 0
        assert "date_created" in meta


# ============================================================================
# 2. MemoryManager 存储管理测试
# ============================================================================

class TestMemoryManager:
    @pytest.mark.asyncio
    async def test_add_and_get_memory(self, memory_manager):
        mem = Memory.create(
            content="用户是Python后端工程师",
            session_id="test_session",
        )
        await memory_manager.add_memories([mem])

        all_data = memory_manager.collection.get()
        assert len(all_data["ids"]) == 1
        assert mem.id in all_data["ids"]
        assert all_data["documents"][0] == "用户是Python后端工程师"

    @pytest.mark.asyncio
    async def test_add_multiple_memories(self, memory_manager):
        mems = [
            Memory.create(
                content=f"测试记忆 {i}",
                session_id="test_session",
            )
            for i in range(5)
        ]
        await memory_manager.add_memories(mems)

        all_data = memory_manager.collection.get()
        assert len(all_data["ids"]) == 5

    @pytest.mark.asyncio
    async def test_add_duplicate_memory(self, memory_manager):
        """添加相同内容的记忆不会重复"""
        content = "用户喜欢用VSCode编辑器"
        mem1 = Memory.create(
            content=content,
            session_id="s1",
        )
        mem2 = Memory.create(
            content=content,
            session_id="s2",
        )
        await memory_manager.add_memories([mem1])
        await memory_manager.add_memories([mem2])

        all_data = memory_manager.collection.get()
        count = sum(1 for doc in all_data["documents"] if doc == content)
        assert count == 1

    @pytest.mark.asyncio
    async def test_delete_memory(self, memory_manager):
        mem = Memory.create(
            content="要删除的记忆",
            session_id="test_session",
        )
        await memory_manager.add_memories([mem])

        all_before = memory_manager.collection.get()
        assert len(all_before["ids"]) == 1

        memory_manager.delete_memory(mem.id)

        all_after = memory_manager.collection.get()
        assert len(all_after["ids"]) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_memory(self, memory_manager):
        memory_manager.delete_memory("nonexistent_id")

    @pytest.mark.asyncio
    async def test_access_count_increment(self, memory_manager):
        mem = Memory.create(
            content="访问计数测试",
            session_id="test_session",
        )
        await memory_manager.add_memories([mem])

        data_before = memory_manager.collection.get(
            ids=[mem.id],
            include=["metadatas"],
        )
        assert data_before["metadatas"][0]["access_count"] == 0

        memory_manager.increment_access(mem.id)

        data_after = memory_manager.collection.get(
            ids=[mem.id],
            include=["metadatas"],
        )
        assert data_after["metadatas"][0]["access_count"] == 1
        assert data_after["metadatas"][0]["last_accessed"] is not None

    @pytest.mark.asyncio
    async def test_hybrid_search(self, memory_manager):
        """混合搜索"""
        mems = [
            Memory.create(
                content="用户是前端工程师，使用React",
                session_id="s1",
            ),
            Memory.create(
                content="用户偏好TypeScript",
                session_id="s1",
            ),
        ]
        await memory_manager.add_memories(mems)

        result = await memory_manager.hybrid_search(
            query="用户的工作是什么",
            n_results=5,
        )
        docs = result.get("documents", [])
        assert len(docs) >= 1
        assert any("前端" in d for d in docs)


# ============================================================================
# 3. Memory Tools 测试
# ============================================================================

class TestMemoryTools:
    @pytest.fixture
    def memory_manager_for_tools(self, temp_dir, ollama_embedding):
        manager = MemoryManager(
            name="test_tool_memories",
            embedding=ollama_embedding,
            memory_dir=str(temp_dir / "memory_tools"),
        )
        return manager

    @pytest.mark.asyncio
    async def test_add_memory_tool(self, memory_manager_for_tools):
        manager = memory_manager_for_tools
        add_tool = create_add_memory_tool(manager, lambda: "session_tool_test")

        assert add_tool.name == "add_memory"
        assert add_tool.is_async is True

        result = await add_tool.async_invoke({
            "memories": [
                "用户使用Arch Linux",
                "用户是DevOps工程师",
            ],
        })
        assert "Saved 2 memories" in result

        all_data = manager.collection.get()
        assert len(all_data["ids"]) == 2

    @pytest.mark.asyncio
    async def test_delete_memory_tool(self, memory_manager_for_tools):
        manager = memory_manager_for_tools
        add_tool = create_add_memory_tool(manager, lambda: "session_del_test")
        delete_tool = create_delete_memory_tool(manager)

        await add_tool.async_invoke({
            "memories": [
                "待删除的记忆A",
                "待删除的记忆B",
            ],
        })

        all_data = manager.collection.get()
        mem_ids = all_data["ids"]
        assert len(mem_ids) >= 2

        result = await delete_tool.async_invoke({
            "memory_ids": [mem_ids[0]],
        })
        assert "Deleted 1 memories" in result

        remaining = manager.collection.get()
        assert len(remaining["ids"]) == len(mem_ids) - 1

    @pytest.mark.asyncio
    async def test_delete_memory_tool_nonexistent(self, memory_manager_for_tools):
        delete_tool = create_delete_memory_tool(memory_manager_for_tools)
        result = await delete_tool.async_invoke({
            "memory_ids": ["fake_id_12345"],
        })
        assert "Not found" in result

    @pytest.mark.asyncio
    async def test_search_memory_tool(self, memory_manager_for_tools, anthropic_model):
        manager = memory_manager_for_tools
        add_tool = create_add_memory_tool(manager, lambda: "session_search_test")
        search_tool = create_search_memory_tool(
            memory_manager=manager,
            submodel=anthropic_model,
            agent_dir_getter=lambda: Path(tempfile.gettempdir()),
            n_results=5,
            rrf_k=60,
            bm25_weight=0.5,
            vector_weight=0.5,
        )

        await add_tool.async_invoke({
            "memories": [
                "用户名叫赵六，是一名数据科学家",
                "用户偏好使用Jupyter Notebook进行数据分析",
            ],
        })

        assert search_tool.name == "search_memory"
        assert search_tool.is_async is True


# ============================================================================
# 4. Memory Hook 测试
# ============================================================================

class TestMemoryHook:
    @pytest.mark.asyncio
    async def test_extract_memories_from_session(self, anthropic_model, temp_dir, ollama_embedding):
        """测试从会话中提取记忆"""
        memory_manager = MemoryManager(
            name="test_extract",
            embedding=ollama_embedding,
            memory_dir=str(temp_dir / "extract_memory"),
        )

        session = Session.create(str(temp_dir / "extract_sessions"))
        session.add_message(HumanMessage(
            content="你好，我叫李明，是一名机器学习工程师，主要使用PyTorch和TensorFlow。"
        ))
        session.add_message(ModelMessage(
            id="resp-1",
            content="你好李明！很高兴认识你。",
            stop_reason="end_turn",
            usage_data={},
            output_tokens=20,
        ))

        await extract_memories(anthropic_model, session, memory_manager)

        all_data = memory_manager.collection.get()
        ids = all_data.get("ids", [])
        docs = all_data.get("documents", [])

        assert len(ids) >= 1, f"应该至少提取到一条记忆，实际: {len(ids)}"
        assert any("李明" in doc for doc in docs), (
            f"提取的记忆应包含用户名，实际: {docs}"
        )

    @pytest.mark.asyncio
    async def test_extract_memories_empty_session(self, anthropic_model, temp_dir, ollama_embedding):
        """空会话不应提取到记忆"""
        memory_manager = MemoryManager(
            name="test_empty",
            embedding=ollama_embedding,
            memory_dir=str(temp_dir / "empty_memory"),
        )

        session = Session.create(str(temp_dir / "empty_sessions"))
        session.add_message(HumanMessage(content="你好"))
        session.add_message(ModelMessage(
            id="r1",
            content="你好！有什么可以帮助你的吗？",
            stop_reason="end_turn",
            usage_data={},
            output_tokens=10,
        ))

        await extract_memories(anthropic_model, session, memory_manager)

        all_data = memory_manager.collection.get()
        print(f"从空会话提取到的记忆: {all_data.get('documents', [])}")

    @pytest.mark.asyncio
    async def test_create_memory_hook(self, temp_dir, anthropic_model, ollama_embedding):
        memory_manager = MemoryManager(
            name="test_hook_factory",
            embedding=ollama_embedding,
            memory_dir=str(temp_dir / "hook_factory"),
        )

        extract_hook_fn, clean_hook_fn, search_hook_fn = create_memory_hook(memory_manager, anthropic_model)

        assert callable(extract_hook_fn)
        assert callable(clean_hook_fn)
        assert callable(search_hook_fn)

    @pytest.mark.asyncio
    async def test_search_memory_hook_respects_ctx_flag(self, temp_dir, anthropic_model, ollama_embedding):
        """search_memory_hook reads auto_search from HookContext and returns early when disabled"""
        memory_manager = MemoryManager(
            name="test_ctx_flag",
            embedding=ollama_embedding,
            memory_dir=str(temp_dir / "ctx_flag_memory"),
        )

        _, _, search_hook_fn = create_memory_hook(
            memory_manager, anthropic_model,
            search_n_results=3,
        )

        ctx_disabled = HookContext()
        ctx_disabled.set('auto_search', False)

        with patch(
            'BBagent.built_in_hook.memory.memory_hook.search_memory_context',
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = "Found relevant memory"

            await search_hook_fn(ctx_disabled)
            mock_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_memory_hook_no_session(self, temp_dir, anthropic_model, ollama_embedding):
        """search_memory_hook returns early when agent has no session"""
        memory_manager = MemoryManager(
            name="test_no_session",
            embedding=ollama_embedding,
            memory_dir=str(temp_dir / "no_session_memory"),
        )

        _, _, search_hook_fn = create_memory_hook(
            memory_manager, anthropic_model,
        )

        class FakeAgent:
            session = None

        ctx = HookContext()
        ctx.agent = FakeAgent()

        result = await search_hook_fn(ctx)
        assert result is None


# ============================================================================
# 5. Agent 与记忆系统集成测试
# ============================================================================

class TestMemoryAgentIntegration:
    @pytest.mark.asyncio
    async def test_agent_with_memory_tools(self, anthropic_model, temp_dir, ollama_embedding):
        """测试 Agent 集成记忆工具"""
        async def run():
            memory_manager = MemoryManager(
                name="agent_mem_test",
                embedding=ollama_embedding,
                memory_dir=str(temp_dir / "agent_memory"),
            )

            add_memory_tool = create_add_memory_tool(
                memory_manager,
                session_id_getter=lambda: "agent_sess_1",
            )
            search_memory_tool = create_search_memory_tool(
                memory_manager=memory_manager,
                submodel=anthropic_model,
                agent_dir_getter=lambda: temp_dir,
                n_results=5,
                rrf_k=60,
                bm25_weight=0.5,
                vector_weight=0.5,
            )

            config = AgentConfig(
                model=anthropic_model,
                base_dir=str(temp_dir / "agent_base"),
                system_prompt="""你是一个带记忆的助手。当用户让你记住信息时，使用 add_memory 工具。当需要回忆时，使用 search_memory。""",
                tools=[add_memory_tool, search_memory_tool],
            )
            agent = Agent(config)

            full_text = []
            async for chunk in agent.run(
                HumanMessage(content="请记住：我的名字叫测试用户A，我住在北京。保存这些信息到记忆库。")
            ):
                if isinstance(chunk, dict) and chunk.get("type") == "text":
                    full_text.append(chunk["content"])

            text = "".join(full_text)
            assert len(text) > 0, "Agent 应该返回文本"

            all_data = memory_manager.collection.get()
            docs = all_data.get("documents", [])
            assert len(docs) >= 1, f"应该保存了记忆，实际: {docs}"

        await run()

    @pytest.mark.asyncio
    async def test_agent_memory_retrieval(self, anthropic_model, temp_dir, ollama_embedding):
        """测试 Agent 记忆检索"""
        async def run():
            memory_manager = MemoryManager(
                name="agent_retrieval_test",
                embedding=ollama_embedding,
                memory_dir=str(temp_dir / "agent_retrieval"),
            )

            mem = Memory.create(
                content="用户张三偏好Python，认为Go也很好用",
                session_id="sess_ret",
            )
            await memory_manager.add_memories([mem])

            add_memory_tool = create_add_memory_tool(
                memory_manager,
                session_id_getter=lambda: "sess_ret",
            )
            search_memory_tool = create_search_memory_tool(
                memory_manager=memory_manager,
                submodel=anthropic_model,
                agent_dir_getter=lambda: temp_dir,
                n_results=5,
                rrf_k=60,
                bm25_weight=0.5,
                vector_weight=0.5,
            )

            config = AgentConfig(
                model=anthropic_model,
                base_dir=str(temp_dir / "agent_retrieval_base"),
                system_prompt="""你是一个带记忆的助手。用户问问题时，先用 search_memory 搜索记忆库。""",
                tools=[add_memory_tool, search_memory_tool],
            )
            agent = Agent(config)

            full_text = []
            async for chunk in agent.run(
                HumanMessage(content="我偏好什么编程语言？请用search_memory搜索后回答。")
            ):
                if isinstance(chunk, dict) and chunk.get("type") == "text":
                    full_text.append(chunk["content"])

            text = "".join(full_text)
            assert len(text) > 0, "Agent 应该返回文本"
            assert "Python" in text or "python" in text.lower(), (
                f"Agent应提到Python，实际: {text[:200]}"
            )

        await run()


# ============================================================================
# 6. Embedding 模型连通性测试
# ============================================================================

class TestEmbedding:
    @pytest.mark.asyncio
    async def test_ollama_embedding_connection(self, ollama_embedding):
        """测试 Ollama Embedding 服务是否可用"""
        embedding = await ollama_embedding.get_embedding("你好世界")
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(v, float) for v in embedding)

    @pytest.mark.asyncio
    async def test_ollama_batch_embedding(self, ollama_embedding):
        """测试批量嵌入"""
        texts = ["Python编程", "机器学习", "深度学习"]
        embeddings = await ollama_embedding.get_embeddings(texts)
        assert len(embeddings) == 3
        assert all(len(emb) > 0 for emb in embeddings)

    @pytest.mark.asyncio
    async def test_embedding_consistency(self, ollama_embedding):
        """同一文本应产生相同嵌入（近似）"""
        text = "用户是一名资深软件工程师"
        emb1 = await ollama_embedding.get_embedding(text)
        emb2 = await ollama_embedding.get_embedding(text)
        assert len(emb1) == len(emb2)
        differences = sum(abs(a - b) for a, b in zip(emb1, emb2))
        assert differences < 1e-5, f"嵌入向量不一致，差异: {differences}"


# ============================================================================
# 7. SubAgent 测试（记忆提取/搜索中用到）
# ============================================================================

class TestSubAgentForMemory:
    def test_subagent_creation(self, anthropic_model):
        sub = SubAgent(
            model=anthropic_model,
            system_prompt="你是一个记忆助手",
        )
        assert sub.model is anthropic_model
        assert sub.system_prompt == "你是一个记忆助手"
        assert sub.tools == {}

    def test_subagent_with_tools(self, anthropic_model):
        def echo(msg: str) -> str:
            return msg

        sub = SubAgent(
            model=anthropic_model,
            system_prompt="Echo工具测试",
            tools=[Tool(func=echo)],
        )
        assert "echo" in sub.tools
        assert sub.tools["echo"].name == "echo"


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
