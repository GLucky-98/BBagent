import asyncio
import logging
from abc import ABC, abstractmethod

import ollama
from ollama import AsyncClient

logger = logging.getLogger(__name__)


class Embedding(ABC):
    @abstractmethod
    async def get_embedding(self, text: str, **kwargs) -> list[float]:
        pass


class OllamaEmbedding(Embedding):
    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model
        self._client = AsyncClient()

    async def get_embedding(self, text: str, truncate: bool = True, **kwargs) -> list[float]:
        embeddings = await self.get_embeddings([text], truncate)
        return embeddings[0]

    async def get_embeddings(self, texts: list[str], truncate: bool = True) -> list[list[float]]:
        try:
            return await self._batch_embed(texts, truncate)
        except Exception:
            logger.warning(
                f"Batch embedding failed ({len(texts)} texts, model={self.model}). Falling back to individual requests.",
            )
            return await self._embed_individually(texts, truncate)

    async def _batch_embed(self, texts: list[str], truncate: bool = True) -> list[list[float]]:
        last_error = None
        for attempt in range(3):
            try:
                response = await self._client.embed(
                    model=self.model,
                    input=texts,
                    truncate=truncate,
                )
                return response.embeddings
            except ollama.ResponseError:
                raise
            except Exception as e:
                last_error = e
                if attempt < 2:
                    await asyncio.sleep(1.0 * (2 ** attempt))

        raise RuntimeError(
            f"Batch embedding failed after 3 retries (model={self.model}): {last_error}"
        ) from last_error

    async def _embed_individually(self, texts: list[str], truncate: bool = True) -> list[list[float]]:
        embeddings = [None] * len(texts)
        failed_indices = []

        for i, text in enumerate(texts):
            for attempt in range(3):
                try:
                    response = await self._client.embed(
                        model=self.model,
                        input=[text],
                        truncate=truncate,
                    )
                    embeddings[i] = response.embeddings[0]
                    break
                except Exception:
                    if attempt < 2:
                        await asyncio.sleep(1.0 * (2 ** attempt))
                    else:
                        failed_indices.append(i)
                        logger.warning(
                            f"Text [{i}] embedding failed after 3 retries (model={self.model}), skipping. "
                            f"Text preview: {text[:100]}...",
                        )

        success_count = sum(1 for e in embeddings if e is not None)
        if failed_indices:
            logger.warning(
                f"Individual embedding completed: {success_count}/{len(texts)} succeeded, "
                f"{len(failed_indices)} failed (indices: {failed_indices})",
            )
        if success_count == 0:
            raise RuntimeError(
                f"All {len(texts)} texts failed to embed (model={self.model}). "
                f"Failed indices: {failed_indices}"
            )
        return [e for e in embeddings if e is not None]


if __name__ == "__main__":
    async def main():
        embedder = OllamaEmbedding()
        embeddings = await embedder.get_embeddings([
            "Why is the sky blue?",
            "Why is the grass green?"
        ])
        for i, emb in enumerate(embeddings):
            print(f"Text {i+1}: dims={len(emb)}, first5={emb[:5]}")
    asyncio.run(main())
