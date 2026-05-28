from fastapi import APIRouter, HTTPException

from backend.state import state_manager
from backend.schemas import PromptConfig

router = APIRouter()


@router.get("")
async def list_prompts():
    return [p.model_dump(mode="json") for p in state_manager.prompts]


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
