from fastapi import APIRouter

from backend.state import state_manager
from backend.schemas import UIState

router = APIRouter()


@router.get("")
async def get_state():
    return state_manager.ui_state.model_dump(mode="json")


@router.post("")
async def save_state(state: UIState):
    state_manager.ui_state = state
    state_manager.save_ui_state()
    return state.model_dump(mode="json")
