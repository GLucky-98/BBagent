import asyncio
import aiohttp
from abc import ABC, abstractmethod

class Embedding(ABC):
    @abstractmethod
    async def get_embedding(self, text: str, **kwargs) -> list[float]:
        pass

class OllamaEmbedding(Embedding):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "bge-m3",
                 max_retries: int = 3, retry_delay: float = 1.0, request_timeout: float = 60.0):
        self.base_url = base_url
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.request_timeout = request_timeout

    async def get_embedding(self, text: str, truncate: bool = True, **kwargs) -> list[float]:
        return await self._embed_with_retry(text, truncate, **kwargs)

    async def get_embeddings(self, texts: list[str], truncate: bool = True) -> list[list[float]]:
        tasks = [self._embed_with_retry(text, truncate) for text in texts]
        return await asyncio.gather(*tasks)

    async def _embed_with_retry(self, text: str, truncate: bool = True, **kwargs) -> list[float]:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await self._do_embed_request(text, truncate, **kwargs)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
            except Exception as e:
                last_error = e
                break

        error_type = type(last_error).__name__ if last_error else "Unknown"
        raise RuntimeError(
            f"embedding 请求失败（{self.model}@{self.base_url}），"
            f"已重试 {self.max_retries} 次。"
            f"最后错误 [{error_type}]: {last_error}"
        )

    async def _do_embed_request(self, text: str, truncate: bool = True, **kwargs) -> list[float]:
        url = f"{self.base_url}/api/embeddings"
        payload = {
            "model": self.model,
            "prompt": text,
            "truncate": truncate
        }
        payload.update(kwargs)

        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                if "embedding" not in data:
                    raise ValueError(
                        f"Ollama 响应缺少 'embedding' 字段，"
                        f"可用字段: {list(data.keys())}"
                    )
                return data["embedding"]


if __name__ == "__main__":
    async def main():
        embedder = OllamaEmbedding()
        emb = await embedder.get_embedding("你好")
        print(len(emb))
        print(emb[:5])
    asyncio.run(main())
