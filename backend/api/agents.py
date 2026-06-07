from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.state import state_manager
from backend.schemas import AgentConfig
from backend.logging import get_backend_logger

DATA_DIR = Path(__file__).parent.parent.parent / "data"

logger = get_backend_logger("api.agents")
router = APIRouter()


def _resolve_agent(agent_id: str) -> str:
    if agent_id not in state_manager.agent_factory.agents:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found",
        )
    return agent_id


@router.get("")
async def list_agents():
    agents_dir = DATA_DIR / "agents"
    result = []
    stale_ids: list[str] = []
    for agent_id in state_manager.agent_factory.agents:
        agent = state_manager.agent_factory.agents[agent_id]
        if not (agent.base_dir / "agent_config.json").exists():
            stale_ids.append(agent_id)
            continue
        config = state_manager.get_agent_config(agent_id)
        if config:
            data = config.model_dump(mode="json")
            state_info = state_manager.get_agent_state(agent_id)
            data["state"] = state_info["state"]
            data["currentSessionId"] = state_info["session_id"]
            result.append(data)
    for agent_id in stale_ids:
        state_manager.agent_factory.agents.pop(agent_id, None)
        state_manager.agent_factory._model_ids.pop(agent_id, None)
    return result


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    _resolve_agent(agent_id)
    config = state_manager.get_agent_config(agent_id)
    if not config:
        return {"error": {"code": "AGENT_NOT_FOUND", "message": f"Agent '{agent_id}' not found"}}
    data = config.model_dump(mode="json")
    state_info = state_manager.get_agent_state(agent_id)
    data["state"] = state_info["state"]
    data["currentSessionId"] = state_info["session_id"]
    return data


@router.post("")
async def create_agent(config: AgentConfig):
    agent = await state_manager.create_agent(config)
    agent_id = next(
        (i for i, a in state_manager.agent_factory.agents.items() if a is agent),
        None,
    )
    data = state_manager.get_agent_config(agent_id).model_dump(mode="json")
    state_info = state_manager.get_agent_state(agent_id)
    data["state"] = state_info["state"]
    data["currentSessionId"] = state_info["session_id"]
    return data


@router.put("/{agent_id}")
async def update_agent(agent_id: str, updates: dict):
    _resolve_agent(agent_id)
    agent = await state_manager.update_agent(agent_id, updates)
    if not agent:
        return {"error": {"code": "AGENT_NOT_FOUND", "message": f"Agent '{agent_id}' not found"}}
    data = state_manager.get_agent_config(agent_id).model_dump(mode="json")
    state_info = state_manager.get_agent_state(agent_id)
    data["state"] = state_info["state"]
    data["currentSessionId"] = state_info["session_id"]
    return data


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, delete_files: bool = Query(default=False)):
    _resolve_agent(agent_id)
    base_path = None
    if delete_files:
        agent = state_manager.agent_factory.agents.get(agent_id)
        if agent:
            base_path = getattr(agent, "base_dir", None)

    await state_manager.delete_agent(agent_id)

    if delete_files and base_path:
        bp = Path(str(base_path)).expanduser().resolve()
        if bp.exists():
            import shutil
            shutil.rmtree(bp)

    return {"success": True}


@router.post("/{agent_id}/start")
async def start_agent(agent_id: str):
    _resolve_agent(agent_id)
    await state_manager.start_agent(agent_id)
    return state_manager.get_agent_state(agent_id)


@router.post("/{agent_id}/stop")
async def stop_agent(agent_id: str):
    _resolve_agent(agent_id)
    await state_manager.stop_agent(agent_id)
    return state_manager.get_agent_state(agent_id)


@router.get("/{agent_id}/state")
async def get_agent_state(agent_id: str):
    _resolve_agent(agent_id)
    state_info = state_manager.get_agent_state(agent_id)
    return state_info


@router.get("/{agent_id}/sessions")
async def list_sessions(agent_id: str):
    _resolve_agent(agent_id)
    return state_manager.get_agent_sessions(agent_id)


@router.post("/{agent_id}/sessions/{session_id}/switch")
async def switch_session(agent_id: str, session_id: str):
    _resolve_agent(agent_id)
    await state_manager.switch_agent_session(agent_id, session_id)
    return {"session_id": session_id, "status": "switched"}


@router.post("/{agent_id}/sessions/new")
async def new_session(agent_id: str):
    _resolve_agent(agent_id)
    await state_manager.new_agent_session(agent_id)
    return {"session_id": state_manager.agent_factory.agents[agent_id].session.id}


@router.get("/{agent_id}/messages")
async def get_messages(agent_id: str):
    _resolve_agent(agent_id)
    return state_manager.get_agent_messages(agent_id)


# ------------------------------------------------------------------
# Timer CRUD
# ------------------------------------------------------------------

@router.get("/{agent_id}/timers")
async def list_timers(agent_id: str):
    _resolve_agent(agent_id)
    return state_manager.agent_factory.list_timers(agent_id)


@router.post("/{agent_id}/timers")
async def add_timer(agent_id: str, body: dict):
    _resolve_agent(agent_id)

    name = body.get("name", "")
    seconds = body.get("seconds")
    hint = body.get("hint", "")
    enabled = body.get("enabled", True)

    if seconds is None or seconds <= 0:
        raise HTTPException(status_code=400, detail="seconds must be a positive number")

    try:
        state_manager.agent_factory.add_timer(agent_id, name=name, seconds=seconds, hint=hint, enabled=enabled)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return state_manager.agent_factory.list_timers(agent_id)


@router.put("/{agent_id}/timers/{timer_name}")
async def update_timer(agent_id: str, timer_name: str, body: dict):
    _resolve_agent(agent_id)

    success = state_manager.agent_factory.update_timer(
        agent_id, timer_name,
        seconds=body.get("seconds"),
        hint=body.get("hint"),
        enabled=body.get("enabled"),
    )
    if not success:
        raise HTTPException(status_code=404, detail=f"Timer '{timer_name}' not found")
    return state_manager.agent_factory.list_timers(agent_id)


@router.post("/{agent_id}/timers/{timer_name}/start")
async def start_timer(agent_id: str, timer_name: str):
    _resolve_agent(agent_id)
    success = state_manager.agent_factory.start_timer(agent_id, timer_name)
    return {"success": success}


@router.post("/{agent_id}/timers/{timer_name}/stop")
async def stop_timer(agent_id: str, timer_name: str):
    _resolve_agent(agent_id)
    success = state_manager.agent_factory.stop_timer(agent_id, timer_name)
    return {"success": success}


@router.delete("/{agent_id}/timers/{timer_name}")
async def delete_timer(agent_id: str, timer_name: str):
    _resolve_agent(agent_id)
    state_manager.agent_factory.cancel_timer(agent_id, timer_name)
    return state_manager.agent_factory.list_timers(agent_id)
