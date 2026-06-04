import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.state import state_manager
from backend.schemas import PromptConfig


class ImportRequest(BaseModel):
    path: str


router = APIRouter()


@router.get("")
async def list_prompts():
    return [p.model_dump(mode="json") for p in state_manager.prompt_factory.list_all()]


@router.post("")
async def create_prompt(config: PromptConfig):
    if state_manager.get_prompt(config.id):
        raise HTTPException(status_code=400, detail=f"Prompt with id '{config.id}' already exists")
    state_manager.add_prompt(config)
    return config.model_dump(mode="json")


@router.put("/{prompt_id}")
async def update_prompt(prompt_id: str, updates: dict):
    updated = state_manager.update_prompt(prompt_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return updated.model_dump(mode="json")


@router.delete("/{prompt_id}")
async def delete_prompt(prompt_id: str):
    if not state_manager.delete_prompt(prompt_id):
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"success": True}


@router.post("/import")
async def import_prompts(req: ImportRequest):
    target = Path(req.path).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=400, detail="Not a valid directory")

    imported = []
    for item in sorted(target.iterdir()):
        if not item.is_file():
            continue
        if item.suffix.lower() not in (".md", ".txt"):
            continue
        try:
            content = item.read_text(encoding="utf-8")
            cfg = PromptConfig(
                id=str(uuid.uuid4()),
                name=item.stem,
                content=content,
            )
            if state_manager.get_prompt(cfg.id):
                continue
            state_manager.add_prompt(cfg)
            imported.append(cfg.name)
        except Exception:
            continue

    return {"imported": len(imported)}
