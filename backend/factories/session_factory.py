"""SessionManager — global Session management, indexing, caching, Fork operations.

Responsibilities:
  - On startup, scan all agent's session directories to build lightweight indexes
  - Provide global session list (filter by agent)
  - Provide single session detail + turn summary
  - Fork session from any turn position
  - LRU cache to avoid repeatedly loading Session objects
"""

import asyncio
import shutil
from collections import OrderedDict
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.errors import ConflictError, ErrorCode, NotFoundError
from backend.logging import get_backend_logger
from bbagent.core.message import HumanMessage, Message, Session, Turn

logger = get_backend_logger("state.session_factory")


@dataclass
class SessionIndex:
    """Lightweight index, does not contain full message data, only for list display and routing."""
    session_id: str
    agent_id: str
    agent_name: str
    timestamp: str
    turn_count: int
    is_active: bool
    parent_session_id: str
    fork_turn_index: int
    session_dir: str


class SessionManager:
    def __init__(self, agent_factory):
        self._agent_factory = agent_factory
        self._index: dict[str, SessionIndex] = {}
        self._cache: OrderedDict[str, Session] = OrderedDict()
        self._cache_capacity = 20
        self._index_built = False

    # ------------------------------------------------------------------
    # index building
    # ------------------------------------------------------------------

    def build_index(self) -> None:
        """Called on startup, scans all agent session directories to build index."""
        self._index.clear()
        self._cache.clear()
        for agent_id, agent in self._agent_factory.agents.items():
            self._index_agent(agent_id, agent)
        self._index_built = True
        logger.info("Session index built: %d sessions", len(self._index))

    def _index_agent(self, agent_id: str, agent) -> None:
        """Build session index for a single agent."""
        agent_name = agent.name
        session_dir = agent.session_dir
        if not session_dir or not session_dir.exists():
            return
        active_session_id = agent.session.id if agent.session else ''
        for sdir in sorted(session_dir.iterdir(), reverse=True):
            if not sdir.is_dir():
                continue
            sid = sdir.name
            jsonl_path = sdir / f'{sid}.jsonl'
            if not jsonl_path.exists():
                continue
            md_path = sdir / f'{sid}.md'
            meta = self._parse_md(md_path) if md_path.exists() else {}
            self._index[sid] = SessionIndex(
                session_id=sid,
                agent_id=agent_id,
                agent_name=agent_name,
                timestamp=meta.get('timestamp', ''),
                turn_count=int(meta.get('turn_count', 0)),
                is_active=(sid == active_session_id),
                parent_session_id=meta.get('parent_session_id', ''),
                fork_turn_index=int(meta.get('fork_turn_index', -1)) if meta.get('fork_turn_index', '') != '' else -1,
                session_dir=str(sdir),
            )

    def refresh_agent_index(self, agent_id: str) -> None:
        """Incrementally refresh this agent's index after its sessions change."""
        agent = self._agent_factory.agents.get(agent_id)
        if not agent:
            return
        # remove this agent's old index and cache
        to_remove = [sid for sid, idx in self._index.items()
                     if idx.agent_id == agent_id]
        for sid in to_remove:
            self._index.pop(sid, None)
            self._cache.pop(sid, None)
        # rebuild this agent's index
        self._index_agent(agent_id, agent)

    def _refresh_active_status(self) -> None:
        """Refresh is_active status for all agents and remove indexes for non-existent sessions."""
        # collect each agent's current active session id
        active_ids: dict[str, str] = {}
        for agent_id, agent in self._agent_factory.agents.items():
            active_ids[agent_id] = agent.session.id if agent.session else ''

        # update is_active and check whether session dirs in index still exist
        stale = []
        for sid, idx in self._index.items():
            idx.is_active = (sid == active_ids.get(idx.agent_id, ''))
            if not Path(idx.session_dir).exists():
                stale.append(sid)
        for sid in stale:
            self._index.pop(sid, None)
            self._cache.pop(sid, None)

    # ------------------------------------------------------------------
    # list & detail
    # ------------------------------------------------------------------

    def list_sessions(self, agent_id: str | None = None) -> list[dict]:
        """Return session list summary. Refreshes is_active status before returning."""
        self._refresh_active_status()
        results = []
        for _sid, idx in self._index.items():
            if agent_id and idx.agent_id != agent_id:
                continue
            results.append(asdict(idx))
        results.sort(key=lambda x: x['timestamp'], reverse=True)
        return results

    async def get_session_detail(self, session_id: str) -> dict:
        """Return session detail + turn summary list."""
        idx = self._index.get(session_id)
        if not idx:
            raise NotFoundError(
                ErrorCode.SESSION_NOT_FOUND,
                f"Session '{session_id}' not found",
            )
        session = await self._load_session(session_id)
        turns = []
        for i, turn in enumerate(session.turns):
            if not turn.is_complete:
                continue
            turns.append({
                'index': i,
                'userMessage': self._user_message_preview(turn),
                'tokenCount': turn.token_count,
                'everUsedTools': list(turn.ever_used_tools),
                'startTimestamp': turn.start_timestamp,
                'endTimestamp': turn.end_timestamp,
                'messageCount': len(turn.messages),
            })
        return {
            'sessionId': session.id,
            'agentId': idx.agent_id,
            'agentName': idx.agent_name,
            'timestamp': session.timestamp,
            'turnCount': len(session.turns),
            'parentSessionId': session.parent_session_id,
            'forkTurnIndex': session.fork_turn_index,
            'turns': turns,
        }

    # ------------------------------------------------------------------
    # Fork
    # ------------------------------------------------------------------

    async def fork_at_turn(self, session_id: str, turn_index: int,
                           target_agent_id: str | None = None) -> dict:
        """Fork from a specific turn position of a given session."""
        # 1. load source session
        source = await self._load_session(session_id)
        src_idx = self._index.get(session_id)

        # 2. determine fork target
        if target_agent_id:
            agent = self._agent_factory.agents.get(target_agent_id)
            if not agent:
                raise NotFoundError(
                    ErrorCode.AGENT_NOT_FOUND,
                    f"Agent '{target_agent_id}' not found",
                )
            fork_root = agent.session_dir
            target_agent_name = agent.name
        elif src_idx:
            target_agent_id = src_idx.agent_id
            target_agent_name = src_idx.agent_name
            agent = self._agent_factory.agents.get(target_agent_id)
            fork_root = agent.session_dir if agent else None
            if not fork_root:
                raise NotFoundError(
                    ErrorCode.AGENT_NOT_FOUND,
                    f"Agent '{target_agent_id}' not found for fork target",
                )
        else:
            raise NotFoundError(
                ErrorCode.SESSION_NOT_FOUND,
                f"Session '{session_id}' not found in index",
            )

        # 3. perform fork
        new_session = source.fork(session_root=fork_root, at=turn_index)

        # 4. write fork source info
        source_agent_id = src_idx.agent_id if src_idx else None
        if source_agent_id and target_agent_id != source_agent_id:
            for turn in new_session.turns:
                turn.memory_extracted = False

        new_session.parent_session_id = session_id
        new_session.fork_turn_index = turn_index
        new_session.save()

        # 5. update index (mark new session as active)
        self._index[new_session.id] = SessionIndex(
            session_id=new_session.id,
            agent_id=target_agent_id,
            agent_name=target_agent_name,
            timestamp=new_session.timestamp,
            turn_count=len(new_session.turns),
            is_active=True,
            parent_session_id=session_id,
            fork_turn_index=turn_index,
            session_dir=str(new_session.dir),
        )

        # 5.1 mark this agent's other sessions as non-active
        for sid, idx in self._index.items():
            if idx.agent_id == target_agent_id and sid != new_session.id:
                idx.is_active = False

        # 6. add to cache
        self._cache_put(new_session.id, new_session)

        # 7. switch target agent to new session
        await self._agent_factory.switch_session(target_agent_id, new_session.id)

        return {
            'sessionId': new_session.id,
            'agentId': target_agent_id,
            'turnCount': len(new_session.turns),
            'parentSessionId': session_id,
            'forkTurnIndex': turn_index,
        }

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    def delete_session(self, session_id: str) -> bool:
        """Delete session (including file cleanup)."""
        idx = self._index.get(session_id)
        if not idx:
            raise NotFoundError(
                ErrorCode.SESSION_NOT_FOUND,
                f"Session '{session_id}' not found",
            )
        # disallow deleting the currently active session
        if idx.is_active:
            raise ConflictError(
                ErrorCode.SESSION_SWITCH_FAILED,
                f"Cannot delete active session '{session_id}', switch to another first",
            )
        session_dir = Path(idx.session_dir)
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)
        self._index.pop(session_id, None)
        self._cache.pop(session_id, None)
        return True

    # ------------------------------------------------------------------
    # cache
    # ------------------------------------------------------------------

    def _load_session_sync(self, session_id: str) -> Session:
        """Synchronously load Session (for non-async contexts)."""
        if session_id in self._cache:
            self._cache.move_to_end(session_id)
            return self._cache[session_id]
        idx = self._index.get(session_id)
        if not idx:
            raise NotFoundError(
                ErrorCode.SESSION_NOT_FOUND,
                f"Session '{session_id}' not found",
            )
        session = Session.load(session_id, Path(idx.session_dir))
        self._cache_put(session_id, session)
        return session

    async def _load_session(self, session_id: str) -> Session:
        """Async load with LRU cache, uses thread pool to avoid blocking the event loop."""
        if session_id in self._cache:
            self._cache.move_to_end(session_id)
            return self._cache[session_id]
        idx = self._index.get(session_id)
        if not idx:
            raise NotFoundError(
                ErrorCode.SESSION_NOT_FOUND,
                f"Session '{session_id}' not found",
            )
        loop = asyncio.get_running_loop()
        session = await loop.run_in_executor(
            None,
            Session.load,
            session_id,
            Path(idx.session_dir),
        )
        self._cache_put(session_id, session)
        return session

    def _cache_put(self, session_id: str, session: Session) -> None:
        """Put into cache, evict least-recently-used non-active session when over capacity."""
        self._cache[session_id] = session
        self._cache.move_to_end(session_id)
        while len(self._cache) > self._cache_capacity:
            # find the first non-active session to evict
            evicted = False
            for sid in list(self._cache.keys()):
                si = self._index.get(sid)
                if not (si and si.is_active):
                    del self._cache[sid]
                    evicted = True
                    break
            if not evicted:
                # all sessions are active, stop eviction
                break

    # ------------------------------------------------------------------
    # helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _user_message_preview(turn: Turn) -> str:
        """Extract text preview of the first UserMessage in the turn."""
        for msg in turn.messages:
            if isinstance(msg, HumanMessage):
                return SessionManager._extract_text(msg)[:120]
        return '(no user message)'

    @staticmethod
    def _extract_text(msg: Message) -> str:
        if isinstance(msg.content, str):
            return msg.content
        parts = [b.text for b in msg.content if hasattr(b, 'text') and b.text]
        return ' '.join(parts)

    @staticmethod
    def _parse_md(md_path: Path) -> dict:
        """Read session metadata (only reads top-level key:value, does not parse turns)."""
        text = md_path.read_text(encoding='utf-8')
        result = {}
        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue  # skip blank lines and title
            if stripped == '---' or stripped.startswith('## '):
                break  # stop at separator lines or turn titles
            if ':' in stripped:
                key, _, value = stripped.partition(':')
                result[key.strip()] = value.strip()
        return result
