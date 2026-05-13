import asyncio
import logging
import aiohttp
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class Embedding(ABC):
    @abstractmethod
    async def get_embedding(self, text: str, **kwargs) -> list[float]:
        pass


class OllamaEmbedding(Embedding):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text",
                 max_retries: int = 3, retry_delay: float = 1.0, request_timeout: float = 60.0):
        self.base_url = base_url
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.request_timeout = request_timeout

    async def get_embedding(self, text: str, truncate: bool = True, **kwargs) -> list[float]:
        embeddings, _ = await self._embed_with_retry([text], truncate, **kwargs)
        return embeddings[0]

    async def get_embeddings(self, texts: list[str], truncate: bool = True) -> list[list[float]]:
        embeddings, _ = await self._embed_with_retry(texts, truncate)
        return embeddings

    async def _embed_with_retry(self, texts: list[str], truncate: bool = True, **kwargs) -> tuple[list[list[float]], dict]:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await self._do_embed_request(texts, truncate, **kwargs)
            except ValueError as e:
                last_error = e
                if "NaN" in str(e):
                    break
            except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, KeyError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
            except Exception as e:
                last_error = e
                break

        if isinstance(last_error, ValueError) and "NaN" in str(last_error) and len(texts) > 1:
            logger.warning(
                "Batch embedding failed with NaN (%d texts, model=%s). "
                "Falling back to individual requests.",
                len(texts), self.model,
            )
            return await self._embed_individually(texts, truncate, **kwargs)

        error_type = type(last_error).__name__ if last_error else "Unknown"
        raise RuntimeError(
            f"Embedding request failed ({self.model}@{self.base_url}), "
            f"retried {self.max_retries} times. "
            f"last error [{error_type}]: {last_error}"
        )

    async def _embed_individually(self, texts: list[str], truncate: bool = True, **kwargs) -> tuple[list[list[float]], dict]:
        embeddings = [None] * len(texts)
        failed_indices = []
        for i, text in enumerate(texts):
            for attempt in range(self.max_retries):
                try:
                    result, meta = await self._do_embed_request([text], truncate, **kwargs)
                    embeddings[i] = result[0]
                    break
                except ValueError as e:
                    if "NaN" in str(e):
                        failed_indices.append(i)
                        logger.warning(
                            "Text [%d] embedding produced NaN (model=%s), skipping. "
                            "Text preview: %.100s...",
                            i, self.model, text,
                        )
                        break
                    raise
                except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                    else:
                        failed_indices.append(i)
                        logger.error(
                            "Text [%d] embedding failed after %d retries: %s. Skipping.",
                            i, self.max_retries, e,
                        )
                        break

        success_count = sum(1 for e in embeddings if e is not None)
        if failed_indices:
            logger.warning(
                "Individual embedding completed: %d/%d succeeded, %d failed (indices: %s)",
                success_count, len(texts), len(failed_indices), failed_indices,
            )
        if success_count == 0:
            raise RuntimeError(
                f"All {len(texts)} texts failed to embed (model={self.model}). "
                f"Failed indices: {failed_indices}"
            )
        return embeddings, {}

    async def _do_embed_request(self, texts: list[str], truncate: bool = True, **kwargs) -> tuple[list[list[float]], dict]:
        url = f"{self.base_url}/api/embed"
        payload = {
            "model": self.model,
            "input": texts,
            "truncate": truncate
        }
        payload.update(kwargs)

        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.post(url, json=payload) as response:
                    if response.status >= 500:
                        body = await response.text()
                        if "NaN" in body:
                            raise ValueError(
                                f"Ollama embedding produced NaN for model={self.model}"
                            )
                    response.raise_for_status()
                    data = await response.json()
                    if "embeddings" not in data:
                        raise ValueError(
                            f"Ollama response missing 'embeddings' field, "
                            f"available fields: {list(data.keys())}"
                        )
                    return data["embeddings"], data
            except aiohttp.ClientError as e:
                raise ConnectionError(f"Failed to connect to Ollama at {self.base_url}: {e}") from e
            except asyncio.TimeoutError:
                raise TimeoutError(f"Request to Ollama timed out after {self.request_timeout}s")


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
