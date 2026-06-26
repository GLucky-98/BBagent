from fastapi import APIRouter, HTTPException

from backend.schemas import ModelConfig, ModelTestRequest
from backend.state import state_manager
from bbagent.core.message import HumanMessage, TextBlock
from bbagent.core.model import Model, Model_Input

router = APIRouter()


@router.get("")
async def list_models():
    return [m.model_dump(mode="json") for m in state_manager.model_factory.list_all()]


@router.post("")
async def create_model(config: ModelConfig):
    if state_manager.get_model(config.id):
        raise HTTPException(status_code=400, detail=f"Model with id '{config.id}' already exists")
    state_manager.add_model(config)
    return config.model_dump(mode="json")


@router.put("/{model_id}")
async def update_model(model_id: str, updates: dict):
    updated, affected = await state_manager.update_model_and_invalidate(
        model_id, updates
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Model not found")
    return {
        **updated.model_dump(mode="json"),
        "affectedAgents": affected,
    }


@router.delete("/{model_id}")
async def delete_model(model_id: str):
    ok, affected = await state_manager.delete_model_and_invalidate(model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"success": True, "affectedAgents": affected}


@router.post("/{model_id}/test")
async def test_model(model_id: str, req: ModelTestRequest):
    model_config = state_manager.get_model(model_id)
    if not model_config:
        raise HTTPException(status_code=404, detail="Model not found")

    try:
        model = Model.from_config_dict(model_config.core_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to initialize model: {e}") from None

    human_msg = HumanMessage(content=req.prompt)
    model_input = Model_Input(messages=[human_msg])
    try:
        response = model.invoke(model_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None

    content = _extract_text_content(response)
    return {"content": content}


def _extract_text_content(response) -> str:
    content = response.content if hasattr(response, "content") else response
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, TextBlock):
                parts.append(block.text)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return str(content)
