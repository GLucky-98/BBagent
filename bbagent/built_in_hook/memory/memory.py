import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import chromadb
import jieba
from rank_bm25 import BM25Okapi

from .embedding import Embedding, OllamaEmbedding


@dataclass
class Memory:
    id: str
    content: str
    session_id: str
    date_created: str
    access_count: int = 0
    last_accessed: str | None = None

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
            last_accessed=data.get("last_accessed"),
        )

    def to_metadata(self) -> dict:
        return {
            "session_id": self.session_id,
            "date_created": self.date_created,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed or "",
        }

    @staticmethod
    def create(content: str, session_id: str, memory_id: str | None = None) -> 'Memory':
        return Memory(
            id=memory_id or "",
            content=content,
            session_id=session_id,
            date_created=datetime.now().isoformat(),
            access_count=0,
            last_accessed=None,
        )


class MemoryManager:

    def __init__(self,
                 name: str = "memories",
                 embedding: Embedding | None = None,
                 memory_dir: str | Path = "./memory",
                 logger: Any | None = None):

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

        self.bm25: Any | None = None
        self.doc_mapping: dict[int, str] = {}
        self._bm25_dirty = True

        self.logger: Any = logger or logging.getLogger(__name__)
        self.logger.info(f"MemoryManager initialized: collection={name}, dir={self.memory_dir}")

        self._next_id = self._compute_next_id()

        self._load_from_files()

    def _compute_next_id(self) -> int:
        all_data = self.collection.get(include=[])
        ids = all_data.get("ids") or []
        if not ids:
            return 1
        numeric_ids = []
        for i in ids:
            try:
                numeric_ids.append(int(i))
            except ValueError:
                continue
        return max(numeric_ids, default=0) + 1

    def _generate_id(self) -> str:
        id_val = self._next_id
        self._next_id += 1
        return str(id_val)

    def _dump_memories_json(self):
        path = self.memory_dir / "memories.json"
        all_data = self.collection.get()
        memories = []
        ids = all_data.get("ids") or []
        documents = all_data.get("documents") or []
        metadatas = all_data.get("metadatas") or []
        for i, doc_id in enumerate(ids):
            metadata = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
            memories.append(Memory(
                id=doc_id,
                content=documents[i] if i < len(documents) else "",
                session_id=str(metadata.get("session_id", "")),
                date_created=str(metadata.get("date_created", "")),
                access_count=int(metadata.get("access_count", 0) or 0),
                last_accessed=str(metadata.get("last_accessed") or "") or None,
            ).to_dict())
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(memories, f, ensure_ascii=False, indent=2)
        self.logger.debug(f"Dumped {len(memories)} memories to {path}")

    def _load_from_files(self):
        all_data = self.collection.get()
        ids = all_data.get("ids") or []
        has_chroma_data = bool(ids)

        if not has_chroma_data:
            self.logger.info("No existing memory data found, creating new memory store")
            self._bm25_dirty = True
            return

        self.logger.info(f"Restored {len(ids)} memories from ChromaDB")
        self._bm25_dirty = True

    @property
    def _cleanup_state_path(self) -> Path:
        return self.memory_dir / "cleanup_state.json"

    def _load_cleanup_state(self) -> dict[str, Any]:
        path = self._cleanup_state_path
        if not path.exists():
            return {"mutation_count": 0, "last_cleanup": None, "last_mutation": None}
        try:
            with open(path, encoding="utf-8") as f:
                return cast(dict[str, Any], json.load(f))
        except (json.JSONDecodeError, OSError):
            self.logger.warning(f"Failed to read cleanup state file, resetting: {path}")
            return {"mutation_count": 0, "last_cleanup": None, "last_mutation": None}

    def _save_cleanup_state(self, state: dict[str, Any]):
        path = self._cleanup_state_path
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.logger.warning(f"Failed to write cleanup state file: {e}")

    def increment_mutation_count(self, count: int = 1):
        state = self._load_cleanup_state()
        state["mutation_count"] = int(state.get("mutation_count", 0) or 0) + count
        state["last_mutation"] = datetime.now().isoformat()
        self._save_cleanup_state(state)

    def decrement_mutation_count(self, count: int = 1):
        state = self._load_cleanup_state()
        state["mutation_count"] = max(0, int(state.get("mutation_count", 0) or 0) - count)
        self._save_cleanup_state(state)

    def check_and_reset_mutation(self, threshold: int) -> bool:
        if threshold < 0:
            return False
        state = self._load_cleanup_state()
        count = int(state.get("mutation_count", 0) or 0)
        if count >= threshold:
            state["mutation_count"] = 0
            state["last_cleanup"] = datetime.now().isoformat()
            self._save_cleanup_state(state)
            return True
        return False

    def get_mutation_count(self) -> int:
        state = self._load_cleanup_state()
        return int(state.get("mutation_count", 0) or 0)

    def should_clean(self, threshold: int) -> bool:
        if threshold < 0:
            return False
        return self.get_mutation_count() >= threshold

    def reset_mutation_count(self):
        state = self._load_cleanup_state()
        state["mutation_count"] = 0
        state["last_cleanup"] = datetime.now().isoformat()
        self._save_cleanup_state(state)

    async def _add_to_chroma(self, memory: Memory, embedding: list[float] | None = None):
        if embedding is None:
            embedding = await self.embedding.get_embedding(memory.content)
        cast(Any, self.collection).add(
            ids=[memory.id],
            embeddings=[embedding],
            documents=[memory.content],
            metadatas=[memory.to_metadata()],
        )

    async def _add_batch_to_chroma(self, memories: list[Memory], embeddings: list[list[float]]):
        cast(Any, self.collection).add(
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

    async def add_memories(self, memories: list[Memory]) -> dict:
        all_data = self.collection.get(include=["documents"])
        existing_contents = set(all_data.get("documents") or [])

        pending = []
        skipped = 0
        for m in memories:
            if m.content in existing_contents:
                skipped += 1
                continue
            if not m.id or not m.id.isdigit():
                m.id = self._generate_id()
            pending.append(m)
            existing_contents.add(m.content)

        if not pending:
            self.logger.debug(
                f"All {len(memories)} memories already exist, skipping",
                context={"duplicate_count": len(memories)},
            )
            return {"added_count": 0, "skipped_duplicates": skipped, "failed_count": 0}
        contents = [m.content for m in pending]
        try:
            embeddings = await self.embedding.get_embeddings(contents)
        except Exception as e:
            self.logger.error(f"Failed to get embeddings for {len(contents)} memories: {e}")
            return {"added_count": 0, "skipped_duplicates": skipped, "failed_count": len(pending)}

        valid_pairs = [(m, e) for m, e in zip(pending, embeddings, strict=False) if e is not None]
        if len(valid_pairs) < len(pending):
            failed_count = len(pending) - len(valid_pairs)
            self.logger.warning(
                f"Partial embedding: {len(valid_pairs)}/{len(pending)} memories embedded, {failed_count} failed",
            )
        else:
            failed_count = 0
        pending = [m for m, _ in valid_pairs]
        embeddings = [e for _, e in valid_pairs]

        if not pending:
            return {"added_count": 0, "skipped_duplicates": skipped, "failed_count": failed_count}

        await self._add_batch_to_chroma(pending, embeddings)

        self.logger.info(
            f"Added {len(pending)} memories{f', skipped {skipped} duplicates' if skipped else ''}",
            context={"added_count": len(pending), "skipped_duplicates": skipped},
        )
        self._dump_memories_json()
        self.increment_mutation_count(len(pending))
        self._bm25_dirty = True
        return {"added_count": len(pending), "skipped_duplicates": skipped, "failed_count": failed_count}

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
        metadatas = data.get("metadatas") or []
        if not metadatas or not metadatas[0]:
            return
        metadata = dict(metadatas[0])
        raw_access_count = metadata.get("access_count", 0)
        if isinstance(raw_access_count, int):
            access_count = raw_access_count
        elif isinstance(raw_access_count, (float, str)):
            access_count = int(raw_access_count)
        else:
            access_count = 0
        metadata["access_count"] = access_count + 1
        metadata["last_accessed"] = datetime.now().isoformat()
        cast(Any, self.collection).update(ids=[memory_id], metadatas=[metadata])
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
        documents = all_data.get("documents") or []

        if not documents:
            self.bm25 = None
            self.doc_mapping = {}
            self.logger.debug("BM25 index is empty (no documents)")
            return

        tokenized_docs = [self._tokenize(doc) for doc in documents]
        self.bm25 = BM25Okapi(tokenized_docs)
        ids = all_data.get("ids") or []
        self.doc_mapping = {i: doc_id for i, doc_id in enumerate(ids)}
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
                      zip(self.doc_mapping.values(), scores, strict=False) if score > 0]

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
            vector_results = cast(Any, self.collection).query(
                query_embeddings=[await self.embedding.get_embedding(query)],
                n_results=n_results * 3,
            )
            vector_rows = vector_results.get("ids") or []
            vector_ids = list(vector_rows[0]) if vector_rows else []
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
        result_ids = top_data.get("ids") or []
        result_documents = top_data.get("documents") or []
        for i, doc_id in enumerate(result_ids):
            if i < len(result_documents):
                id_to_doc[doc_id] = result_documents[i]

        results: dict = {"ids": [], "documents": []}
        for doc_id in top_ids:
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
        return int(self.collection.count())

    def get_all(self) -> list[dict]:
        all_data = self.collection.get(include=["documents"])
        ids = all_data.get("ids") or []
        documents = all_data.get("documents") or []
        return [
            {"id": ids[i], "content": documents[i]}
            for i in range(min(len(ids), len(documents)))
        ]

    def get_by_ids(self, memory_ids: list[str]) -> list[dict]:
        data = self.collection.get(ids=memory_ids, include=["documents"])
        id_to_doc = dict(zip(data.get("ids") or [], data.get("documents") or [], strict=False))
        result = []
        for mid in memory_ids:
            if mid in id_to_doc:
                result.append({"id": mid, "content": id_to_doc[mid]})
        return result
