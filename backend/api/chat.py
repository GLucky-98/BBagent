import asyncio
import base64
import contextlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.attachments import FileStore
from backend.logging import get_backend_logger
from backend.state import DATA_DIR, state_manager
from bbagent.core.message import ContentBlock, ImageBlock, TextBlock

logger = get_backend_logger("api.chat")

router = APIRouter()
_file_store = FileStore(DATA_DIR / "attachments")

_SWITCH = object()   # sentinel: wake forwarder to re-read queue holder
_STOP = object()     # sentinel: stop forwarder


class _QueueHolder:
    """Mutable holder so forwarder can pick up new queue after switch."""

    def __init__(self):
        self.queue: asyncio.Queue | None = None


def _resolve_chat_agent(agent_id: str) -> str | None:
    """Validate an agent_id from a chat WS message. Returns the id if
    present in state_manager.agent_factory.agents, else None.
    """
    if agent_id in state_manager.agent_factory.agents:
        return agent_id
    return None


def _collect_owned_files(agent_id: str, files: object) -> list[dict]:
    owned = []
    if isinstance(files, list):
        for raw in files:
            if not isinstance(raw, dict):
                continue
            path = str(raw.get("path") or "")
            if not path or not _file_store.is_owned_file(agent_id, path):
                continue
            file_id = str(raw.get("id") or "")
            if not file_id:
                continue
            name = str(raw.get("originalName") or raw.get("storedName") or "file")
            content_type = str(raw.get("contentType") or "application/octet-stream")
            size = raw.get("size")
            owned.append({
                "id": file_id,
                "name": name,
                "path": path,
                "content_type": content_type,
                "size": size,
            })
    return owned


def _format_file_text(content: str, owned_files: list[dict]) -> str:
    content = content.strip()
    if not owned_files:
        return content
    if not content:
        content = "Please review the uploaded file(s)."

    image_lines = []
    file_lines = []
    for item in owned_files:
        size = item.get("size")
        size_label = f", {size} bytes" if isinstance(size, int) else ""
        file_id = item["id"]
        name = item["name"]
        content_type = item["content_type"]
        if str(content_type).lower().startswith("image/"):
            image_lines.append(f"- {name}: file_id={file_id} ({content_type}{size_label})")
        else:
            file_lines.append(f"- {name}: file_id={file_id} ({content_type}{size_label})")

    lines = [content, "", "[Files]"]
    if image_lines:
        lines.extend([
            "Image files are included directly in this message as model-visible image input:",
            *image_lines,
        ])
    if file_lines:
        if image_lines:
            lines.append("")
        lines.extend([
            "These files were uploaded by the user and copied into managed local storage. "
            "Use the read_file tool with file_id when you need to inspect their text content:",
            *file_lines,
        ])
    return "\n".join(lines)


def _format_user_message(agent_id: str, content: str, attachments: object) -> str:
    return _format_file_text(content, _collect_owned_files(agent_id, attachments))


def _build_user_content(agent_id: str, content: str, attachments: object) -> str | list[ContentBlock]:
    owned_files = _collect_owned_files(agent_id, attachments)
    text = _format_file_text(content, owned_files)
    image_blocks: list[ImageBlock] = []

    for item in owned_files:
        content_type = str(item["content_type"])
        if not content_type.lower().startswith("image/"):
            continue
        try:
            image_data = base64.b64encode(Path(item["path"]).read_bytes()).decode("ascii")
        except OSError as exc:
            logger.warning(f"Failed to read uploaded image file: {exc}")
            continue
        image_blocks.append(ImageBlock(data=image_data, image_type=content_type, origin="user"))

    if not image_blocks:
        return text
    return (
        [TextBlock(text=text, origin="user"), *image_blocks]
        if text
        else image_blocks
    )


