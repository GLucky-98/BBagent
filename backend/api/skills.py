from fastapi import APIRouter

from backend.state import state_manager

router = APIRouter()


@router.get("")
async def list_skills():
    skills = state_manager.list_skills()
    return [s.model_dump(mode="json") for s in skills]
