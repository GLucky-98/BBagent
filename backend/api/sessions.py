"""Global Session management API.

Provides cross-agent session list, detail, fork, delete operations.
Existing Agent-level session API (GET /api/agents/{id}/sessions) remains unchanged.
"""

from fastapi import APIRouter, HTTPException, Query

from backend.errors import AppError
from backend.schemas import SessionForkRequest
from backend.state import state_manager

router = APIRouter()


@router.get("")
async def list_sessions(agent_id: str = Query(default=None)):
    """Global session list, supports filtering by agent."""
    return state_manager.list_all_sessions(agent_id=agent_id)


@router.get("/{session_id}")
async def get_session_detail(session_id: str):
    """session detail + turn summary list."""
    try:
        return await state_manager.get_session_detail(session_id)
    except AppError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from None


@router.post("/{session_id}/fork")
async def fork_session(session_id: str, body: SessionForkRequest):
    """Fork session from a specific turn."""
    try:
        return await state_manager.fork_session_at_turn(
            session_id=session_id,
            turn_index=body.turnIndex,
            target_agent_id=body.targetAgentId,
        )
    except AppError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from None


@router.post("/reindex")
async def reindex_sessions():
    """Rebuild global session index."""
    state_manager.reindex_sessions()
    return {"ok": True}


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete session (including file cleanup)."""
    try:
        return {"ok": state_manager.delete_session(session_id)}
    except AppError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from None