@router.websocket("/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()

    holder = _QueueHolder()
    current_agent_id: str | None = None
    subscriber_id = f"ws:{uuid4().hex[:8]}"
    switch_lock = asyncio.Lock()

    # Subscribe to global dispatcher for cross-agent state updates.
    # This subscription persists for the lifetime of the WS connection
    # so we always receive agent_state events for every agent.
    global_sub_id = f"global:{uuid4().hex[:8]}"
    global_q = state_manager.global_dispatcher.subscribe(global_sub_id)

    async def subscribe_to(agent_id: str) -> bool:
        """
        Atomically switch subscription to a new agent.

        IMPORTANT: validate the new agent BEFORE unsubscribing from the old one.
        If validation fails, the caller's subscription is left intact.
        """
        nonlocal current_agent_id

        # 1. Validate new agent FIRST (fail-fast, don't touch old subscription)
        if _resolve_chat_agent(agent_id) is None:
            await websocket.send_json({
                "type": "error",
                "content": f"Agent '{agent_id}' not found"
            })
            return False
        new_disp = state_manager.get_agent_dispatcher(agent_id)
        if not new_disp:
            await websocket.send_json({
                "type": "error",
                "content": f"Dispatcher not found for agent '{agent_id}'"
            })
            return False

        # 2. Unsubscribe from old (if any) — push sentinel to wake forwarder
        if current_agent_id:
            old_disp = state_manager.get_agent_dispatcher(current_agent_id)
            if old_disp:
                old_disp.unsubscribe(subscriber_id)
            if holder.queue is not None:
                holder.queue.put_nowait(_SWITCH)

        # 3. Subscribe to new
        holder.queue = new_disp.subscribe(subscriber_id, replay=True)
        current_agent_id = agent_id
        agent = state_manager.agent_factory.agents[agent_id]
        context_tokens = agent.session.get_visible_token_count() if agent.session else 0
        await websocket.send_json({
            "type": "switched",
            "agent_id": agent_id,
            "agent_name": agent.name,
            "agent_state": agent.state,
            "context_tokens": context_tokens,
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

    async def global_forwarder():
        """Forward global dispatcher events (agent_state) to WS client."""
        while True:
            try:
                chunk = await global_q.get()
            except Exception:
                break
            if chunk is _STOP:
                break
            try:
                await websocket.send_json(chunk)
            except Exception as e:
                logger.error(f"global_forwarder send_json failed: {e}")
                break

    async def receiver():
        """Read WS messages, dispatch to agent."""
        try:
            async for msg in websocket.iter_json():
                msg_type = msg.get("type")

                if msg_type == "switch_agent":
                    async with switch_lock:
                        # unified-id: messages carry agent_id (UUID).
                        ref = msg.get("agent_id") or msg.get("agent_name")
                        if ref:
                            await subscribe_to(ref)

                elif msg_type == "user_message":
                    agent = (
                        state_manager.agent_factory.agents.get(current_agent_id)
                        if current_agent_id else None
                    )
                    if agent:
                        source_id = msg.get("message_id") or "user"
                        content = _build_user_content(
                            current_agent_id,
                            str(msg.get("content") or ""),
                            msg.get("attachments", []),
                        )
                        if msg.get("attachments"):
                            await state_manager.agent_factory.ensure_builtin_tool_runtime(
                                current_agent_id,
                                "read_file",
                            )
                        if content:
                            agent.input.push(content, source_id=source_id)

                elif msg_type == "interrupt":
                    agent = (
                        state_manager.agent_factory.agents.get(current_agent_id)
                        if current_agent_id else None
                    )
                    if agent:
                        await agent.interrupt()

        except WebSocketDisconnect:
            pass

    forwarder_task = asyncio.create_task(forwarder())
    global_forwarder_task = asyncio.create_task(global_forwarder())

    try:
        await receiver()
    finally:
        # Push stop sentinel to unblock forwarders, then await them
        if holder.queue is not None:
            holder.queue.put_nowait(_STOP)
        global_q.put_nowait(_STOP)
        forwarder_task.cancel()
        global_forwarder_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await forwarder_task
        with contextlib.suppress(asyncio.CancelledError):
            await global_forwarder_task

        # Unsubscribe from per-agent dispatcher
        if current_agent_id:
            disp = state_manager.get_agent_dispatcher(current_agent_id)
            if disp:
                disp.unsubscribe(subscriber_id)
        # Unsubscribe from global dispatcher
        state_manager.global_dispatcher.unsubscribe(global_sub_id)
