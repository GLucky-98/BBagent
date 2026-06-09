"""全局 Session 管理 API。

提供跨 agent 的 session 列表、详情、fork、删除等操作。
现有 Agent 级 session API（GET /api/agents/{id}/sessions）保持不变。
"""

from fastapi import APIRouter, HTTPException, Query

from backend.state import state_manager
from backend.schemas import SessionForkRequest
from backend.errors import AppError

router = APIRouter()


@router.get("")
async def list_sessions(agent_id: str = Query(default=None)):
    """全局 session 列表，支持按 agent 过滤。"""
    return state_manager.list_all_sessions(agent_id=agent_id)


@router.get("/{session_id}")
async def get_session_detail(session_id: str):
    """session 详情 + turn 摘要列表。"""
    try:
        return await state_manager.get_session_detail(session_id)
    except AppError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{session_id}/fork")
async def fork_session(session_id: str, body: SessionForkRequest):
    """从指定 turn fork session。"""
    try:
        return await state_manager.fork_session_at_turn(
            session_id=session_id,
            turn_index=body.turnIndex,
            target_agent_id=body.targetAgentId,
        )
    except AppError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/reindex")
async def reindex_sessions():
    """重建全局 session 索引。"""
    state_manager.reindex_sessions()
    return {"ok": True}


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """删除 session（含文件清理）。"""
    try:
        return {"ok": state_manager.delete_session(session_id)}
    except AppError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
