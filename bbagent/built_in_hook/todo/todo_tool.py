from pydantic import BaseModel, Field

from ...core.tool import Tool
from .runtime import TodoRuntime
from .todo import TodoItemInput, TodoManager, TodoStatus


class TodoItemInputModel(BaseModel):
    id: str = Field(description="Short stable id for this item, unique within the todo list.")
    content: str = Field(description="The concrete task to complete. Include all useful task detail here.")
    blocked_by: list[str] = Field(
        default_factory=list,
        description="Ids of items in the same list that must be done or cancelled before this item can start.",
    )


TODO_CREATE_DESCRIPTION = """Create a runtime todo list for the current multi-step task.

Use this before substantial work that benefits from explicit progress tracking.

Input fields:
- `title`: short name for the overall task or work plan.
- `items`: complete list of todo items to track.
- `items[].id`: short, stable, unique id within this list; use simple ids like `inspect`, `implement`, `test`.
- `items[].content`: the actual work item. Put the full actionable task text here.
- `items[].blocked_by`: ids of items in this same list that must finish before this item is ready.

Do not create placeholder items. Do not put dependency explanations in `blocked_by`; it accepts item ids only."""

TODO_UPDATE_DESCRIPTION = """Update one item in the active runtime todo list.

Use this as work starts, completes, is cancelled, or dependencies change. Valid statuses are:
pending, in_progress, blocked, done, cancelled."""

TODO_LIST_DESCRIPTION = "Show the active runtime todo list grouped by progress and dependency readiness."
TODO_CLEAR_DESCRIPTION = "Clear the active runtime todo list."


def _mark_if_changed(result, runtime: TodoRuntime) -> None:
    if result.changed:
        runtime.mark_dirty()


def _format_current_state(manager: TodoManager) -> str:
    formatted = manager.format_for_model()
    return formatted if formatted else "No active todo list."


def _tool_response(message: str, manager: TodoManager, runtime: TodoRuntime) -> str:
    runtime.mark_status_shown()
    return f"{message}\n\n{_format_current_state(manager)}"


def create_todo_tools(manager: TodoManager, runtime: TodoRuntime) -> list[Tool]:
    async def todo_create(title: str, items: list[TodoItemInputModel]) -> str:
        item_inputs = [
            TodoItemInput(
                id=item.id,
                content=item.content,
                blocked_by=list(item.blocked_by),
            )
            for item in items
        ]
        result = manager.create_list(title, item_inputs)
        _mark_if_changed(result, runtime)
        return _tool_response(result.message, manager, runtime)

    async def todo_update(
        item_id: str,
        status: TodoStatus | None = None,
        content: str | None = None,
        blocked_by: list[str] | None = None,
    ) -> str:
        result = manager.update_item(
            item_id=item_id,
            status=status,
            content=content,
            blocked_by=blocked_by,
        )
        _mark_if_changed(result, runtime)
        return _tool_response(result.message, manager, runtime)

    async def todo_list() -> str:
        runtime.mark_status_shown()
        return _format_current_state(manager)

    async def todo_clear(reason: str = "") -> str:
        result = manager.clear(reason)
        _mark_if_changed(result, runtime)
        return _tool_response(result.message, manager, runtime)

    return [
        Tool(todo_create, name="todo_create", description=TODO_CREATE_DESCRIPTION, source="hook"),
        Tool(todo_update, name="todo_update", description=TODO_UPDATE_DESCRIPTION, source="hook"),
        Tool(todo_list, name="todo_list", description=TODO_LIST_DESCRIPTION, source="hook"),
        Tool(todo_clear, name="todo_clear", description=TODO_CLEAR_DESCRIPTION, source="hook"),
    ]
