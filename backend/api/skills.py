from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.logging import get_backend_logger
from backend.state import state_manager

logger = get_backend_logger("api.skills")


class ImportRequest(BaseModel):
    path: str


router = APIRouter()


@router.get("")
async def list_skills():
    return [s.model_dump(mode="json") for s in state_manager.list_skills()]


@router.post("/import")
def import_skills(req: ImportRequest):
    target = Path(req.path).expanduser().resolve()
    if not target.exists():
        raise HTTPException(status_code=400, detail="Path does not exist")

    if target.is_dir() or (target.is_file() and target.name.lower() == "skill.md"):
        import_path = target
    else:
        raise HTTPException(status_code=400, detail="Not a valid skill path (must be SKILL.md file or directory)")

    logger.info(f"Importing skills from: {import_path}")
    added, skipped = state_manager.import_skills_from_dir(import_path)

    for item in added:
        logger.info(f"  [imported] {item.name}")
    for item in skipped:
        logger.info(f"  [skipped] {item} (already exists)")

    result = {
        "success": True,
        "imported": len(added),
        "skipped": len(skipped),
        "items": [s.name for s in added],
        "skipped_items": skipped,
    }
    logger.info(f"Skills import complete: {result['imported']} imported, {result['skipped']} skipped")
    return result


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    if not state_manager.delete_skill(skill_id):
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"success": True}


@router.post("/{skill_id}/refresh")
async def refresh_skill(skill_id: str):
    config = state_manager.refresh_skill(skill_id)
    if not config:
        raise HTTPException(status_code=404, detail="Skill not found")
    return config.model_dump(mode="json")
