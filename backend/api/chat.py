import asyncio
import logging
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.state import state_manager

logger = logging.getLogger("chat_ws")

router = APIRouter()

_SWITCH = object()   # sentinel: wake forwarder to re-read queue holder
_STOP = object()     # sentinel: stop forwarder


class _QueueHolder:
    """Mutable holder so forwarder can pick up new queue after switch."""

    def __init__(self):
        self.queue: asyncio.Queue | None = None


@router.websocket("/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()

    holder = _QueueHolder()
    current_agent_name: str | None = None
    subscriber_id = f"global:{uuid4().hex[:8]}"
    switch_lock = asyncio.Lock()

    async def subscribe_to(agent_name: str) -> bool:
        """
        Atomically switch subscription to a new agent.

        IMPORTANT: validate the new agent BEFORE unsubscribing from the old one.
        If validation fails, the caller's subscription is left intact.
        """
        nonlocal current_agent_name

        # 1. Validate new agent FIRST (fail-fast, don't touch old subscription)
        agent = state_manager.agents.get(agent_name)
        if not agent:
            await websocket.send_json({
                "type": "error",
                "content": f"Agent '{agent_name}' not found"
            })
            return False

        new_disp = state_manager.get_agent_dispatcher(agent_name)
        if not new_disp:
            await websocket.send_json({
                "type": "error",
                "content": f"Dispatcher not found for agent '{agent_name}'"
            })
            return False

        # 2. Unsubscribe from old (if any) — push sentinel to wake forwarder
        if current_agent_name:
            old_disp = state_manager.get_agent_dispatcher(current_agent_name)
            if old_disp:
                old_disp.unsubscribe(subscriber_id)
            if holder.queue is not None:
                holder.queue.put_nowait(_SWITCH)

        # 3. Subscribe to new
        holder.queue = new_disp.subscribe(subscriber_id, replay=True)
        current_agent_name = agent_name
        await websocket.send_json({
            "type": "switched",
            "agent_name": agent_name,
            "agent_state": str(agent.state).lower(),
        })
        return True

    async def forwarder():
        """Long-lived task: read from holder.queue, forward to WS client."""
        while True:
            q = holder.queue
            if q is None:
                await asyncio.sleep(0.05)
                continue
            try:
                chunk = await q.get()
            except Exception:
                break

            if chunk is _SWITCH:
                continue          # holder.queue has been replaced, re-read
            if chunk is _STOP:
                break
            if chunk is None:
                continue

            try:
                await websocket.send_json(chunk)
            except Exception as e:
                logger.error(f"forwarder send_json failed: {e}, chunk type={chunk.get('type')}")
                break

    async def receiver():
        """Read WS messages, dispatch to agent."""
        try:
            async for msg in websocket.iter_json():
                msg_type = msg.get("type")

                if msg_type == "switch_agent":
                    async with switch_lock:
                        await subscribe_to(msg["agent_name"])

                elif msg_type == "user_message":
                    agent = (
                        state_manager.agents.get(current_agent_name)
                        if current_agent_name else None
                    )
                    if agent:
                        agent.input.push(msg["content"])

                elif msg_type == "interrupt":
                    agent = (
                        state_manager.agents.get(current_agent_name)
                        if current_agent_name else None
                    )
                    if agent:
                        await agent.interrupt()

                elif msg_type == "human_answer":
                    agent = (
                        state_manager.agents.get(current_agent_name)
                        if current_agent_name else None
                    )
                    if agent:
                        ask_tool = agent.tools.get("ask_human")
                        if ask_tool and hasattr(ask_tool, "_ask_human_state"):
                            state = ask_tool._ask_human_state
                            if state.future and not state.future.done():
                                state.future.set_result(msg["content"])
        except WebSocketDisconnect:
            pass

    forwarder_task = asyncio.create_task(forwarder())

    try:
        await receiver()
    finally:
        # Push stop sentinel to unblock forwarder, then await it
        if holder.queue is not None:
            holder.queue.put_nowait(_STOP)
        forwarder_task.cancel()
        try:
            await forwarder_task
        except asyncio.CancelledError:
            pass

        if current_agent_name:
            disp = state_manager.get_agent_dispatcher(current_agent_name)
            if disp:
                disp.unsubscribe(subscriber_id)
