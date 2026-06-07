import asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException

from backend.state import state_manager
from backend.schemas import TeamConfig, TeamSummary, CreateTeamRequest
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
        # 检查 team_config.json 是否存在（可能在新结构 teams/{id}/{name}/ 或旧结构 teams/{id}/）
        found = False
        if team.base_dir:
            found = (team.base_dir / "team_config.json").exists()
        if not found and (teams_dir / team_id / "team_config.json").exists():
            found = True
        if not found:
            stale_ids.append(team_id)
            continue
        meta = state_manager.team_factory._team_meta.get(team_id, {})
        data = TeamSummary(
            id=team_id,
            name=team.name,
            agentCount=len(team.agents),
            teamDescription=team.team_description,
            workingDir=meta.get("workingDir", ""),
            baseDir=str(team.base_dir) if team.base_dir else "",
            memberIds=meta.get("memberIds", []),
            started=state_manager.team_factory.is_started(team_id),
        ).model_dump(mode="json")
        data["state"] = state_manager.team_factory.get_state(team_id)
        result.append(data)
    for team_id in stale_ids:
        state_manager.team_factory.teams.pop(team_id, None)
    return result


@router.get("/{team_id}")
async def get_team(team_id: str):
    _resolve_team(team_id)
    config = state_manager.get_team_config(team_id)
    if not config:
        return {"error": {"code": "TEAM_NOT_FOUND", "message": f"Team '{team_id}' not found"}}
    data = config.model_dump(mode="json")
    data["state"] = state_manager.team_factory.get_state(team_id)
    return data


@router.post("")
async def create_team(req: CreateTeamRequest):
    # Check for duplicate name
    for team in state_manager.team_factory.teams.values():
        if team.name == req.name:
            raise ConflictError(ErrorCode.TEAM_NOT_FOUND,
                                f"Team '{req.name}' already exists")

    # Build TeamConfig from the request
    config = TeamConfig(
        name=req.name,
        teamDescription=req.teamDescription,
        workingDir=req.workingDir,
        contacts=req.contacts,
    )

    _team, team_id = await state_manager.create_team(config, member_configs=req.members)
    data = state_manager.get_team_config(team_id).model_dump(mode="json")
    data["state"] = state_manager.team_factory.get_state(team_id)
    return data


@router.put("/{team_id}")
async def update_team(team_id: str, updates: dict):
    _resolve_team(team_id)
    team = state_manager.update_team(team_id, updates)
    if not team:
        return {"error": {"code": "TEAM_NOT_FOUND", "message": f"Team '{team_id}' not found"}}
    data = state_manager.get_team_config(team_id).model_dump(mode="json")
    data["state"] = state_manager.team_factory.get_state(team_id)
    return data


@router.delete("/{team_id}")
async def delete_team(team_id: str):
    _resolve_team(team_id)
    if not await state_manager.delete_team(team_id):
        return {"error": {"code": "TEAM_NOT_FOUND", "message": f"Team '{team_id}' not found"}}
    return {"success": True}


@router.get("/{team_id}/messages")
async def get_team_messages(team_id: str):
    _resolve_team(team_id)
    team = state_manager.team_factory.teams.get(team_id)
    if not team:
        return []
    return [msg.to_dict() for msg in team.get_team_messages()]


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

    # 等待所有 agent 事件循环启动完毕（状态不再为 Ready）
    for _ in range(30):  # 最多等 3 秒
        team.update_state()
        if str(team.state).lower() not in ("ready",):
            break
        await asyncio.sleep(0.1)
    else:
        team.update_state()
        logger.warning("Team '%s' members did not leave Ready state within 3s", team.name)

    state_manager.team_factory.start(team_id)
    return {"state": state_manager.team_factory.get_state(team_id)}


@router.post("/{team_id}/stop")
async def stop_team(team_id: str):
    _resolve_team(team_id)
    team = state_manager.team_factory.teams.get(team_id)
    if not team:
        return {"error": {"code": "TEAM_NOT_FOUND", "message": f"Team '{team_id}' not found"}}

    await team.stop()
    state_manager.team_factory.stop(team_id)
    agent_id_by_name = {a.name: aid for aid, a in state_manager.agent_factory.agents.items()}
    for agent_name in team.agents:
        aid = agent_id_by_name.get(agent_name, agent_name)
        try:
            await state_manager.stop_agent(aid)
        except Exception:
            logger.warning("Failed to stop agent '%s' during team stop", agent_name)
    return {"state": state_manager.team_factory.get_state(team_id)}
