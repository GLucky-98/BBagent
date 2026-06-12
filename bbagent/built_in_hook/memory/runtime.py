import asyncio
import logging
from collections.abc import Coroutine

from ...core.message import Session
from .fingerprint import extract_seen_memory_keys


class MemoryRuntime:
    """Runtime coordination for one agent's memory subsystem.

    MemoryManager owns storage. This class owns background task lifecycle,
    store access serialization, and extraction/cleanup de-duplication.
    """

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)
        self.store_lock = asyncio.Lock()
        self.jobs: set[asyncio.Task] = set()
        self.inflight_turns: set[tuple[str, int]] = set()
        self.completed_turns: set[tuple[str, int]] = set()
        self.clean_task: asyncio.Task | None = None
        self.seen_memory_keys_by_session: dict[str, set[bytes]] = {}
        self.scanned_turn_count_by_session: dict[str, int] = {}

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

    def get_seen_memory_keys(self, session: Session, inject_prefix: str) -> set[bytes]:
        session_id = session.id
        scanned_turn_count = self.scanned_turn_count_by_session.get(session_id)
        if scanned_turn_count is None or scanned_turn_count > len(session.turns):
            seen = extract_seen_memory_keys(session, inject_prefix)
            self.seen_memory_keys_by_session[session_id] = seen
            self.scanned_turn_count_by_session[session_id] = len(session.turns)
            return seen

        seen = self.seen_memory_keys_by_session.setdefault(session_id, set())
        if scanned_turn_count < len(session.turns):
            partial = Session(id=session.id, turns=session.turns[scanned_turn_count:])
            seen.update(extract_seen_memory_keys(partial, inject_prefix))
            self.scanned_turn_count_by_session[session_id] = len(session.turns)
        return seen

    def mark_memory_keys_seen(self, session_id: str, keys: list[bytes]):
        if not keys:
            return
        self.seen_memory_keys_by_session.setdefault(session_id, set()).update(keys)

    def schedule_clean(self, coro: Coroutine, name: str) -> bool:
        if self.clean_task is not None and not self.clean_task.done():
            self.logger.debug("Memory clean skipped (clean job already running)")
            coro.close()
            return False
        self.clean_task = self.schedule(coro, name)
        return True
