from pathlib import Path

from fastapi import APIRouter, Query

from backend.state import state_manager
from backend.schemas import AgentConfig
from backend.errors import ConflictError, ErrorCode
from backend.logging import get_backend_logger

logger = get_backend_logger("api.agents")
router = APIRouter()


@router.get("")
async def list_agents():
    result = []
    for name in state_manager.agents:
        config = state_manager.get_agent_config(name)
        if config:
            data = config.model_dump(mode="json")
            state_info = state_manager.get_agent_state(name)
            data["state"] = state_info["state"]
            data["currentSessionId"] = state_info["session_id"]
            result.append(data)
    return result


@router.get("/{name}")
async def get_agent(name: str):
    config = state_manager.get_agent_config(name)
    if not config:
        return {"error": {"code": "AGENT_NOT_FOUND", "message": f"Agent '{name}' not found"}}
    data = config.model_dump(mode="json")
    state_info = state_manager.get_agent_state(name)
    data["state"] = state_info["state"]
    data["currentSessionId"] = state_info["session_id"]
    return data


@router.post("")
async def create_agent(config: AgentConfig):
    if config.name in state_manager.agents:
        raise ConflictError(ErrorCode.AGENT_ALREADY_EXISTS,
                            f"Agent '{config.name}' already exists")
    agent = await state_manager.create_agent(config)
    data = state_manager.get_agent_config(agent.name).model_dump(mode="json")
    data["state"] = "Waiting"
    data["currentSessionId"] = agent.session.id
    data["messages"] = []
    return data


@router.put("/{name}")
async def update_agent(name: str, updates: dict):
    agent = await state_manager.update_agent(name, updates)
    if not agent:
        return {"error": {"code": "AGENT_NOT_FOUND", "message": f"Agent '{name}' not found"}}
    data = state_manager.get_agent_config(name).model_dump(mode="json")
    state_info = state_manager.get_agent_state(name)
    data["state"] = state_info["state"]
    data["currentSessionId"] = state_info["session_id"]
    return data


@router.delete("/{name}")
async def delete_agent(name: str, delete_files: bool = Query(default=False)):
    base_path = None
    if delete_files:
        agent = state_manager.agents.get(name)
        if agent:
            base_path = getattr(agent, "base_dir", None)

    state_manager.delete_agent(name)

    if delete_files and base_path:
        bp = Path(str(base_path)).expanduser().resolve()
        if bp.exists():
            import shutil
            shutil.rmtree(bp)

    return {"success": True}


@router.post("/{name}/start")
async def start_agent(name: str):
    await state_manager.start_agent(name)
    return state_manager.get_agent_state(name)


@router.post("/{name}/stop")
async def stop_agent(name: str):
    await state_manager.stop_agent(name)
    return state_manager.get_agent_state(name)


@router.get("/{name}/state")
async def get_agent_state(name: str):
    state_info = state_manager.get_agent_state(name)
    if state_info["state"] == "unknown":
        return {"error": {"code": "AGENT_NOT_FOUND", "message": f"Agent '{name}' not found"}}
    return state_info


@router.get("/{name}/sessions")
async def list_sessions(name: str):
    return state_manager.get_agent_sessions(name)


@router.post("/{name}/sessions/{session_id}/switch")
async def switch_session(name: str, session_id: str):
    await state_manager.switch_agent_session(name, session_id)
    return {"session_id": session_id, "status": "switched"}


@router.post("/{name}/sessions/new")
async def new_session(name: str):
    await state_manager.new_agent_session(name)
    return {"session_id": state_manager.agents[name].session.id}


@router.get("/{name}/messages")
async def get_messages(name: str):
    return state_manager.get_agent_messages(name)
