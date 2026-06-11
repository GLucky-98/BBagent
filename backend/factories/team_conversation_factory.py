import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from bbagent.core.team import AgentTeam, TeamMessage

from backend.errors import ConflictError, ErrorCode, NotFoundError
from backend.factories import _next_id


class TeamConversationManager:
    """Persist and load Team-level conversations.

    A TeamConversation owns the team message log plus the per-member session
    bindings that make the message log replayable as a coherent team context.
    """

    def __init__(self, agent_factory):
        self._agent_factory = agent_factory

    def ensure_loaded(self, team_id: str, team: AgentTeam) -> dict:
        conversations = self.list_conversations(team)
        if not conversations:
            self._create_default_from_legacy(team)
            conversations = self.list_conversations(team)
        active = next((c for c in conversations if c.get("active")), conversations[0] if conversations else None)
        if active:
            self._set_active(team, active["id"])
            team.load_team_messages(self._messages_path(team, active["id"]))
        return active or {}

    def list_conversations(self, team: AgentTeam) -> list[dict]:
        index = self._read_index(team)
        conversations = index.get("conversations", [])
        changed = False
        result = []
        for item in conversations:
            cid = item.get("id", "")
            meta_path = self._meta_path(team, cid)
            if not cid or not meta_path.exists():
                changed = True
                continue
            meta = self._read_json(meta_path)
            meta["active"] = cid == index.get("activeConversationId")
            meta["messageCount"] = self._message_count(team, cid)
            result.append(meta)
        result.sort(key=lambda c: c.get("updatedAt", 0), reverse=True)
        if changed:
            index["conversations"] = [{"id": c["id"]} for c in result]
            if index.get("activeConversationId") not in {c["id"] for c in result}:
                index["activeConversationId"] = result[0]["id"] if result else ""
            self._write_index(team, index)
        return result

    async def create_conversation(self, team: AgentTeam, name: str | None = None) -> dict:
        self._assert_team_ready(team)
        cid = _next_id()
        now = self._now()
        member_sessions: dict[str, str] = {}
        statuses: dict[str, dict] = {}

        for member_name, agent in team.agents.items():
            current = getattr(agent, "session", None)
            reused = bool(current and len(current.turns) == 0)
            if reused:
                session_id = current.id
                statuses[member_name] = {"status": "reused_empty", "sessionId": session_id}
            else:
                agent_id = self._agent_id_for(agent)
                if not agent_id:
                    raise NotFoundError(ErrorCode.AGENT_NOT_FOUND, f"Agent '{member_name}' not found")
                await self._agent_factory.new_session(agent_id)
                session_id = agent.session.id
                statuses[member_name] = {"status": "created", "sessionId": session_id}
            member_sessions[member_name] = session_id

        meta = {
            "id": cid,
            "name": name or f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "createdAt": now,
            "updatedAt": now,
            "memberSessions": member_sessions,
            "missingSessions": {},
            "messageCount": 0,
        }
        self._conversation_dir(team, cid).mkdir(parents=True, exist_ok=True)
        self._messages_path(team, cid).touch()
        self._write_json(self._meta_path(team, cid), meta)
        self._add_to_index(team, cid)
        self._set_active(team, cid)
        team.load_team_messages(self._messages_path(team, cid))
        return {"conversation": {**meta, "active": True}, "memberSessionStatus": statuses, "warnings": []}

    async def load_conversation(self, team: AgentTeam, conversation_id: str) -> dict:
        self._assert_team_ready(team)
        meta = self._get_meta(team, conversation_id)
        member_sessions = dict(meta.get("memberSessions", {}))
        missing: dict[str, str] = {}
        statuses: dict[str, dict] = {}
        warnings: list[str] = []

        for member_name, agent in team.agents.items():
            agent_id = self._agent_id_for(agent)
            if not agent_id:
                raise NotFoundError(ErrorCode.AGENT_NOT_FOUND, f"Agent '{member_name}' not found")
            session_id = member_sessions.get(member_name)
            if session_id and self._session_exists(agent, session_id):
                await self._agent_factory.switch_session(agent_id, session_id)
                statuses[member_name] = {"status": "loaded", "sessionId": session_id}
            else:
                old_session_id = session_id or ""
                await self._agent_factory.new_session(agent_id)
                new_session_id = agent.session.id
                member_sessions[member_name] = new_session_id
                if old_session_id:
                    missing[member_name] = old_session_id
                    warnings.append(
                        f"Session '{old_session_id}' for member '{member_name}' was missing; created '{new_session_id}'."
                    )
                    statuses[member_name] = {
                        "status": "missing_recreated",
                        "oldSessionId": old_session_id,
                        "sessionId": new_session_id,
                    }
                else:
                    statuses[member_name] = {"status": "created_missing_binding", "sessionId": new_session_id}

        meta["memberSessions"] = member_sessions
        meta["missingSessions"] = missing
        meta["updatedAt"] = self._now()
        self._write_json(self._meta_path(team, conversation_id), meta)
        self._set_active(team, conversation_id)
        team.load_team_messages(self._messages_path(team, conversation_id))
        return {
            "conversation": {**meta, "active": True, "messageCount": self._message_count(team, conversation_id)},
            "messages": [msg.to_dict() for msg in team.get_team_messages()],
            "memberSessionStatus": statuses,
            "warnings": warnings,
        }

    async def delete_conversation(self, team: AgentTeam, conversation_id: str) -> dict:
        self._assert_team_ready(team)
        index = self._read_index(team)
        conversations = [c for c in index.get("conversations", []) if c.get("id") != conversation_id]
        if len(conversations) == len(index.get("conversations", [])):
            raise NotFoundError(ErrorCode.SESSION_NOT_FOUND, f"Conversation '{conversation_id}' not found")

        cdir = self._conversation_dir(team, conversation_id)
        if cdir.exists():
            shutil.rmtree(cdir, ignore_errors=True)
        index["conversations"] = conversations
        was_active = index.get("activeConversationId") == conversation_id
        index["activeConversationId"] = conversations[0]["id"] if was_active and conversations else index.get("activeConversationId", "")
        self._write_index(team, index)

        loaded = None
        if was_active:
            if conversations:
                loaded = await self.load_conversation(team, conversations[0]["id"])
            else:
                loaded = await self.create_conversation(team, "Conversation")
        return {"success": True, "active": loaded}

    def get_active_conversation(self, team: AgentTeam) -> dict | None:
        index = self._read_index(team)
        cid = index.get("activeConversationId")
        if not cid:
            return None
        meta_path = self._meta_path(team, cid)
        if not meta_path.exists():
            return None
        meta = self._read_json(meta_path)
        return {**meta, "active": True, "messageCount": self._message_count(team, cid)}

    def get_messages(self, team: AgentTeam, conversation_id: str | None = None) -> list[dict]:
        if conversation_id:
            path = self._messages_path(team, conversation_id)
            return [msg.to_dict() for msg in self._read_messages(path)]
        return [msg.to_dict() for msg in team.get_team_messages()]

    def record_message(self, team: AgentTeam, msg_dict: dict) -> None:
        active = self.get_active_conversation(team)
        if not active:
            self._create_default_from_legacy(team)
            active = self.get_active_conversation(team)
        if not active:
            return
        cid = active["id"]
        path = self._messages_path(team, cid)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(msg_dict, ensure_ascii=False) + "\n")
        meta = self._get_meta(team, cid)
        meta["updatedAt"] = self._now()
        meta["messageCount"] = self._message_count(team, cid)
        self._write_json(self._meta_path(team, cid), meta)

    def assert_member_session_switch_allowed(self, team: AgentTeam, agent_id: str) -> None:
        team.update_state()
        if str(team.state).lower() == "ready":
            return
        active = self.get_active_conversation(team)
        if not active:
            return
        agent = self._agent_factory.agents.get(agent_id)
        if not agent:
            return
        for member_name, member_agent in team.agents.items():
            if member_agent is agent and active.get("memberSessions", {}).get(member_name):
                raise ConflictError(
                    ErrorCode.TEAM_CONVERSATION_LOCKED,
                    f"Cannot switch session for team member '{member_name}' while team '{team.name}' is running",
                )

    async def align_active_sessions(self, team: AgentTeam) -> dict:
        active = self.get_active_conversation(team)
        if not active:
            created = await self.create_conversation(team, "Conversation")
            return created
        return await self.load_conversation(team, active["id"])

    def _create_default_from_legacy(self, team: AgentTeam) -> dict:
        cid = _next_id()
        now = self._now()
        self._conversation_dir(team, cid).mkdir(parents=True, exist_ok=True)
        legacy = team.base_dir / "team_messages.jsonl" if team.base_dir else None
        messages_path = self._messages_path(team, cid)
        if legacy and legacy.exists():
            shutil.copyfile(legacy, messages_path)
        else:
            messages_path.touch()
        meta = {
            "id": cid,
            "name": "Conversation",
            "createdAt": now,
            "updatedAt": now,
            "memberSessions": {
                name: agent.session.id
                for name, agent in team.agents.items()
                if getattr(agent, "session", None)
            },
            "missingSessions": {},
            "messageCount": self._message_count(team, cid),
        }
        self._write_json(self._meta_path(team, cid), meta)
        self._write_index(team, {"activeConversationId": cid, "conversations": [{"id": cid}]})
        return meta

    def _assert_team_ready(self, team: AgentTeam) -> None:
        team.update_state()
        if str(team.state).lower() != "ready":
            raise ConflictError(
                ErrorCode.TEAM_CONVERSATION_LOCKED,
                f"Cannot change team conversation while team '{team.name}' is not ready",
            )

    def _agent_id_for(self, agent) -> str | None:
        for aid, candidate in self._agent_factory.agents.items():
            if candidate is agent:
                return aid
        return None

    @staticmethod
    def _session_exists(agent, session_id: str) -> bool:
        return bool(session_id) and (agent.session_dir / session_id / f"{session_id}.jsonl").exists()

    def _read_messages(self, path: Path) -> list[TeamMessage]:
        if not path.exists():
            return []
        messages = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(TeamMessage.from_dict(json.loads(line)))
        return messages

    def _message_count(self, team: AgentTeam, conversation_id: str) -> int:
        path = self._messages_path(team, conversation_id)
        if not path.exists():
            return 0
        with open(path, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def _get_meta(self, team: AgentTeam, conversation_id: str) -> dict:
        path = self._meta_path(team, conversation_id)
        if not path.exists():
            raise NotFoundError(ErrorCode.SESSION_NOT_FOUND, f"Conversation '{conversation_id}' not found")
        return self._read_json(path)

    def _add_to_index(self, team: AgentTeam, conversation_id: str) -> None:
        index = self._read_index(team)
        ids = {item.get("id") for item in index.get("conversations", [])}
        if conversation_id not in ids:
            index.setdefault("conversations", []).insert(0, {"id": conversation_id})
        self._write_index(team, index)

    def _set_active(self, team: AgentTeam, conversation_id: str) -> None:
        index = self._read_index(team)
        if conversation_id not in {item.get("id") for item in index.get("conversations", [])}:
            index.setdefault("conversations", []).insert(0, {"id": conversation_id})
        index["activeConversationId"] = conversation_id
        self._write_index(team, index)

    def _read_index(self, team: AgentTeam) -> dict:
        path = self._index_path(team)
        if not path.exists():
            return {"activeConversationId": "", "conversations": []}
        return self._read_json(path)

    def _write_index(self, team: AgentTeam, index: dict) -> None:
        path = self._index_path(team)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(path, index)

    @staticmethod
    def _read_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _index_path(self, team: AgentTeam) -> Path:
        return self._root(team) / "index.json"

    def _meta_path(self, team: AgentTeam, conversation_id: str) -> Path:
        return self._conversation_dir(team, conversation_id) / "meta.json"

    def _messages_path(self, team: AgentTeam, conversation_id: str) -> Path:
        return self._conversation_dir(team, conversation_id) / "messages.jsonl"

    def _conversation_dir(self, team: AgentTeam, conversation_id: str) -> Path:
        return self._root(team) / conversation_id

    @staticmethod
    def _root(team: AgentTeam) -> Path:
        if not team.base_dir:
            raise ValueError("Team base_dir is not set")
        return team.base_dir / "team_conversations"

    @staticmethod
    def _now() -> int:
        return int(datetime.now().timestamp())
