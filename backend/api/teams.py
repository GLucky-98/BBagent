from fastapi import APIRouter, HTTPException

from backend.state import state_manager
from backend.schemas import TeamConfig, TeamSummary

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
        raise HTTPException(status_code=404, detail="Team not found")
    return config.model_dump(mode="json")


@router.post("")
async def create_team(config: TeamConfig):
    if config.name in state_manager.teams:
        raise HTTPException(status_code=400, detail=f"Team '{config.name}' already exists")
    try:
        team = state_manager.create_team(config)
        return state_manager.get_team_config(team.name).model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{name}")
async def update_team(name: str, updates: dict):
    team = state_manager.update_team(name, updates)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return state_manager.get_team_config(name).model_dump(mode="json")


@router.delete("/{name}")
async def delete_team(name: str):
    if not state_manager.delete_team(name):
        raise HTTPException(status_code=404, detail="Team not found")
    return {"success": True}


@router.post("/{name}/start")
async def start_team(name: str):
    team = state_manager.teams.get(name)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    try:
        await team.start()
        return {"status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/stop")
async def stop_team(name: str):
    team = state_manager.teams.get(name)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    try:
        await team.stop()
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
