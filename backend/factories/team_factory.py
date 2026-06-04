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

        team = await AgentTeam.load(team_dir)
        setattr(team, "id", team_id)
        self.teams[team_id] = team

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get(self, team_id: str) -> Optional[AgentTeam]:
        return self.teams.get(team_id)

    def get_config(self, team_id: str) -> Optional[TeamConfig]:
        team = self.teams.get(team_id)
        if not team:
            return None

        team_base_dir = ""
        if team.agents:
            first_agent = next(iter(team.agents.values()))
            team_base_dir = str(first_agent.base_dir.parent)

        # Build memberIds from team's agents
        member_ids: list[str] = []
        for agent_name, agent in team.agents.items():
            # Find agent_id by identity match
            agent_id = next(
                (aid for aid, a in self._agent_factory.agents.items() if a is agent),
                "",
            )
            member_ids.append(agent_id)

        # Build contacts
        contacts: dict[str, dict[str, str]] = {}
        for agent_name, visible_set in team._contacts.items():
            entry: dict[str, str] = {other: "" for other in visible_set}
            entry[agent_name] = ""
            contacts[agent_name] = entry

        return TeamConfig(
            id=team_id,
            name=team.name,
            teamDescription=team.team_description,
            baseDir=team_base_dir,
            memberIds=member_ids,
            contacts=contacts,
        )

    def list_summaries(self) -> list[TeamSummary]:
        result = []
        for team_id, team in self.teams.items():
            result.append(TeamSummary(
                id=team_id,
                name=team.name,
                agentCount=len(team.agents),
                teamDescription=team.team_description,
            ))
        return result

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create(self, config: TeamConfig, member_configs: list[AgentConfig] | None = None) -> AgentTeam:
        """Create a team. member_configs are used to create agents if provided.

        In the new design, TeamConfig.memberIds stores agent IDs. The caller
        can either:
        1. Pass memberIds directly (agents already exist), or
        2. Pass member_configs to create agents first, then populate memberIds.
        """
        team_id = config.id or _next_id()

        # Derive team base dir
        team_base_dir = ""
        if config.baseDir:
            team_base_dir = config.baseDir
            Path(team_base_dir).mkdir(parents=True, exist_ok=True)

        # Create member agents if member_configs provided
        created_agent_ids: list[str] = []
        agents = {}

        if member_configs:
            try:
                for member_cfg in member_configs:
                    if team_base_dir and not member_cfg.basePath:
                        member_cfg = member_cfg.model_copy(
                            update={"basePath": str(Path(team_base_dir) / member_cfg.name)}
                        )
                    agent = await self._agent_factory.create(member_cfg)
                    agent_id = next(
                        (aid for aid, a in self._agent_factory.agents.items() if a is agent),
                        None,
                    )
                    if agent_id:
                        created_agent_ids.append(agent_id)
                    agents[agent.name] = agent
            except Exception:
                for aid in created_agent_ids:
                    try:
                        await self._agent_factory.delete(aid)
                    except Exception:
                        pass
                raise
        else:
            # Use existing agents from memberIds
            for agent_id in config.memberIds:
                agent = self._agent_factory.agents.get(agent_id)
                if agent:
                    agents[agent.name] = agent

        # Build contacts
        contacts = {}
        for agent_name, contact_dict in config.contacts.items():
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

        # Save to disk
        team_dir = self._data_dir / "teams" / team_id
        team_dir.mkdir(parents=True, exist_ok=True)
        team.save(team_dir)

        # Write team config as JSON
        config_path = team_dir / "team_config.json"
        team_data = {
            "id": team_id,
            "name": config.name,
            "teamDescription": config.teamDescription,
            "memberIds": config.memberIds or created_agent_ids,
            "contacts": config.contacts,
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(team_data, f, indent=2, ensure_ascii=False)

        setattr(team, "id", team_id)
        self.teams[team_id] = team
        return team

    def update(self, team_id: str, updates: dict) -> Optional[AgentTeam]:
        team = self.teams.get(team_id)
        if not team:
            return None
        if "teamDescription" in updates:
            team.team_description = updates["teamDescription"]
        if "name" in updates:
            # Name change is reflected in the team object
            pass
        team_dir = self._data_dir / "teams" / team_id
        team.save(team_dir)
        return team

    def delete(self, team_id: str) -> bool:
        team = self.teams.get(team_id)
        if not team:
            return False
        del self.teams[team_id]
        team_dir = self._data_dir / "teams" / team_id
        if team_dir.exists():
            shutil.rmtree(team_dir)
        return True
