from fastapi import APIRouter, HTTPException

from backend.state import state_manager
from backend.schemas import ModelConfig, ModelTestRequest
from BBagent.core.model import Model, Model_Input
from BBagent.core.message import TextBlock, HumanMessage

router = APIRouter()


@router.get("")
async def list_models():
    return [m.model_dump(mode="json") for m in state_manager.models]


@router.post("")
async def create_model(config: ModelConfig):
    if state_manager.get_model(config.id):
        raise HTTPException(status_code=400, detail=f"Model with id '{config.id}' already exists")
    state_manager.add_model(config)
    return config.model_dump(mode="json")


@router.put("/{model_id}")
async def update_model(model_id: str, updates: dict):
    updated = state_manager.update_model(model_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Model not found")
    return updated.model_dump(mode="json")


@router.delete("/{model_id}")
async def delete_model(model_id: str):
    if not state_manager.delete_model(model_id):
        raise HTTPException(status_code=404, detail="Model not found")
    return {"success": True}


@router.post("/{model_id}/test")
async def test_model(model_id: str, req: ModelTestRequest):
    model_config = state_manager.get_model(model_id)
    if not model_config:
        raise HTTPException(status_code=404, detail="Model not found")

    config_dict = _build_model_config_dict(model_config)
    try:
        model = Model.from_config_dict(config_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to initialize model: {e}")

    human_msg = HumanMessage(content=req.prompt)
    model_input = Model_Input(messages=[human_msg])
    try:
        response = await model.async_invoke(model_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    content = _extract_text_content(response)
    return {"content": content}


def _build_model_config_dict(model_config: ModelConfig) -> dict:
    base = {
        "provider": model_config.provider,
        "model": model_config.modelName,
        "api_key": model_config.apiKey,
        "base_url": model_config.baseUrl,
        "max_context_tokens": model_config.maxContextTokens,
        "temperature": model_config.temperature,
        "top_p": model_config.topP,
    }
    if model_config.thinking:
        base["thinking"] = model_config.thinking
    if model_config.provider == "anthropic":
        base["max_tokens"] = model_config.maxCompletionTokens
    else:
        base["max_completion_tokens"] = model_config.maxCompletionTokens
    return base


def _extract_text_content(response) -> str:
    if hasattr(response, "content"):
        content = response.content
    else:
        content = response
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
