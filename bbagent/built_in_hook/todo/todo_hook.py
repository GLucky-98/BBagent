from ...core.hook import HookContext
from .runtime import TodoRuntime
from .todo import TodoManager

TODO_CONTEXT_START = "[Current Todo List]"
TODO_CONTEXT_END = "[End Current Todo List]"


def _format_todo_context(manager: TodoManager) -> str:
    formatted = manager.format_for_model()
    if not formatted:
        return ""
    return f"{formatted}\n{TODO_CONTEXT_END}"


def create_todo_hook(
    manager: TodoManager,
    runtime: TodoRuntime,
    stream_inject_interval: int = 1,
):
    def todo_context_provider() -> str:
        return _format_todo_context(manager)

    async def inject_after_input(ctx: HookContext):
        runtime.mark_injected()

    async def remind_before_stream(ctx: HookContext):
        runtime.tick_stream()
        if (
            runtime.last_injected_version == runtime.version
            and runtime.stream_count_since_inject < max(1, stream_inject_interval)
        ):
            return
        runtime.mark_injected()

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
        runtime.last_injected_version = -1
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
        inject_after_input,
        remind_before_stream,
        emit_on_tool_result,
        clear_on_new_session,
        cleanup_after_run,
        todo_context_provider,
    )
