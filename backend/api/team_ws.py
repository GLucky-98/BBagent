import asyncio
import re
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.state import state_manager

router = APIRouter()

MENTION_RE = re.compile(r"^@([a-zA-Z0-9_]+)")


def _resolve_team_ws(team_id: str) -> str | None:
    """Resolve a WS path param (team_id) to the team_id. Returns
    None if not found.
    """
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
    subscriber_id = f"team:{team_id}:{uuid4().hex[:8]}"
    member_queues: dict[str, asyncio.Queue] = {}

    for member_name, member_agent in team.agents.items():
        # Find this member's agent_id by identity match
        agent_id = next(
            (i for i, a in state_manager.agent_factory.agents.items() if a is member_agent),
            None,
        )
        if agent_id is None:
            continue
        dispatcher = state_manager.get_agent_dispatcher(agent_id)
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
                            source_id=f"team:{team_id}:user",
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
        for member_name, member_agent in team.agents.items():
            agent_id = next(
                (i for i, a in state_manager.agent_factory.agents.items() if a is member_agent),
                None,
            )
            if agent_id is None:
                continue
            dispatcher = state_manager.get_agent_dispatcher(agent_id)
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
