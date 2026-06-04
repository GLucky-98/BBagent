import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.state import state_manager
from backend.schemas import MCPServerConfig


class ImportRequest(BaseModel):
    path: str


router = APIRouter()


def _resolve_mcp(ref: str) -> str:
    """Resolve a URL ref (id) to the canonical mcp_id."""
    if ref in state_manager.mcp_factory._configs:
        return ref
    raise HTTPException(status_code=404, detail=f"MCP server '{ref}' not found")


@router.get("")
async def list_mcps():
    return [m.model_dump(mode="json") for m in state_manager.mcp_factory.list_all()]


@router.post("")
async def create_mcp(config: MCPServerConfig):
    # Check duplicate name
    for existing in state_manager.mcp_factory.list_all():
        if existing.name == config.name:
            raise HTTPException(status_code=400, detail=f"MCP server '{config.name}' already exists")
    saved = await state_manager.add_mcp(config)
    return saved.model_dump(mode="json")


@router.put("/{mcp_ref}")
async def update_mcp(mcp_ref: str, updates: dict):
    mcp_id = _resolve_mcp(mcp_ref)
    updated = await state_manager.update_mcp(mcp_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return {
        **updated.model_dump(mode="json"),
        "hint": "MCP server config updated. Agents using tools from this MCP server may need to restart to take effect",
    }


@router.delete("/{mcp_ref}")
async def delete_mcp(mcp_ref: str):
    mcp_id = _resolve_mcp(mcp_ref)
    if not state_manager.delete_mcp(mcp_id):
        raise HTTPException(status_code=404, detail="MCP server not found")
    return {
        "success": True,
        "hint": "MCP server deleted. Agents using tools from this MCP server need to reconfigure their tools",
    }


@router.post("/{mcp_ref}/discover")
async def discover_mcp(mcp_ref: str):
    mcp_id = _resolve_mcp(mcp_ref)
    cfg = state_manager.mcp_factory.get(mcp_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="MCP server not found")
    try:
        tools = await state_manager.discover_mcp_tools(mcp_id)
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

    from BBagent.core.mcp import parse_config_dict

    imported = []
    for item in sorted(target.iterdir()):
        if not item.is_file() or item.suffix.lower() != ".json":
            continue
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
            core_configs = parse_config_dict(data, default_name=item.stem)

            for core_cfg in core_configs:
                # Check duplicate name
                name_exists = any(
                    e.name == core_cfg.name for e in state_manager.mcp_factory.list_all()
                )
                if name_exists:
                    continue
                cfg = MCPServerConfig(
                    name=core_cfg.name,
                    command=core_cfg.command,
                    args=core_cfg.args,
                    env=core_cfg.env,
                )
                await state_manager.add_mcp(cfg)
                imported.append(cfg.name)
        except Exception:
            continue

    return {"imported": len(imported)}
