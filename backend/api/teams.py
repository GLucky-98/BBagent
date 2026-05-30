from fastapi import APIRouter

from backend.state import state_manager
from backend.schemas import TeamConfig, TeamSummary
from backend.errors import ConflictError, ErrorCode
from backend.logging import get_backend_logger

logger = get_backend_logger("api.teams")
router = APIRouter()


@router.get("")
async def list_teams():
    result = []
    for name, team in state_manager.teams.items():
        result.append(TeamSummary(
            name=name,
            agentCount=len(team.agents),
            teamDescription=team.team_description,
        ).model_dump(mode="json"))
    return result


@router.get("/{name}")
async def get_team(name: str):
    config = state_manager.get_team_config(name)
    if not config:
        return {"error": {"code": "TEAM_NOT_FOUND", "message": f"Team '{name}' not found"}}
    return config.model_dump(mode="json")


@router.post("")
async def create_team(config: TeamConfig):
    if config.name in state_manager.teams:
        raise ConflictError(ErrorCode.TEAM_NOT_FOUND,
                            f"Team '{config.name}' already exists")
    team = state_manager.create_team(config)
    return state_manager.get_team_config(team.name).model_dump(mode="json")


@router.put("/{name}")
async def update_team(name: str, updates: dict):
    team = state_manager.update_team(name, updates)
    if not team:
        return {"error": {"code": "TEAM_NOT_FOUND", "message": f"Team '{name}' not found"}}
    return state_manager.get_team_config(name).model_dump(mode="json")


@router.delete("/{name}")
async def delete_team(name: str):
    if not state_manager.delete_team(name):
        return {"error": {"code": "TEAM_NOT_FOUND", "message": f"Team '{name}' not found"}}
    return {"success": True}


@router.post("/{name}/start")
async def start_team(name: str):
    team = state_manager.teams.get(name)
    if not team:
        return {"error": {"code": "TEAM_NOT_FOUND", "message": f"Team '{name}' not found"}}

    for agent_name in team.agents:
        await state_manager.start_agent(agent_name)
    await team.start()
    return {"status": "started"}


@router.post("/{name}/stop")
async def stop_team(name: str):
    team = state_manager.teams.get(name)
    if not team:
        return {"error": {"code": "TEAM_NOT_FOUND", "message": f"Team '{name}' not found"}}

    await team.stop()
    for agent_name in team.agents:
        try:
            await state_manager.stop_agent(agent_name)
        except Exception:
            logger.warning("Failed to stop agent '%s' during team stop", agent_name)
    return {"status": "stopped"}
