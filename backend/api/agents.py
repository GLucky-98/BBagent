from fastapi import APIRouter, HTTPException

from backend.state import state_manager
from backend.schemas import AgentConfig, AgentSummary

router = APIRouter()


@router.get("")
async def list_agents():
    result = []
    for name in state_manager.agents:
        config = state_manager.get_agent_config(name)
        if config:
            result.append(config.model_dump(mode="json"))
    return result


@router.get("/{name}")
async def get_agent(name: str):
    config = state_manager.get_agent_config(name)
    if not config:
        raise HTTPException(status_code=404, detail="Agent not found")
    return config.model_dump(mode="json")


@router.post("")
async def create_agent(config: AgentConfig):
    if config.name in state_manager.agents:
        raise HTTPException(status_code=400, detail=f"Agent '{config.name}' already exists")
    try:
        agent = state_manager.create_agent(config)
        return state_manager.get_agent_config(agent.name).model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{name}")
async def update_agent(name: str, updates: dict):
    agent = state_manager.update_agent(name, updates)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return state_manager.get_agent_config(name).model_dump(mode="json")


@router.delete("/{name}")
async def delete_agent(name: str):
    if not state_manager.delete_agent(name):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"success": True}


@router.post("/{name}/new_session")
async def new_session(name: str):
    agent = state_manager.agents.get(name)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    try:
        await agent.new_session()
        return {"session_id": agent.session.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
