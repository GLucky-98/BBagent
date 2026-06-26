import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.logging import get_backend_logger
from backend.schemas import PromptConfig
from backend.state import state_manager

logger = get_backend_logger("api.prompts")


class ImportRequest(BaseModel):
    path: str
    group: str = ""


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

    logger.info(f"Importing prompts from: {target}")

    imported: list[str] = []
    skipped: list[str] = []
    errors: list[dict] = []

    for item in sorted(target.iterdir()):
        if not item.is_file():
            continue
        try:
            if item.suffix.lower() == ".json":
                # PromptConfig JSON — full fidelity import
                data = json.loads(item.read_text(encoding="utf-8"))
                cfg = PromptConfig(**data)
                # Override group if specified in request
                if req.group:
                    cfg = cfg.model_copy(update={"group": req.group})
                # Skip if same id already exists
                if state_manager.get_prompt(cfg.id):
                    skipped.append(item.stem)
                    logger.info(f"  [skipped] {item.stem} (id already exists)")
                    continue
            elif item.suffix.lower() in (".md", ".txt"):
                # Plain text — derive name/content from file
                content = item.read_text(encoding="utf-8")
                group = req.group
                # Skip if same name in same group already exists
                if any(p.name == item.stem and p.group == group for p in state_manager.prompt_factory.list_all()):
                    skipped.append(item.stem)
                    logger.info(f"  [skipped] {item.stem} (name+group already exists)")
                    continue
                cfg = PromptConfig(
                    id=str(uuid.uuid4()),
                    name=item.stem,
                    content=content,
                    group=group,
                )
            else:
                continue

            state_manager.add_prompt(cfg)
            imported.append(cfg.name)
            logger.info(f"  [imported] {cfg.name}")
        except Exception as e:
            errors.append({"file": item.name, "error": str(e)})
            logger.warning(f"  [error] {item.name}: {e}")

    result = {
        "imported": len(imported),
        "skipped": len(skipped),
        "errors": len(errors),
        "items": imported,
        "skipped_items": skipped,
        "error_items": errors,
    }
    logger.info(f"Prompt import complete: {result['imported']} imported, {result['skipped']} skipped, {result['errors']} errors")
    return result
