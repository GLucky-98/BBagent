import asyncio
import logging
from typing import Coroutine, Optional


class MemoryRuntime:
    """Runtime coordination for one agent's memory subsystem.

    MemoryManager owns storage. This class owns background task lifecycle,
    store access serialization, and extraction/cleanup de-duplication.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.store_lock = asyncio.Lock()
        self.jobs: set[asyncio.Task] = set()
        self.inflight_turns: set[tuple[str, int]] = set()
        self.completed_turns: set[tuple[str, int]] = set()
        self.clean_task: asyncio.Task | None = None

    def schedule(self, coro: Coroutine, name: str) -> asyncio.Task:
        task = asyncio.create_task(self._run_job(coro, name), name=name)
        self.jobs.add(task)
        task.add_done_callback(self.jobs.discard)
        return task

    async def _run_job(self, coro: Coroutine, name: str):
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.warning(
                f"Memory background job failed: {name}: {e}"
            )

    def claim_turns(self, session_id: str, indexed_turns: list[tuple[int, object]]) -> list[tuple[int, object]]:
        claimed = []
        for idx, turn in indexed_turns:
            key = (session_id, idx)
            if key in self.inflight_turns or key in self.completed_turns:
                continue
            self.inflight_turns.add(key)
            claimed.append((idx, turn))
        return claimed

    def mark_turns_completed(self, session_id: str, indexes: list[int]):
        for idx in indexes:
            self.completed_turns.add((session_id, idx))

    def release_turns(self, session_id: str, indexes: list[int]):
        for idx in indexes:
            self.inflight_turns.discard((session_id, idx))

    def schedule_clean(self, coro: Coroutine, name: str) -> bool:
        if self.clean_task is not None and not self.clean_task.done():
            self.logger.debug("Memory clean skipped (clean job already running)")
            coro.close()
            return False
        self.clean_task = self.schedule(coro, name)
        return True
