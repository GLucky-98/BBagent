"""TeamFactory — manages TeamConfig CRUD and AgentTeam lifecycle.

TeamConfig now stores memberIds (list of agent_id strings) instead of
nested AgentConfig objects. Agent creation is delegated to AgentFactory.
"""

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Optional

from BBagent.core.agent import Agent
from BBagent.core.team import AgentTeam, TeamConfig as CoreTeamConfig

from backend.schemas import TeamConfig, AgentConfig, TeamSummary
from backend.factories import _next_id
from backend.logging import get_backend_logger, log_operation

logger = get_backend_logger("state.team_factory")


class TeamFactory:
    def __init__(self, data_dir: Path, agent_factory):
        self._data_dir = data_dir
        self._agent_factory = agent_factory
        self.teams: dict[str, AgentTeam] = {}  # team_id -> AgentTeam
        self._team_meta: dict[str, dict] = {}  # team_id -> persisted config dict
        self._started: set[str] = set()  # team_ids that have been started

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    async def load(self):
        teams_dir = self._data_dir / "teams"
        if not teams_dir.exists():
            return

        dirs = []
        for d in sorted(teams_dir.iterdir()):
            if not d.is_dir():
                continue
            config_path = d / "team_config.json"
            if config_path.exists():
                dirs.append((d, config_path))
        if not dirs:
            return

        results = await asyncio.gather(
            *[self._load_one(team_dir, config_path)
              for team_dir, config_path in dirs],
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Failed to load team from '%s': %s", dirs[i][0].name, result)

    async def _load_one(self, team_dir: Path, config_path: Path):
        with open(config_path, 'r', encoding='utf-8') as f:
            raw = json.loads(f.read()) or {}
        team_id: str = raw.get("id", "") or _next_id()

        # Reconstruct agents from memberIds
        agent_ids: list[str] = raw.get("memberIds", [])
        agents: dict[str, Agent] = {}
        for aid in agent_ids:
            agent = self._agent_factory.agents.get(aid)
            if agent:
                agents[agent.name] = agent

        # Reconstruct contacts
        contacts: dict[str, dict[str, str]] = {}
        for agent_name, contact_dict in raw.get("contacts", {}).items():
            contacts[agent_name] = {
                other: role
                for other, role in contact_dict.items()
                if other != agent_name
            }

        core_config = CoreTeamConfig(
            name=raw.get("name", ""),
            team_description=raw.get("teamDescription", ""),
            agents=agents,
            contacts=contacts,
        )
        team = AgentTeam.create(core_config)

        self.teams[team_id] = team
        self._team_meta[team_id] = raw
        if raw.get("started", False):
            self._started.add(team_id)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get(self, team_id: str) -> Optional[AgentTeam]:
        return self.teams.get(team_id)

    def get_config(self, team_id: str) -> Optional[TeamConfig]:
        team = self.teams.get(team_id)
        if not team:
            return None

        meta = self._team_meta.get(team_id, {})

        return TeamConfig(
            id=team_id,
            name=team.name,
            teamDescription=team.team_description,
            workingDir=meta.get("workingDir", ""),
            memberIds=meta.get("memberIds", []),
            contacts=meta.get("contacts", {}),
            started=team_id in self._started,
        )

    def list_summaries(self) -> list[TeamSummary]:
        result = []
        for team_id, team in self.teams.items():
            result.append(TeamSummary(
                id=team_id,
                name=team.name,
                agentCount=len(team.agents),
                teamDescription=team.team_description,
                started=team_id in self._started,
            ))
        return result

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create(self, config: TeamConfig, member_configs: list[AgentConfig] | None = None) -> tuple[AgentTeam, str]:
        """创建团队。

        流程：
        1. 生成 team_id
        2. 通过 AgentFactory 逐个创建成员 Agent（agent 自动落盘到 data/agents/）
        3. 构建 core AgentTeam 实例
        4. 落盘 team_config.json
        失败时回滚已创建的 agent。
        """
        team_id = _next_id()

        # --- 步骤1: 创建成员 Agent ---
        # team 的 workingDir 是所有 member agent 共享的工作目录
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
                # AgentFactory.create() 内部设置了 config.id = agent_id
                # member_cfg 是引用传递，所以 .id 已被赋值
                created_agent_ids.append(member_cfg.id)
                agents[agent.name] = agent
        except Exception:
            # 回滚：删除已创建的 agent
            for aid in created_agent_ids:
                try:
                    await self._agent_factory.delete(aid)
                except Exception:
                    pass
            raise

        # --- 步骤2: 构建 core AgentTeam ---
        contacts: dict[str, dict[str, str]] = {}
        for agent_name, contact_dict in (config.contacts or {}).items():
            contacts[agent_name] = {
                other: role
                for other, role in contact_dict.items()
                if other != agent_name
            }

        core_config = CoreTeamConfig(
            name=config.name,
            team_description=config.teamDescription,
            agents=agents,
            contacts=contacts,
        )
        team = AgentTeam.create(core_config)

        # --- 步骤3: 落盘 team_config.json ---
        team_dir = self._data_dir / "teams" / team_id
        team_dir.mkdir(parents=True, exist_ok=True)

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
        return team, team_id

    def _persist_team_meta(self, team_id: str):
        meta = self._team_meta.get(team_id)
        if not meta:
            return
        team_dir = self._data_dir / "teams" / team_id
        config_path = team_dir / "team_config.json"
        if config_path.parent.exists():
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)

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
        return str(team.state).lower()

    def update(self, team_id: str, updates: dict) -> Optional[AgentTeam]:
        team = self.teams.get(team_id)
        if not team:
            return None

        meta = self._team_meta.get(team_id, {})
        if "teamDescription" in updates:
            team.team_description = updates["teamDescription"]
            meta["teamDescription"] = updates["teamDescription"]
        if "name" in updates:
            meta["name"] = updates["name"]

        # Persist updated meta
        team_dir = self._data_dir / "teams" / team_id
        config_path = team_dir / "team_config.json"
        if config_path.exists():
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)

        return team

    async def delete(self, team_id: str) -> bool:
        team = self.teams.get(team_id)
        if not team:
            return False

        # 级联删除所有 member agents
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
        team_dir = self._data_dir / "teams" / team_id
        if team_dir.exists():
            shutil.rmtree(team_dir)
        return True
