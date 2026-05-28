from fastapi import APIRouter, HTTPException

from backend.state import state_manager
from backend.schemas import MCPServerConfig

router = APIRouter()


@router.get("")
async def list_mcps():
    return [m.model_dump(mode="json") for m in state_manager.mcp_servers]


@router.post("")
async def create_mcp(config: MCPServerConfig):
    if state_manager.get_mcp(config.name):
        raise HTTPException(status_code=400, detail=f"MCP server '{config.name}' already exists")
    state_manager.add_mcp(config)
    return config.model_dump(mode="json")


@router.put("/{name}")
async def update_mcp(name: str, updates: dict):
    updated = state_manager.update_mcp(name, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return updated.model_dump(mode="json")


@router.delete("/{name}")
async def delete_mcp(name: str):
    if not state_manager.delete_mcp(name):
        raise HTTPException(status_code=404, detail="MCP server not found")
    return {"success": True}


@router.post("/{name}/activate")
async def activate_mcp(name: str):
    manager = state_manager.get_mcp_manager()
    try:
        tools = await manager.activate_client(name)
        return {"success": True, "tools": len(tools)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/deactivate")
async def deactivate_mcp(name: str):
    manager = state_manager.get_mcp_manager()
    try:
        await manager.deactivate_client(name)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
