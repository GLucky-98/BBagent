import asyncio
from collections.abc import Callable
from copy import copy
from dataclasses import dataclass
from enum import Enum
from typing import Any


class HookType(Enum):
    BEFORE_RUN = "before_run"
    AFTER_INPUT = "after_input"

    BEFORE_STREAM = "before_stream"

    ON_TEXT_CHUNK = "on_text_chunk"
    ON_THINKING_CHUNK = "on_thinking_chunk"
    ON_TOOL_USE = "on_tool_use"
    ON_TOOL_RESULT = "on_tool_result"
    ON_MESSAGE = "on_message"

    ON_ERROR = "on_error"

    AFTER_RUN = "after_run"

    NEW_SESSION = "new_session"


class HookContext:
    """Data bridge between Hook and Agent"""

    def __init__(self):
        self.agent = None
        self.data: dict[str, Any] = {}

    def set(self, key: str, value: Any):
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


@dataclass
class Hook:
    hook_type: HookType
    handler: Callable
    priority: int = 100
    name: str = None
    critical: bool = False

    def __post_init__(self):
        if self.name is None:
            self.name = getattr(self.handler, '__name__', str(self.handler))

    async def execute(self, context: HookContext, *args, **kwargs) -> Any:
        agent = context.agent
        span_name = f"hook_{self.name}"
        with agent.logger.span(span_name):
            try:
                if asyncio.iscoroutinefunction(self.handler):
                    return await self.handler(context, *args, **kwargs)
                else:
                    return self.handler(context, *args, **kwargs)
            except Exception as e:
                agent.logger.warning(
                    f"Hook '{self.name}' execution failed: {e}",
                    context={"hook_type": self.hook_type.value, "hook_name": self.name}
                )
                if self.hook_type != HookType.ON_ERROR:
                    await agent.hook.trigger(HookType.ON_ERROR, e)
                if self.critical:
                    raise
                return None


class AgentHook:
    DEFAULT_PRIORITY = 150

    def __init__(self):
        self._hooks: dict[HookType, list[Hook]] = {
            hook_type: [] for hook_type in HookType
        }
        self._context: HookContext | None = None
        self._enabled = True

    @property
    def context(self) -> HookContext:
        if self._context is None:
            self._context = HookContext()
        return self._context

    def set_context(self, agent):
        self.context.agent = agent

    def hook(self, hook_type: HookType, priority: int | None = None, critical: bool = False):
        """Decorator: register Hook"""
        if priority is None:
            priority = self.DEFAULT_PRIORITY

        def decorator(func: Callable) -> Callable:
            h = Hook(
                hook_type=hook_type,
                handler=func,
                priority=priority,
                name=getattr(func, '__name__', str(func)),
                critical=critical,
            )
            self._register(h)
            return func
        return decorator

    def register(self, hook_type: HookType, func: Callable,
                 priority: int | None = None, critical: bool = False):
        """Register Hook via function"""
        if priority is None:
            priority = self.DEFAULT_PRIORITY

        h = Hook(
            hook_type=hook_type,
            handler=func,
            priority=priority,
            critical=critical,
        )
        self._register(h)

    def unregister(self, hook_type: HookType, name: str | None = None):
        """Unregister Hook, if name not specified unregister all Hooks of that type"""
        if name is None:
            self._hooks[hook_type] = []
        else:
            self._hooks[hook_type] = [
                h for h in self._hooks[hook_type]
                if h.name != name
            ]

    def _register(self, hook: Hook):
        self._hooks[hook.hook_type].append(hook)
        self._hooks[hook.hook_type].sort(key=lambda h: h.priority)

    async def trigger(self, hook_type: HookType, *args, **kwargs):
        if not self._enabled:
            return

        for hook in self._hooks[hook_type]:
            await hook.execute(self.context, *args, **kwargs)

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    def list_hooks(self) -> dict[HookType, list[str]]:
        return {
            hook_type: [h.name for h in hooks]
            for hook_type, hooks in self._hooks.items()
            if hooks
        }

    def clear(self):
        for hook_type in self._hooks:
            self._hooks[hook_type] = []
        self._context = None

    def merge(self, *others: 'AgentHook'):
        for other in others:
            for hook_type, hooks in other._hooks.items():
                for hook in hooks:
                    new_hook = copy(hook)
                    existing = {h.priority for h in self._hooks[hook_type]}
                    while new_hook.priority in existing:
                        new_hook.priority += 1
                    self._register(new_hook)
