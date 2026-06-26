"""TeamFactory — manages TeamConfig CRUD and AgentTeam lifecycle.

TeamConfig now stores memberIds (list of agent_id strings) instead of
nested AgentConfig objects. Agent creation is delegated to AgentFactory.
"""

import asyncio
import contextlib
import json
import shutil
from pathlib import Path

from backend.dispatcher import AgentOutputDispatcher
from backend.factories import _next_id
from backend.factories.team_conversation_factory import TeamConversationManager
from backend.logging import get_backend_logger
from backend.schemas import AgentConfig, TeamConfig
from bbagent.core.agent import Agent
from bbagent.core.team import AgentTeam
from bbagent.core.team import TeamConfig as CoreTeamConfig

logger = get_backend_logger("state.team_factory")


class TeamFactory:
    def __init__(self, data_dir: Path, agent_factory):
        self._data_dir = data_dir
        self._agent_factory = agent_factory
        self.teams: dict[str, AgentTeam] = {}  # team_id -> AgentTeam
        self._team_meta: dict[str, dict] = {}  # team_id -> persisted config dict
        self._started: set[str] = set()  # team_ids that have been started
        self._dispatchers: dict[str, AgentOutputDispatcher] = {}
        self.conversations = TeamConversationManager(agent_factory)

    # ------------------------------------------------------------------
    # Dispatchers
    # ------------------------------------------------------------------

    def _ensure_dispatcher(self, team_id: str) -> AgentOutputDispatcher:
        dispatcher = self._dispatchers.get(team_id)
        if dispatcher is None:
            dispatcher = AgentOutputDispatcher(replay_buffer=False)
            self._dispatchers[team_id] = dispatcher
        return dispatcher

    @staticmethod
    def _team_message_payload(msg_dict: dict) -> dict:
        data = dict(msg_dict)
        inner_type = data.pop("type", None)
        payload = {"type": "team_message", **data}
        if inner_type is not None:
            payload["msg_type"] = inner_type
        return payload

    def _wire_team_dispatcher(self, team_id: str, team: AgentTeam) -> None:
        dispatcher = self._ensure_dispatcher(team_id)

        async def on_team_message(msg_dict: dict):
            self.conversations.record_message(team, msg_dict)
            await dispatcher.on_chunk(self._team_message_payload(msg_dict))

        team._on_team_message = on_team_message

    def get_dispatcher(self, team_id: str) -> AgentOutputDispatcher | None:
        if team_id not in self.teams:
            return None
        return self._ensure_dispatcher(team_id)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    async def load(self):
        teams_dir = self._data_dir / "teams"
        if not teams_dir.exists():
            return

        dirs: list[tuple[Path, Path]] = []  # (team_dir, config_path)
        for id_dir in sorted(teams_dir.iterdir()):
            if not id_dir.is_dir():
                continue
            for name_dir in sorted(id_dir.iterdir()):
                if not name_dir.is_dir():
                    continue
                config_path = name_dir / "team_config.json"
                if config_path.exists():
                    dirs.append((name_dir, config_path))
        if not dirs:
            return

        results = await asyncio.gather(
            *[self._load_one(team_dir, config_path)
              for team_dir, config_path in dirs],
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "Failed to load team from '%s': %s", dirs[i][0], result, exc_info=result,
                )

    async def _load_one(self, team_dir: Path, config_path: Path):
        with open(config_path, encoding='utf-8') as f:
            raw = json.loads(f.read()) or {}
        team_id: str = raw.get("id", "") or _next_id()

        # Reconstruct agents from memberIds
        agent_ids: list[str] = raw.get("memberIds", [])
        agents: dict[str, Agent] = {}
        for aid in agent_ids:
            agent = self._agent_factory.agents.get(aid)
            if agent:
                agents[agent.name] = agent

        # Reconstruct contacts — pass through directly, format is {agentName: {otherName: role}}
        contacts: dict[str, dict[str, str]] = {}
        for agent_name, contact_dict in raw.get("contacts", {}).items():
            contacts[agent_name] = {
                other: role
                for other, role in contact_dict.items()
                if other != agent_name  # defensive filter for self-key
            }

        core_config = CoreTeamConfig(
            name=raw.get("name", ""),
            team_description=raw.get("teamDescription", ""),
            agents=agents,
            contacts=contacts,
        )
        team = AgentTeam.create(core_config)
        team.base_dir = team_dir

        self.teams[team_id] = team
        self._team_meta[team_id] = raw
        self._wire_team_dispatcher(team_id, team)
        self.conversations.ensure_loaded(team_id, team)
        if raw.get("started", False):
            self._started.add(team_id)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get(self, team_id: str) -> AgentTeam | None:
        return self.teams.get(team_id)

    def get_config(self, team_id: str) -> TeamConfig | None:
        team = self.teams.get(team_id)
        if not team:
            return None

        meta = self._team_meta.get(team_id, {})

        return TeamConfig(
            id=team_id,
            name=team.name,
            teamDescription=team.team_description,
            workingDir=meta.get("workingDir", ""),
            baseDir=str(team.base_dir) if team.base_dir else "",
            memberIds=meta.get("memberIds", []),
            contacts=meta.get("contacts", {}),
            started=team_id in self._started,
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create(self, config: TeamConfig, member_configs: list[AgentConfig] | None = None) -> tuple[AgentTeam, str]:
        """Create a team.

        Flow:
        1. generate team_id
        2. create member agents one by one via AgentFactory (agents auto-persist to data/agents/)
        3. build core AgentTeam instance
        4. persist team_config.json
        Rolls back created agents on failure.
        """
        team_id = _next_id()

        # --- step 0: validate member name uniqueness ---
        seen_names: set[str] = set()
        for member_cfg in (member_configs or []):
            name = member_cfg.name.strip()
            if name in seen_names:
                raise ValueError(f"Duplicate member name '{name}' in team '{config.name}'")
            seen_names.add(name)

        # --- step 1: create member agents ---
        # team's workingDir is the shared working directory for all member agents
        team_working_dir = config.workingDir or ""
        created_agent_ids: list[str] = []
        agents: dict[str, Agent] = {}
        try:
            for member_cfg in (member_configs or []):
                if team_working_dir and not member_cfg.workingDir:
                    member_cfg = member_cfg.model_copy(
                        update={"workingDir": team_working_dir}
                    )
                agent = await self._agent_factory.create(member_cfg)
                # AgentFactory.create() sets config.id = agent_id internally
                # member_cfg is passed by reference, so .id has been assigned
                created_agent_ids.append(member_cfg.id)
                agents[agent.name] = agent
        except Exception:
            # rollback: delete already-created agents
            for aid in created_agent_ids:
                with contextlib.suppress(Exception):
                    await self._agent_factory.delete(aid)
            raise

        # --- step 2: build core AgentTeam ---
        # contacts format: {agentName: {otherName: role}}, no self-key
        contacts = config.contacts or {}

        core_config = CoreTeamConfig(
            name=config.name,
            team_description=config.teamDescription,
            agents=agents,
            contacts=contacts,
        )
        team = AgentTeam.create(core_config)

        # --- step 3: persist team_config.json ---
        team_dir = self._data_dir / "teams" / team_id / config.name
        team_dir.mkdir(parents=True, exist_ok=True)
        team.base_dir = team_dir

        team_data = {
            "id": team_id,
            "name": config.name,
            "teamDescription": config.teamDescription,
            "memberIds": created_agent_ids,
            "contacts": config.contacts,
            "workingDir": team_working_dir,
            "started": False,
        }
        with open(team_dir / "team_config.json", 'w', encoding='utf-8') as f:
            json.dump(team_data, f, indent=2, ensure_ascii=False)

        self.teams[team_id] = team
        self._team_meta[team_id] = team_data
        self._wire_team_dispatcher(team_id, team)
        await self.conversations.create_conversation(team, "Conversation")
        return team, team_id

    def _persist_team_meta(self, team_id: str):
        meta = self._team_meta.get(team_id)
        if not meta:
            return
        team = self.teams.get(team_id)
        if not team or not team.base_dir:
            return
        config_path = team.base_dir / "team_config.json"
        if config_path.parent.exists():
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _clear_team_runtime(agent: Agent) -> None:
        team_tool_names = [
            name
            for name, tool in list(agent.tools.items())
            if getattr(tool, "source", None) == "team"
        ]
        if team_tool_names:
            agent.remove_tools(team_tool_names)
        agent.remove_runtime_prompt("team")
        agent.remove_runtime_prompt("teammates")

    @staticmethod
    def _normalize_contacts(
        contacts: dict[str, dict[str, str]] | None,
        member_names: set[str],
    ) -> dict[str, dict[str, str]]:
        result: dict[str, dict[str, str]] = {}
        for name in member_names:
            raw_contacts = (contacts or {}).get(name, {})
            result[name] = {
                other: role
                for other, role in raw_contacts.items()
                if other in member_names and other != name
            }
        return result

    @staticmethod
    def _member_update_payload(config: AgentConfig) -> dict:
        return {
            "name": config.name,
            "modelId": config.modelId,
            "systemPrompt": config.systemPrompt,
            "workingDir": config.workingDir,
            "toolIds": list(config.toolIds),
            "skillIds": list(config.skillIds),
            "toolPolicy": dict(config.toolPolicy or {}),
            "hookNames": list(config.hookNames),
            "hookConfig": dict(config.hookConfig or {}),
        }

    def _rebuild_runtime_team(self, team_id: str) -> AgentTeam:
        old_team = self.teams[team_id]
        meta = self._team_meta.get(team_id, {})
        base_dir = old_team.base_dir
        team_messages = old_team.get_team_messages()

        for agent in old_team.agents.values():
            self._clear_team_runtime(agent)

        agents: dict[str, Agent] = {}
        for aid in meta.get("memberIds", []):
            agent = self._agent_factory.agents.get(aid)
            if agent:
                agents[agent.name] = agent

        team = AgentTeam.create(
            CoreTeamConfig(
                name=meta.get("name", old_team.name),
                team_description=meta.get("teamDescription", old_team.team_description),
                agents=agents,
                contacts=meta.get("contacts", {}),
            )
        )
        team.base_dir = base_dir
        team._team_messages = team_messages
        self.teams[team_id] = team
        self._wire_team_dispatcher(team_id, team)
        return team

    async def _sync_members(
        self,
        team_id: str,
        member_updates: list[dict],
        meta: dict,
        delete_removed_member_ids: set[str] | None = None,
    ) -> None:
        old_member_ids = list(meta.get("memberIds", []))
        member_id_by_name: dict[str, str] = {}
        for aid in old_member_ids:
            agent = self._agent_factory.agents.get(aid)
            if agent:
                member_id_by_name[agent.name] = aid

        new_member_ids: list[str] = []
        seen_names: set[str] = set()
        created_ids: list[str] = []
        try:
            for raw_member in member_updates:
                member_cfg = AgentConfig(**raw_member)
                member_cfg.name = member_cfg.name.strip()
                if not member_cfg.name:
                    raise ValueError("Team member name cannot be empty")
                if member_cfg.name in seen_names:
                    raise ValueError(f"Duplicate member name '{member_cfg.name}' in team '{meta.get('name', team_id)}'")
                seen_names.add(member_cfg.name)

                existing_id = member_id_by_name.get(member_cfg.name)
                if existing_id:
                    await self._agent_factory.update(
                        existing_id,
                        self._member_update_payload(member_cfg),
                    )
                    new_member_ids.append(existing_id)
                    continue

                if meta.get("workingDir") and not member_cfg.workingDir:
                    member_cfg.workingDir = meta["workingDir"]
                agent = await self._agent_factory.create(member_cfg)
                created_ids.append(member_cfg.id)
                self._clear_team_runtime(agent)
                new_member_ids.append(member_cfg.id)
        except Exception:
            for aid in created_ids:
                with contextlib.suppress(Exception):
                    await self._agent_factory.delete(aid)
            raise

        meta["memberIds"] = new_member_ids
        meta["contacts"] = self._normalize_contacts(meta.get("contacts", {}), seen_names)

        delete_requested = delete_removed_member_ids or set()
        removed_ids = set(old_member_ids) - set(new_member_ids)
        for aid in sorted(removed_ids & delete_requested):
            await self._agent_factory.delete(aid)

    def start(self, team_id: str):
        self._started.add(team_id)
        meta = self._team_meta.get(team_id, {})
        meta["started"] = True
        self._persist_team_meta(team_id)

    def stop(self, team_id: str):
        self._started.discard(team_id)
        meta = self._team_meta.get(team_id, {})
        meta["started"] = False
        self._persist_team_meta(team_id)

    def is_started(self, team_id: str) -> bool:
        return team_id in self._started

    def get_state(self, team_id: str) -> str:
        team = self.teams.get(team_id)
        if not team:
            return "unknown"
        team.update_state()
        return team.state

    async def update(self, team_id: str, updates: dict) -> AgentTeam | None:
        team = self.teams.get(team_id)
        if not team:
            return None

        meta = self._team_meta.get(team_id, {})
        if "teamDescription" in updates:
            team.team_description = updates["teamDescription"]
            meta["teamDescription"] = updates["teamDescription"]
        if "name" in updates:
            team.name = updates["name"]
            meta["name"] = updates["name"]
        if "workingDir" in updates:
            meta["workingDir"] = updates["workingDir"]
        if "contacts" in updates:
            meta["contacts"] = updates["contacts"]
        if "members" in updates:
            delete_removed_member_ids = set(updates.get("deleteRemovedMemberIds") or [])
            await self._sync_members(
                team_id,
                updates["members"] or [],
                meta,
                delete_removed_member_ids,
            )
            team = self._rebuild_runtime_team(team_id)
        elif "contacts" in updates:
            member_names = set(team.agents.keys())
            meta["contacts"] = self._normalize_contacts(meta.get("contacts", {}), member_names)
            team = self._rebuild_runtime_team(team_id)

        # Persist updated meta
        if team.base_dir:
            config_path = team.base_dir / "team_config.json"
            if config_path.parent.exists():
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, indent=2, ensure_ascii=False)

        return team

    async def delete(self, team_id: str) -> bool:
        team = self.teams.get(team_id)
        if not team:
            return False

        # cascade delete all member agents
        meta = self._team_meta.get(team_id, {})
        member_ids: list[str] = meta.get("memberIds", [])
        for aid in member_ids:
            try:
                await self._agent_factory.delete(aid)
                logger.info("Deleted member agent '%s' during team '%s' deletion", aid, team_id)
            except Exception as e:
                logger.warning("Failed to delete member agent '%s' during team deletion: %s", aid, e)

        del self.teams[team_id]
        self._team_meta.pop(team_id, None)
        self._started.discard(team_id)
        self._dispatchers.pop(team_id, None)
        # delete teams/{id}/ directory (parent of team.base_dir)
        if team.base_dir:
            team_root = team.base_dir.parent
            if team_root.exists():
                shutil.rmtree(team_root)
        return True
