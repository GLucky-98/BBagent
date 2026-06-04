from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.state import state_manager
from backend.schemas import SkillConfig


class ImportRequest(BaseModel):
    path: str


router = APIRouter()


@router.get("")
async def list_skills():
    return [s.model_dump(mode="json") for s in state_manager.list_skills()]


@router.post("/import")
async def import_skills(req: ImportRequest):
    target = Path(req.path).expanduser().resolve()
    if not target.exists():
        raise HTTPException(status_code=400, detail="Path does not exist")

    if target.is_file() and target.suffix.lower() == ".md":
        state_manager.save_imported_skills_dirs(target.parent)
    elif target.is_dir():
        state_manager.save_imported_skills_dirs(target)
    else:
        raise HTTPException(status_code=400, detail="Not a valid skill path (must be .md file or directory)")

    return {"success": True}
