from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from BBagent.core.skill import scan_skills

from backend.state import state_manager


class ImportRequest(BaseModel):
    path: str


router = APIRouter()


@router.get("")
async def list_skills():
    skills = state_manager.list_skills()
    return [s.model_dump(mode="json") for s in skills]


@router.post("/import")
async def import_skills(req: ImportRequest):
    target = Path(req.path).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=400, detail="Not a valid directory")

    imported = []
    try:
        imported_skills = scan_skills(target)
        for name, skill in imported_skills.items():
            if name in state_manager.skills:
                continue
            state_manager.skills[name] = skill
            imported.append(name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if imported:
        state_manager.save_imported_skills_dirs(target)

    skills_list = state_manager.list_skills()
    imported_configs = [s for s in skills_list if s.name in imported]
    return {"imported": len(imported), "skills": imported_configs}
