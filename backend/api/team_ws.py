import re

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

    # 注册 team_message 回调，将 TeamMessage 实时推送给前端
    async def on_team_message(msg_dict: dict):
        try:
            # TeamMessage.to_dict() 中的 "type" 改名为 "msg_type" 避免和外层冲突
            inner_type = msg_dict.pop("type", None)
            payload = {"type": "team_message", **msg_dict}
            if inner_type is not None:
                payload["msg_type"] = inner_type
            await websocket.send_json(payload)
        except Exception:
            pass

    team._on_team_message = on_team_message

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
    except WebSocketDisconnect:
        pass
    finally:
        team._on_team_message = None


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
