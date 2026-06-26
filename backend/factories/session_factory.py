"""SessionManager — 全局 Session 管理、索引、缓存、Fork 操作.

职责:
  - 启动时扫描所有 agent 的 session 目录构建轻量索引
  - 提供全局 session 列表(按 agent 过滤)
  - 提供单个 session 详情 + turn 摘要
  - 从任意 turn 位置 fork session
  - LRU 缓存避免重复加载 Session 对象
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
    """轻量索引,不包含完整消息数据,仅用于列表展示和路由."""
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
    # 索引构建
    # ------------------------------------------------------------------

    def build_index(self) -> None:
        """启动时调用,扫描所有 agent 的 session 目录构建索引."""
        self._index.clear()
        self._cache.clear()
        for agent_id, agent in self._agent_factory.agents.items():
            self._index_agent(agent_id, agent)
        self._index_built = True
        logger.info("Session index built: %d sessions", len(self._index))

    def _index_agent(self, agent_id: str, agent) -> None:
        """为单个 agent 构建 session 索引."""
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
        """agent 的 session 发生变化后增量刷新该 agent 的索引."""
        agent = self._agent_factory.agents.get(agent_id)
        if not agent:
            return
        # 移除该 agent 的旧索引和缓存
        to_remove = [sid for sid, idx in self._index.items()
                     if idx.agent_id == agent_id]
        for sid in to_remove:
            self._index.pop(sid, None)
            self._cache.pop(sid, None)
        # 重建该 agent 的索引
        self._index_agent(agent_id, agent)

    def _refresh_active_status(self) -> None:
        """刷新所有 agent 的 is_active 状态,并移除已不存在的 session 索引."""
        # 收集每个 agent 的当前 active session id
        active_ids: dict[str, str] = {}
        for agent_id, agent in self._agent_factory.agents.items():
            active_ids[agent_id] = agent.session.id if agent.session else ''

        # 更新 is_active,并检查索引中的 session 目录是否还存在
        stale = []
        for sid, idx in self._index.items():
            idx.is_active = (sid == active_ids.get(idx.agent_id, ''))
            if not Path(idx.session_dir).exists():
                stale.append(sid)
        for sid in stale:
            self._index.pop(sid, None)
            self._cache.pop(sid, None)

    # ------------------------------------------------------------------
    # 列表 & 详情
    # ------------------------------------------------------------------

    def list_sessions(self, agent_id: str | None = None) -> list[dict]:
        """返回 session 列表摘要.刷新 is_active 状态后返回."""
        self._refresh_active_status()
        results = []
        for _sid, idx in self._index.items():
            if agent_id and idx.agent_id != agent_id:
                continue
            results.append(asdict(idx))
        results.sort(key=lambda x: x['timestamp'], reverse=True)
        return results

    async def get_session_detail(self, session_id: str) -> dict:
        """返回 session 详情 + turn 摘要列表."""
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
        """从指定 session 的指定 turn 位置 fork."""
        # 1. 加载源 session
        source = await self._load_session(session_id)
        src_idx = self._index.get(session_id)

        # 2. 确定 fork 目标
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

        # 3. 执行 fork
        new_session = source.fork(session_root=fork_root, at=turn_index)

        # 4. 写入 fork 来源信息
        source_agent_id = src_idx.agent_id if src_idx else None
        if source_agent_id and target_agent_id != source_agent_id:
            for turn in new_session.turns:
                turn.memory_extracted = False

        new_session.parent_session_id = session_id
        new_session.fork_turn_index = turn_index
        new_session.save()

        # 5. 更新索引(新 session 标记为 active)
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

        # 5.1 将该 agent 其他 session 标记为非 active
        for sid, idx in self._index.items():
            if idx.agent_id == target_agent_id and sid != new_session.id:
                idx.is_active = False

        # 6. 加入缓存
        self._cache_put(new_session.id, new_session)

        # 7. 让目标 agent 切换到新 session
        await self._agent_factory.switch_session(target_agent_id, new_session.id)

        return {
            'sessionId': new_session.id,
            'agentId': target_agent_id,
            'turnCount': len(new_session.turns),
            'parentSessionId': session_id,
            'forkTurnIndex': turn_index,
        }

    # ------------------------------------------------------------------
    # 删除
    # ------------------------------------------------------------------

    def delete_session(self, session_id: str) -> bool:
        """删除 session(含文件清理)."""
        idx = self._index.get(session_id)
        if not idx:
            raise NotFoundError(
                ErrorCode.SESSION_NOT_FOUND,
                f"Session '{session_id}' not found",
            )
        # 不允许删除当前活跃 session
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
    # 缓存
    # ------------------------------------------------------------------

    def _load_session_sync(self, session_id: str) -> Session:
        """同步加载 Session(用于非 async 上下文)."""
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
        """带 LRU 缓存的异步加载,用线程池避免阻塞事件循环."""
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
        """放入缓存,超出容量时淘汰最久未访问的非活跃 session."""
        self._cache[session_id] = session
        self._cache.move_to_end(session_id)
        while len(self._cache) > self._cache_capacity:
            # 找到第一个非活跃的 session 淘汰
            evicted = False
            for sid in list(self._cache.keys()):
                si = self._index.get(sid)
                if not (si and si.is_active):
                    del self._cache[sid]
                    evicted = True
                    break
            if not evicted:
                # 全是活跃 session,停止淘汰
                break

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _user_message_preview(turn: Turn) -> str:
        """提取 turn 中第一条 UserMessage 的文本预览."""
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
        """读取 session 元数据(只读顶层 key:value,不解析 turns)."""
        text = md_path.read_text(encoding='utf-8')
        result = {}
        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue  # 跳过空行和标题
            if stripped == '---' or stripped.startswith('## '):
                break  # 遇到分隔线或 turn 标题就停止
            if ':' in stripped:
                key, _, value = stripped.partition(':')
                result[key.strip()] = value.strip()
        return result
