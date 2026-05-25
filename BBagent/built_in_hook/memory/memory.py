import re
import json
import asyncio
import hashlib
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from datetime import datetime
from pathlib import Path


import jieba
import chromadb
from rank_bm25 import BM25Okapi

from .embedding import Embedding, OllamaEmbedding

@dataclass
class Memory:
    id: str
    content: str
    session_id: str
    date_created: str
    access_count: int = 0
    last_accessed: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'Memory':
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            session_id=data.get("session_id", ""),
            date_created=data.get("date_created", ""),
            access_count=data.get("access_count", 0),
            last_accessed=data.get("last_accessed", None),
        )

    def to_metadata(self) -> dict:
        return {
            "session_id": self.session_id,
            "date_created": self.date_created,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed or "",
        }

    @staticmethod
    def create(content: str, session_id: str) -> 'Memory':
        return Memory(
            id=hashlib.sha256(content.encode('utf-8')).hexdigest(),
            content=content,
            session_id=session_id,
            date_created=datetime.now().isoformat(),
            access_count=0,
            last_accessed=None,
        )
  

class MemoryManager:

    def __init__(self,
                 name: str = "memories",
                 embedding: Embedding = None,
                 memory_dir: str | Path = "./memory",
                 logger: Optional[logging.Logger] = None):

        if embedding is None:
            embedding = OllamaEmbedding()
        self.embedding = embedding
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(self.memory_dir / "chroma_db"))
        self.collection = self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )

        self.bm25 = None
        self.doc_mapping = {}
        self._bm25_dirty = True

        self.logger = logger or logging.getLogger(__name__)
        self.logger.info(f"MemoryManager initialized: collection={name}, dir={self.memory_dir}")

        self._load_from_files()

    def _dump_memories_json(self):
        path = self.memory_dir / "memories.json"
        all_data = self.collection.get()
        memories = []
        for i, doc_id in enumerate(all_data.get("ids", [])):
            memories.append(Memory(
                id=doc_id,
                content=all_data["documents"][i],
                session_id=all_data["metadatas"][i].get("session_id", ""),
                date_created=all_data["metadatas"][i].get("date_created", ""),
                access_count=all_data["metadatas"][i].get("access_count", 0),
                last_accessed=all_data["metadatas"][i].get("last_accessed", None),
            ).to_dict())
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(memories, f, ensure_ascii=False, indent=2)
        self.logger.debug(f"Dumped {len(memories)} memories to {path}")

    def _load_from_files(self):
        all_data = self.collection.get()
        has_chroma_data = bool(all_data.get("ids"))

        if not has_chroma_data:
            self.logger.info("No existing memory data found, creating new memory store")
            self._bm25_dirty = True
            return

        self.logger.info(f"Restored {len(all_data['ids'])} memories from ChromaDB")
        self._bm25_dirty = True

    @property
    def _cleanup_state_path(self) -> Path:
        return self.memory_dir / "cleanup_state.json"

    def _load_cleanup_state(self) -> dict:
        path = self._cleanup_state_path
        if not path.exists():
            return {"mutation_count": 0, "last_cleanup": None, "last_mutation": None}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            self.logger.warning(f"Failed to read cleanup state file, resetting: {path}")
            return {"mutation_count": 0, "last_cleanup": None, "last_mutation": None}

    def _save_cleanup_state(self, state: dict):
        path = self._cleanup_state_path
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.logger.warning(f"Failed to write cleanup state file: {e}")

    def increment_mutation_count(self, count: int = 1):
        state = self._load_cleanup_state()
        state["mutation_count"] = state.get("mutation_count", 0) + count
        state["last_mutation"] = datetime.now().isoformat()
        self._save_cleanup_state(state)

    def decrement_mutation_count(self, count: int = 1):
        state = self._load_cleanup_state()
        state["mutation_count"] = max(0, state.get("mutation_count", 0) - count)
        self._save_cleanup_state(state)

    def check_and_reset_mutation(self, threshold: int) -> bool:
        if threshold < 0:
            return False
        state = self._load_cleanup_state()
        count = state.get("mutation_count", 0)
        if count >= threshold:
            state["mutation_count"] = 0
            state["last_cleanup"] = datetime.now().isoformat()
            self._save_cleanup_state(state)
            return True
        return False

    async def _add_to_chroma(self, memory: Memory, embedding: list[float] = None):
        if embedding is None:
            embedding = await self.embedding.get_embedding(memory.content)
        self.collection.add(
            ids=[memory.id],
            embeddings=[embedding],
            documents=[memory.content],
            metadatas=[memory.to_metadata()],
        )

    async def _add_batch_to_chroma(self, memories: List[Memory], embeddings: List[List[float]]):
        self.collection.add(
            ids=[m.id for m in memories],
            embeddings=embeddings,
            documents=[m.content for m in memories],
            metadatas=[m.to_metadata() for m in memories],
        )

    def _remove_from_chroma(self, memory_id: str):
        try:
            self.collection.delete(ids=[memory_id])
        except Exception as e:
            self.logger.warning(f"Failed to delete memory from ChromaDB: id={memory_id}, error={e}")

    async def add_memories(self, memories: List[Memory]):
        new_ids = [m.id for m in memories]
        existing = self.collection.get(ids=new_ids)
        existing_ids = set(existing.get("ids", []))

        pending = [m for m in memories if m.id not in existing_ids]
        if not pending:
            self.logger.debug(
                f"All {len(memories)} memories already exist, skipping",
                context={"duplicate_count": len(memories)},
            )
            return

        skipped = len(memories) - len(pending)
        contents = [m.content for m in pending]
        try:
            embeddings = await self.embedding.get_embeddings(contents)
        except Exception as e:
            self.logger.error(f"Failed to get embeddings for {len(contents)} memories: {e}")
            return

        valid_pairs = [(m, e) for m, e in zip(pending, embeddings) if e is not None]
        if len(valid_pairs) < len(pending):
            failed_count = len(pending) - len(valid_pairs)
            self.logger.warning(
                f"Partial embedding: {len(valid_pairs)}/{len(pending)} memories embedded, {failed_count} failed",
            )
        pending = [m for m, _ in valid_pairs]
        embeddings = [e for _, e in valid_pairs]

        await self._add_batch_to_chroma(pending, embeddings)

        self.logger.info(
            f"Added {len(pending)} memories{f', skipped {skipped} duplicates' if skipped else ''}",
            context={"added_count": len(pending), "skipped_duplicates": skipped},
        )
        self._dump_memories_json()
        self.increment_mutation_count(len(pending))
        self._bm25_dirty = True

    def delete_memory(self, memory_id: str):
        doc_data = self.collection.get(ids=[memory_id])
        if not doc_data.get("ids"):
            self.logger.debug(f"Delete memory: id={memory_id} not found, skipping")
            return

        self._remove_from_chroma(memory_id)
        self.logger.info(f"Deleted memory: id={memory_id}")
        self._dump_memories_json()
        self._bm25_dirty = True

    def increment_access(self, memory_id: str):
        data = self.collection.get(ids=[memory_id], include=["metadatas"])
        if not data["metadatas"] or not data["metadatas"][0]:
            return
        metadata = data["metadatas"][0]
        metadata["access_count"] = metadata.get("access_count", 0) + 1
        metadata["last_accessed"] = datetime.now().isoformat()
        self.collection.update(ids=[memory_id], metadatas=[metadata])
        self.logger.debug(
            f"Incremented access count for memory {memory_id[:12]}",
            context={"memory_id_prefix": memory_id[:12]},
        )

    def _ensure_bm25(self):
        if self._bm25_dirty:
            self.build_bm25_index()
            self._bm25_dirty = False

    def build_bm25_index(self):
        all_data = self.collection.get()
        documents = all_data.get("documents", [])

        if not documents:
            self.bm25 = None
            self.doc_mapping = {}
            self.logger.debug("BM25 index is empty (no documents)")
            return

        tokenized_docs = [self._tokenize(doc) for doc in documents]
        self.bm25 = BM25Okapi(tokenized_docs)
        self.doc_mapping = {i: doc_id for i, doc_id in enumerate(all_data["ids"])}
        self.logger.debug(f"BM25 index built: {len(documents)} documents")

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        text = re.sub(r'[^\w\s一-鿿]', ' ', text)
        tokens = []
        for word in text.split():
            tokens.extend(jieba.lcut(word))
        return [t for t in tokens if t.strip()]

    def _bm25_search(self, query: str, n_results: int) -> list[str]:
        self._ensure_bm25()

        if self.bm25 is None:
            return []

        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        doc_scores = [(doc_id, score) for doc_id, score in
                      zip(self.doc_mapping.values(), scores) if score > 0]

        doc_scores.sort(key=lambda x: x[1], reverse=True)

        return [doc_id for doc_id, _ in doc_scores[:n_results]]

    async def hybrid_search(self,
                            query: str,
                            n_results: int = 5,
                            rrf_k: int = 60,
                            vector_weight: float = 0.5,
                            bm25_weight: float = 0.5) -> dict:

        vector_ids = []
        try:
            vector_results = self.collection.query(
                query_embeddings=[await self.embedding.get_embedding(query)],
                n_results=n_results * 3,
            )
            vector_ids = vector_results["ids"][0] if vector_results.get("ids") else []
        except Exception as e:
            self.logger.warning(f"Vector search failed: {e}")

        self._ensure_bm25()
        bm25_ids = self._bm25_search(query, n_results=n_results * 3)

        rrf_scores: dict[str, float] = {}
        for rank, doc_id in enumerate(vector_ids, 1):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + vector_weight / (rrf_k + rank)
        for rank, doc_id in enumerate(bm25_ids, 1):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + bm25_weight / (rrf_k + rank)

        sorted_ids = sorted(rrf_scores.items(), key=lambda x: (-x[1], x[0]))
        top_ids = [doc_id for doc_id, _ in sorted_ids[:n_results]]

        if not top_ids:
            return {"ids": [], "documents": []}

        top_data = self.collection.get(ids=top_ids, include=["documents"])
        id_to_doc = {}
        for i, doc_id in enumerate(top_data.get("ids", [])):
            id_to_doc[doc_id] = top_data["documents"][i]

        results: dict = {"ids": [], "documents": []}
        for doc_id in top_ids:
            self.increment_access(doc_id)
            if doc_id in id_to_doc:
                results["ids"].append(doc_id)
                results["documents"].append(id_to_doc[doc_id])

        self.logger.debug(
            f"Hybrid search returned {len(results['ids'])} results: query={query[:50]}",
            context={
                "result_count": len(results["ids"]),
                "bm25_count": len(bm25_ids),
                "vector_count": len(vector_ids),
                "query_preview": query[:50],
            },
        )
        return results

    @property
    def count(self) -> int:
        return self.collection.count()

    def get_all(self) -> list[dict]:
        all_data = self.collection.get(include=["documents"])
        return [
            {"id": all_data["ids"][i], "content": all_data["documents"][i]}
            for i in range(len(all_data.get("ids", [])))
        ]

    def get_by_ids(self, memory_ids: list[str]) -> list[dict]:
        data = self.collection.get(ids=memory_ids, include=["documents"])
        id_to_doc = dict(zip(data.get("ids", []), data.get("documents", [])))
        result = []
        for mid in memory_ids:
            if mid in id_to_doc:
                result.append({"id": mid, "content": id_to_doc[mid]})
                self.increment_access(mid)
        return result
