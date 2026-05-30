import asyncio
import re
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.state import state_manager

router = APIRouter()

MENTION_RE = re.compile(r"^@([a-zA-Z0-9_]+)")


@router.websocket("/team/{team_name}")
async def team_chat_ws(websocket: WebSocket, team_name: str):
    await websocket.accept()

    team = state_manager.teams.get(team_name)
    if not team:
        await websocket.close(code=4004, reason="Team not found")
        return

    subscriber_id = f"team:{team_name}:{uuid4().hex[:8]}"
    member_queues: dict[str, asyncio.Queue] = {}

    for member_name in team.agents:
        dispatcher = state_manager.get_agent_dispatcher(member_name)
        if dispatcher:
            q = dispatcher.subscribe(f"{subscriber_id}:{member_name}")
            member_queues[member_name] = q

    async def forwarder():
        merge_tasks = []
        try:
            for member_name, q in member_queues.items():
                merge_tasks.append(_forward_member(websocket, member_name, q))
            if merge_tasks:
                await asyncio.gather(*merge_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass

    async def _forward_member(ws: WebSocket, member_name: str, q: asyncio.Queue):
        try:
            while True:
                chunk = await q.get()
                if chunk is None:
                    break
                chunk["source_agent"] = member_name
                try:
                    await ws.send_json(chunk)
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    forwarder_task = asyncio.create_task(forwarder())

    try:
        async for msg in websocket.iter_json():
            msg_type = msg.get("type")
            if msg_type != "user_message":
                continue

            content = msg.get("content", "")
            mentions = msg.get("mentions", [])

            if not mentions:
                mentions = _parse_mentions(content)

            if mentions:
                stripped_content = content
                for m in mentions:
                    stripped_content = re.sub(rf"^@\s*{m}\s*", "", stripped_content, count=1)
                for member_name in mentions:
                    member_agent = team.agents.get(member_name)
                    if member_agent:
                        member_agent.input.push(
                            stripped_content.strip(),
                            source_id=f"team:{team_name}:user",
                        )
            else:
                await websocket.send_json({
                    "type": "system",
                    "content": "Use @agent_name to direct your message to a team member.",
                })
    except WebSocketDisconnect:
        pass
    finally:
        forwarder_task.cancel()
        try:
            await forwarder_task
        except asyncio.CancelledError:
            pass
        for member_name in team.agents:
            dispatcher = state_manager.get_agent_dispatcher(member_name)
            if dispatcher:
                dispatcher.unsubscribe(f"{subscriber_id}:{member_name}")


def _parse_mentions(text: str) -> list[str]:
    mentions = []
    remaining = text.strip()
    while remaining:
        m = MENTION_RE.match(remaining)
        if not m:
            break
        mentions.append(m.group(1))
        remaining = remaining[m.end():].strip()
    return mentions
