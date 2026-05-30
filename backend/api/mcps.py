import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.state import state_manager
from backend.schemas import MCPServerConfig


class ImportRequest(BaseModel):
    path: str


router = APIRouter()


@router.get("")
async def list_mcps():
    return [m.model_dump(mode="json") for m in state_manager.mcp_servers]


@router.post("")
async def create_mcp(config: MCPServerConfig):
    if state_manager.get_mcp(config.name):
        raise HTTPException(status_code=400, detail=f"MCP server '{config.name}' already exists")
    await state_manager.add_mcp(config)
    return config.model_dump(mode="json")


@router.put("/{name}")
async def update_mcp(name: str, updates: dict):
    updated = await state_manager.update_mcp(name, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return updated.model_dump(mode="json")


@router.delete("/{name}")
async def delete_mcp(name: str):
    if not state_manager.delete_mcp(name):
        raise HTTPException(status_code=404, detail="MCP server not found")
    return {"success": True}


@router.post("/{name}/discover")
async def discover_mcp(name: str):
    try:
        tools = await state_manager._discover_mcp_tools(name)
        return {"success": True, "tools": [t.model_dump(mode="json") for t in tools]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_mcps(req: ImportRequest):
    target = Path(req.path).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=400, detail="Not a valid directory")

    imported = []
    for item in sorted(target.iterdir()):
        if not item.is_file() or item.suffix.lower() != ".json":
            continue
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
            if "mcpServers" in data:
                servers = data["mcpServers"]
                entries = servers if isinstance(servers, list) else list(servers.values())
            elif isinstance(data, list):
                entries = data
            elif isinstance(data, dict) and "name" in data and "command" in data:
                entries = [data]
            else:
                continue

            for entry in entries:
                cfg = MCPServerConfig(
                    name=entry.get("name", item.stem),
                    command=entry.get("command", ""),
                    args=entry.get("args", []),
                    env=entry.get("env", {}),
                )
                if state_manager.get_mcp(cfg.name):
                    continue
                await state_manager.add_mcp(cfg)
                imported.append(cfg.name)
        except Exception:
            continue

    return {"imported": len(imported)}
