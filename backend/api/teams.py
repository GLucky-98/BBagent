from pathlib import Path
from fastapi import APIRouter, HTTPException

from backend.state import state_manager
from backend.schemas import TeamConfig, TeamSummary
from backend.errors import ConflictError, ErrorCode
from backend.logging import get_backend_logger

DATA_DIR = Path(__file__).parent.parent.parent / "data"

logger = get_backend_logger("api.teams")
router = APIRouter()


def _resolve_team(team_id: str) -> str:
    if team_id not in state_manager.team_factory.teams:
        raise HTTPException(
            status_code=404,
            detail=f"Team '{team_id}' not found",
        )
    return team_id


@router.get("")
async def list_teams():
    teams_dir = DATA_DIR / "teams"
    result = []
    stale_ids: list[str] = []
    for team_id, team in state_manager.team_factory.teams.items():
        if not (teams_dir / team_id / "team_config.json").exists():
            stale_ids.append(team_id)
            continue
        result.append(TeamSummary(
            id=team_id,
            name=team.name,
            agentCount=len(team.agents),
            teamDescription=team.team_description,
        ).model_dump(mode="json"))
    for team_id in stale_ids:
        state_manager.team_factory.teams.pop(team_id, None)
    return result


@router.get("/{team_id}")
async def get_team(team_id: str):
    _resolve_team(team_id)
    config = state_manager.get_team_config(team_id)
    if not config:
        return {"error": {"code": "TEAM_NOT_FOUND", "message": f"Team '{team_id}' not found"}}
    return config.model_dump(mode="json")


@router.post("")
async def create_team(config: TeamConfig):
    # Check for duplicate name
    for team in state_manager.team_factory.teams.values():
        if team.name == config.name:
            raise ConflictError(ErrorCode.TEAM_NOT_FOUND,
                                f"Team '{config.name}' already exists")
    team = await state_manager.create_team(config)
    team_id = next(
        (tid for tid, t in state_manager.team_factory.teams.items() if t is team),
        None,
    )
    return state_manager.get_team_config(team_id).model_dump(mode="json")


@router.put("/{team_id}")
async def update_team(team_id: str, updates: dict):
    _resolve_team(team_id)
    team = state_manager.update_team(team_id, updates)
    if not team:
        return {"error": {"code": "TEAM_NOT_FOUND", "message": f"Team '{team_id}' not found"}}
    return state_manager.get_team_config(team_id).model_dump(mode="json")


@router.delete("/{team_id}")
async def delete_team(team_id: str):
    _resolve_team(team_id)
    if not state_manager.delete_team(team_id):
        return {"error": {"code": "TEAM_NOT_FOUND", "message": f"Team '{team_id}' not found"}}
    return {"success": True}


@router.post("/{team_id}/start")
async def start_team(team_id: str):
    _resolve_team(team_id)
    team = state_manager.team_factory.teams.get(team_id)
    if not team:
        return {"error": {"code": "TEAM_NOT_FOUND", "message": f"Team '{team_id}' not found"}}

    agent_id_by_name = {a.name: aid for aid, a in state_manager.agent_factory.agents.items()}
    for agent_name in team.agents:
        aid = agent_id_by_name.get(agent_name, agent_name)
        await state_manager.start_agent(aid)
    await team.start()
    return {"status": "started"}


@router.post("/{team_id}/stop")
async def stop_team(team_id: str):
    _resolve_team(team_id)
    team = state_manager.team_factory.teams.get(team_id)
    if not team:
        return {"error": {"code": "TEAM_NOT_FOUND", "message": f"Team '{team_id}' not found"}}

    await team.stop()
    agent_id_by_name = {a.name: aid for aid, a in state_manager.agent_factory.agents.items()}
    for agent_name in team.agents:
        aid = agent_id_by_name.get(agent_name, agent_name)
        try:
            await state_manager.stop_agent(aid)
        except Exception:
            logger.warning("Failed to stop agent '%s' during team stop", agent_name)
    return {"status": "stopped"}
