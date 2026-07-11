import asyncio
import contextlib
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.logging import get_backend_logger
from backend.state import state_manager

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:  # pragma: no cover - exercised only without optional web deps
    FileSystemEvent = object  # type: ignore[misc,assignment]
    FileSystemEventHandler = object  # type: ignore[misc,assignment]
    Observer = None  # type: ignore[assignment]

logger = get_backend_logger("api.file_watch")
router = APIRouter()

DEBOUNCE_SECONDS = 0.5
_STOP = object()

IGNORED_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".DS_Store",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
}
IGNORED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".swp",
    ".tmp",
    ".temp",
}
IGNORED_EVENT_TYPES = {"opened", "closed", "closed_no_write"}


def _resolve_path(path: str | Path | None) -> Path | None:
    if not path:
        return None
    try:
        return Path(path).expanduser().resolve()
    except OSError:
        return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _should_ignore(path: Path) -> bool:
    if any(part in IGNORED_NAMES for part in path.parts):
        return True
    if path.name.startswith(".") and path.name not in {".env", ".env.example"}:
        return True
    return path.suffix in IGNORED_SUFFIXES


def _roots_for_agent(agent_id: str) -> list[dict[str, str]]:
    roots: list[dict[str, str]] = []

    agent = state_manager.agent_factory.agents.get(agent_id)
    if agent is not None:
        policy = dict(getattr(agent, "policy", {}) or {})
        working_dir = _resolve_path(policy.get("cwd") or getattr(agent, "base_dir", None))
        base_dir = _resolve_path(getattr(agent, "base_dir", None))
    else:
        team_config = state_manager.team_factory.get_config(agent_id)
        if team_config is None:
            return []
        working_dir = _resolve_path(team_config.workingDir)
        base_dir = _resolve_path(team_config.baseDir)

    if working_dir and working_dir.exists() and working_dir.is_dir():
        roots.append({"scope": "workingDir", "path": str(working_dir)})
    if base_dir and base_dir.exists() and base_dir.is_dir():
        roots.append({"scope": "baseDir", "path": str(base_dir)})
    return roots


def _dedupe_roots(roots: list[dict[str, str]]) -> list[dict[str, str]]:
    by_path: dict[str, set[str]] = {}
    for root in roots:
        path = root["path"]
        by_path.setdefault(path, set()).add(root["scope"])
    return [
        {"path": path, "scope": ",".join(sorted(scopes))}
        for path, scopes in by_path.items()
    ]


class _WatchHandler(FileSystemEventHandler):  # type: ignore[misc]
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue,
        roots: list[dict[str, str]],
    ):
        self._loop = loop
        self._queue = queue
        self._roots = [(root["scope"].split(","), Path(root["path"])) for root in roots]

    def on_any_event(self, event: FileSystemEvent) -> None:
        event_type = getattr(event, "event_type", "")
        if event_type in IGNORED_EVENT_TYPES:
            return

        paths = [Path(str(getattr(event, "src_path", "")))]
        dest_path = getattr(event, "dest_path", None)
        if dest_path:
            paths.append(Path(str(dest_path)))

        scopes: set[str] = set()
        changed_paths: set[str] = set()
        for raw_path in paths:
            path = _resolve_path(raw_path)
            if path is None or _should_ignore(path):
                continue
            for root_scopes, root_path in self._roots:
                if _is_relative_to(path, root_path):
                    scopes.update(root_scopes)
                    changed_paths.add(str(path))

        if not scopes or not changed_paths:
            return

        payload = {
            "event_type": event_type,
            "scopes": sorted(scopes),
            "paths": sorted(changed_paths),
        }
        with contextlib.suppress(RuntimeError):
            self._loop.call_soon_threadsafe(self._queue.put_nowait, payload)


class _WatchSession:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.queue: asyncio.Queue = asyncio.Queue()
        self.observer: Any | None = None
        self.forwarder_task: asyncio.Task | None = None
        self.session_id = f"file_ws:{uuid4().hex[:8]}"

    async def watch_agent(self, agent_id: str) -> None:
        await self.stop()
        roots = _dedupe_roots(_roots_for_agent(agent_id))
        if not roots:
            await self.websocket.send_json({
                "type": "file_watch_stopped",
                "agent_id": agent_id,
                "reason": "no_watchable_roots",
            })
            return
        if Observer is None:
            await self.websocket.send_json({
                "type": "file_watch_unavailable",
                "agent_id": agent_id,
                "reason": "watchdog is not installed",
            })
            return

        loop = asyncio.get_running_loop()
        handler = _WatchHandler(loop, self.queue, roots)
        observer = Observer()
        scheduled = 0
        for root in roots:
            try:
                observer.schedule(handler, root["path"], recursive=True)
                scheduled += 1
            except OSError as e:
                logger.warning("Failed to watch '%s': %s", root["path"], e)

        if scheduled == 0:
            await self.websocket.send_json({
                "type": "file_watch_stopped",
                "agent_id": agent_id,
                "reason": "schedule_failed",
            })
            return

        observer.start()
        self.observer = observer
        self.forwarder_task = asyncio.create_task(self._forward_changes(agent_id, roots))
        await self.websocket.send_json({
            "type": "file_watch_started",
            "agent_id": agent_id,
            "roots": roots,
        })
        logger.info("%s watching %d root(s) for '%s'", self.session_id, scheduled, agent_id)

    async def _forward_changes(self, agent_id: str, roots: list[dict[str, str]]) -> None:
        while True:
            item = await self.queue.get()
            if item is _STOP:
                return

            scopes = set(item["scopes"])
            paths = set(item["paths"])
            event_types = {item["event_type"]}
            deadline = asyncio.get_running_loop().time() + DEBOUNCE_SECONDS
            while True:
                timeout = deadline - asyncio.get_running_loop().time()
                if timeout <= 0:
                    break
                try:
                    next_item = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    break
                if next_item is _STOP:
                    return
                scopes.update(next_item["scopes"])
                paths.update(next_item["paths"])
                event_types.add(next_item["event_type"])

            await self.websocket.send_json({
                "type": "file_tree_changed",
                "agent_id": agent_id,
                "scopes": sorted(scopes),
                "paths": sorted(paths),
                "event_types": sorted(event_types),
                "roots": roots,
            })

    async def stop(self) -> None:
        if self.observer is not None:
            observer = self.observer
            self.observer = None
            observer.stop()
            observer.join(timeout=1)
        if self.forwarder_task is not None:
            self.queue.put_nowait(_STOP)
            task = self.forwarder_task
            self.forwarder_task = None
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break


@router.websocket("/files")
async def files_ws(websocket: WebSocket):
    await websocket.accept()
    session = _WatchSession(websocket)

    try:
        async for msg in websocket.iter_json():
            msg_type = msg.get("type")
            if msg_type == "watch_files":
                agent_id = msg.get("agent_id")
                if agent_id:
                    await session.watch_agent(agent_id)
                else:
                    await session.stop()
    except WebSocketDisconnect:
        pass
    finally:
        await session.stop()
