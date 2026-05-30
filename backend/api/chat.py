import asyncio
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.state import state_manager

router = APIRouter()


@router.websocket("/chat/{agent_name}")
async def chat_ws(websocket: WebSocket, agent_name: str):
    await websocket.accept()

    agent = state_manager.agents.get(agent_name)
    if not agent:
        await websocket.close(code=4004, reason="Agent not found")
        return

    dispatcher = state_manager.get_agent_dispatcher(agent_name)
    if not dispatcher:
        await websocket.close(code=4005, reason="Agent dispatcher not found")
        return

    subscriber_id = f"{agent_name}:{uuid4().hex[:8]}"
    queue = dispatcher.subscribe(subscriber_id)

    async def forwarder():
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                try:
                    await websocket.send_json(chunk)
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    async def receiver():
        try:
            async for msg in websocket.iter_json():
                msg_type = msg.get("type")
                if msg_type == "interrupt":
                    await agent.interrupt()
                elif msg_type == "user_message":
                    agent.input.push(msg.get("content", ""))
        except WebSocketDisconnect:
            pass

    forwarder_task = asyncio.create_task(forwarder())

    try:
        await receiver()
    finally:
        forwarder_task.cancel()
        try:
            await forwarder_task
        except asyncio.CancelledError:
            pass
        dispatcher.unsubscribe(subscriber_id)
