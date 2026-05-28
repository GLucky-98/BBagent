from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.state import state_manager
from BBagent.core.message import HumanMessage

router = APIRouter()


@router.websocket("/chat/{agent_name}")
async def chat_ws(websocket: WebSocket, agent_name: str):
    await websocket.accept()
    agent = state_manager.agents.get(agent_name)
    if not agent:
        await websocket.close(code=4004, reason="Agent not found")
        return

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")
            if msg_type == "user_message":
                content = msg.get("content", "")
                human_msg = HumanMessage(content=content)
                async for chunk in agent.run(human_msg):
                    await websocket.send_json(chunk)
            elif msg_type == "interrupt":
                await agent.interrupt()
                await websocket.send_json({"type": "interrupted", "content": "Agent interrupted"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "content": str(e)})
