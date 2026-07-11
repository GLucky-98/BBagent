from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.attachments import FileStore
from backend.state import DATA_DIR, state_manager

router = APIRouter()

_store = FileStore(DATA_DIR / "attachments")


def _resolve_agent(agent_id: str) -> None:
    if agent_id not in state_manager.agent_factory.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")


@router.post("/{agent_id}")
async def upload_attachments(
    agent_id: str,
    files: list[UploadFile] = File(...),
):
    _resolve_agent(agent_id)
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    saved = []
    for file in files:
        uploaded_file = await _store.save(agent_id, file)
        saved.append(uploaded_file.to_api_dict())
    return saved
