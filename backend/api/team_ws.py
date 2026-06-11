import asyncio
import re
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.state import state_manager

router = APIRouter()

MENTION_RE = re.compile(r"^@([a-zA-Z0-9_]+)")


def _resolve_team_ws(team_id: str) -> str | None:
    if team_id in state_manager.team_factory.teams:
        return team_id
    return None


@router.websocket("/team/{team_ref}")
async def team_chat_ws(websocket: WebSocket, team_ref: str):
    await websocket.accept()

    team_id = _resolve_team_ws(team_ref)
    if team_id is None:
        await websocket.close(code=4004, reason="Team not found")
        return

    team = state_manager.team_factory.teams[team_id]
    dispatcher = state_manager.team_factory.get_dispatcher(team_id)
    if dispatcher is None:
        await websocket.close(code=4004, reason="Team dispatcher not found")
        return

    subscriber_id = f"team_ws:{team_id}:{uuid4().hex[:8]}"
    queue = dispatcher.subscribe(subscriber_id, replay=False)

    async def forwarder():
        while True:
            chunk = await queue.get()
            await websocket.send_json(chunk)

    async def receiver():
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
                        await team.push_to_agent(
                            member_name,
                            stripped_content.strip(),
                            source="user",
                        )
            else:
                await websocket.send_json({
                    "type": "system",
                    "content": "Use @agent_name to direct your message to a team member.",
                })

    forwarder_task = asyncio.create_task(forwarder())
    receiver_task = asyncio.create_task(receiver())

    try:
        done, _ = await asyncio.wait(
            {forwarder_task, receiver_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            exc = task.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                raise exc
    except WebSocketDisconnect:
        pass
    finally:
        dispatcher.unsubscribe(subscriber_id)
        for task in (forwarder_task, receiver_task):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


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
