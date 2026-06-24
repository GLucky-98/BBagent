from typing import cast

from ...core.hook import HookContext
from ...core.message import ContentOrigin, HumanMessage, Message, TextBlock
from .runtime import TodoRuntime
from .todo import TodoManager

TODO_CONTEXT_START = "[Current Todo List]"
TODO_CONTEXT_END = "[End Current Todo List]"


def _format_todo_context(manager: TodoManager) -> str:
    formatted = manager.format_for_model()
    if not formatted:
        return ""
    return f"{formatted}\n{TODO_CONTEXT_END}"


def _default_origin_for_message(message) -> ContentOrigin:
    role = getattr(message, "role", "")
    if role in {"user", "model", "tool"}:
        return cast(ContentOrigin, role)
    return "system"


def _inject_todo_context_to_last_message(ctx: HookContext, context: str) -> bool:
    agent = ctx.agent
    session = getattr(agent, "session", None)
    if session is None or not session.turns:
        return False

    for turn in reversed(session.turns):
        if not turn.messages:
            continue
        message = turn.messages[-1]
        blocks = Message._normalize_content(message.content, _default_origin_for_message(message))
        message.content = [TextBlock(text=f"{context}\n\n", origin="system"), *blocks]
        return True

    session.add_message(HumanMessage(content=[TextBlock(text=f"{context}\n\n", origin="system")]))
    return True


def create_todo_hook(
    manager: TodoManager,
    runtime: TodoRuntime,
    stream_inject_interval: int = 1,
):
    async def remind_before_stream(ctx: HookContext):
        if manager.current() is None:
            runtime.stream_count_since_inject = 0
            return

        runtime.tick_stream()
        interval = max(0, stream_inject_interval)

        if runtime.stream_count_since_inject <= interval:
            return

        context = _format_todo_context(manager)
        if not context:
            runtime.stream_count_since_inject = 0
            return

        if _inject_todo_context_to_last_message(ctx, context):
            runtime.mark_status_shown()

    async def emit_on_tool_result(ctx: HookContext, _tool_msg):
        if not runtime.dirty:
            return
        snapshot = manager.snapshot()
        if snapshot is not None:
            await ctx.agent._emit({
                "type": "todo_list",
                "content": snapshot,
            })
        runtime.mark_emitted()

    async def clear_on_new_session(ctx: HookContext):
        if manager.current() is not None:
            manager.clear("session changed")
            runtime.mark_dirty()
        runtime.stream_count_since_inject = 0

    async def cleanup_after_run(ctx: HookContext):
        if not runtime.dirty:
            return
        snapshot = manager.snapshot()
        if snapshot is not None:
            await ctx.agent._emit({
                "type": "todo_list",
                "content": snapshot,
            })
        runtime.mark_emitted()

    return (
        remind_before_stream,
        emit_on_tool_result,
        clear_on_new_session,
        cleanup_after_run,
    )
