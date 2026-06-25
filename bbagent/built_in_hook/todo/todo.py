from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal
from uuid import uuid4

TodoStatus = Literal["pending", "in_progress", "blocked", "done", "cancelled"]
ACTIVE_STATUSES = {"pending", "in_progress", "blocked"}
TERMINAL_STATUSES = {"done", "cancelled"}


@dataclass
class TodoItem:
    id: str
    content: str
    status: TodoStatus = "pending"
    blocked_by: list[str] = field(default_factory=list)

    def to_dict(self, terminal_ids: set[str] | None = None) -> dict:
        terminal_ids = terminal_ids or set()
        data = asdict(self)
        data["ready"] = self.status == "pending" and all(dep in terminal_ids for dep in self.blocked_by)
        return data


@dataclass
class TodoList:
    id: str
    title: str
    items: list[TodoItem]


@dataclass
class TodoItemInput:
    id: str
    content: str
    blocked_by: list[str] = field(default_factory=list)


@dataclass
class TodoMutationResult:
    changed: bool
    message: str


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


class TodoManager:
    def __init__(self):
        self._current: TodoList | None = None

    def create_list(self, title: str, items: list[TodoItemInput]) -> TodoMutationResult:
        if not title.strip():
            return TodoMutationResult(False, "Todo list title must not be empty.")
        if not items:
            return TodoMutationResult(False, "Todo list must contain at least one item.")

        todo_items = [
            TodoItem(
                id=item.id.strip(),
                content=item.content.strip(),
                blocked_by=_dedupe([dep.strip() for dep in item.blocked_by if dep.strip()]),
            )
            for item in items
        ]

        error = self._validate_items(todo_items)
        if error:
            return TodoMutationResult(False, error)

        todo_list = TodoList(
            id=f"todo-{uuid4().hex[:12]}",
            title=title.strip(),
            items=todo_items,
        )
        self._current = todo_list
        self._recalculate_blocked_items()
        return TodoMutationResult(True, f"Created todo list '{todo_list.title}' with {len(todo_items)} items.")

    def update_item(
        self,
        item_id: str,
        status: TodoStatus | None = None,
        content: str | None = None,
        blocked_by: list[str] | None = None,
    ) -> TodoMutationResult:
        if self._current is None:
            return TodoMutationResult(False, "No active todo list. Use todo_create first.")

        item = self._find_item(item_id)
        if item is None:
            return TodoMutationResult(False, f"Todo item not found: {item_id}")

        if status is not None and status not in ACTIVE_STATUSES | TERMINAL_STATUSES:
            return TodoMutationResult(False, f"Invalid todo status: {status}")

        candidate_items = [
            TodoItem(
                id=existing.id,
                content=existing.content,
                status=existing.status,
                blocked_by=list(existing.blocked_by),
            )
            for existing in self._current.items
        ]
        candidate = next(existing for existing in candidate_items if existing.id == item.id)

        if content is not None:
            candidate.content = content.strip()
        if blocked_by is not None:
            candidate.blocked_by = _dedupe([dep.strip() for dep in blocked_by if dep.strip()])
        if status is not None:
            candidate.status = status

        error = self._validate_items(candidate_items)
        if error:
            return TodoMutationResult(False, error)

        unresolved = self._unresolved_dependencies(candidate, candidate_items)
        if candidate.status == "in_progress" and unresolved:
            return TodoMutationResult(
                False,
                f"Todo item '{item.id}' is blocked by unfinished items: {', '.join(unresolved)}.",
            )

        if content is not None:
            item.content = candidate.content
        if blocked_by is not None:
            item.blocked_by = candidate.blocked_by
        if status is not None:
            item.status = candidate.status

        self._recalculate_blocked_items()

        if self._is_complete():
            self._current = None
            return TodoMutationResult(True, f"Updated todo item '{item_id}'.\nTodo list completed and cleared.")

        return TodoMutationResult(True, f"Updated todo item '{item_id}'.")

    def clear(self, reason: str = "") -> TodoMutationResult:
        if self._current is None:
            return TodoMutationResult(False, "No active todo list.")
        self._current = None
        message = "Cleared active todo list."
        if reason.strip():
            message += f" Reason: {reason.strip()}"
        return TodoMutationResult(True, message)

    def current(self) -> TodoList | None:
        return self._current

    def snapshot(self) -> dict | None:
        if self._current is None:
            return None

        terminal_ids = {item.id for item in self._current.items if item.status in TERMINAL_STATUSES}
        data = asdict(self._current)
        data["items"] = [item.to_dict(terminal_ids) for item in self._current.items]
        data["summary"] = {
            status: sum(1 for item in self._current.items if item.status == status)
            for status in ["pending", "in_progress", "blocked", "done", "cancelled"]
        }
        return data

    def format_for_model(self) -> str:
        if self._current is None:
            return ""

        groups = {
            "In progress": [item for item in self._current.items if item.status == "in_progress"],
            "Ready to work on": [
                item
                for item in self._current.items
                if item.status == "pending" and not self._unresolved_dependencies(item)
            ],
            "Blocked": [item for item in self._current.items if item.status == "blocked"],
            "Completed in this list": [
                item for item in self._current.items if item.status in TERMINAL_STATUSES
            ],
        }
        lines = [
            "[Current Todo List]",
            f"Title: {self._current.title}",
            "",
        ]
        for label, items in groups.items():
            if not items:
                continue
            lines.append(f"{label}:")
            for item in items:
                lines.append(f"- {item.id}: {item.content}")
                if item.blocked_by:
                    lines.append(f"  blocked_by: {', '.join(item.blocked_by)}")
            lines.append("")
        return "\n".join(lines).strip()

    def _find_item(self, item_id: str) -> TodoItem | None:
        if self._current is None:
            return None
        for item in self._current.items:
            if item.id == item_id:
                return item
        return None

    def _validate_items(self, items: list[TodoItem]) -> str:
        ids = [item.id for item in items]
        if any(not item_id for item_id in ids):
            return "Todo item ids must not be empty."
        if len(set(ids)) != len(ids):
            return "Todo item ids must be unique."
        if any(not item.content for item in items):
            return "Todo item content must not be empty."

        id_set = set(ids)
        for item in items:
            missing = [dep for dep in item.blocked_by if dep not in id_set]
            if missing:
                return f"Todo item '{item.id}' has unknown dependencies: {', '.join(missing)}."
            if item.id in item.blocked_by:
                return f"Todo item '{item.id}' cannot be blocked by itself."

        cycle = self._find_cycle(items)
        if cycle:
            return f"Todo dependencies contain a cycle: {' -> '.join(cycle)}."
        return ""

    def _find_cycle(self, items: list[TodoItem]) -> list[str]:
        graph = {item.id: item.blocked_by for item in items}
        visiting: set[str] = set()
        visited: set[str] = set()
        path: list[str] = []

        def visit(node: str) -> list[str]:
            if node in visiting:
                start = path.index(node)
                return [*path[start:], node]
            if node in visited:
                return []
            visiting.add(node)
            path.append(node)
            for dep in graph[node]:
                cycle = visit(dep)
                if cycle:
                    return cycle
            path.pop()
            visiting.remove(node)
            visited.add(node)
            return []

        for node in graph:
            cycle = visit(node)
            if cycle:
                return cycle
        return []

    def _unresolved_dependencies(
        self,
        item: TodoItem,
        items: list[TodoItem] | None = None,
    ) -> list[str]:
        items = items if items is not None else (self._current.items if self._current else [])
        by_id = {existing.id: existing for existing in items}
        return [
            dep_id
            for dep_id in item.blocked_by
            if by_id[dep_id].status not in TERMINAL_STATUSES
        ]

    def _recalculate_blocked_items(self) -> None:
        if self._current is None:
            return
        for item in self._current.items:
            if item.status in TERMINAL_STATUSES:
                continue
            unresolved = self._unresolved_dependencies(item)
            if unresolved and item.status != "blocked":
                item.status = "blocked"
            elif not unresolved and item.status == "blocked" and item.blocked_by:
                item.status = "pending"

    def _is_complete(self) -> bool:
        if self._current is None:
            return False
        return all(item.status in TERMINAL_STATUSES for item in self._current.items)
