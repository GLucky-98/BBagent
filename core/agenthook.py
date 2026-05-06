import asyncio
from enum import Enum
from typing import Callable, Any, Dict, List, Optional
from dataclasses import dataclass


class HookControl(Enum):
    NORMAL = "normal"
    BREAK = "break"


class HookType(Enum):
    BEFORE_RUN = "before_run"
    AFTER_INPUT = "after_input"

    BEFORE_STREAM = "before_stream"

    ON_TEXT_CHUNK = "on_text_chunk"
    ON_THINKING_CHUNK = "on_thinking_chunk"

    ON_TOOL_USE = "on_tool_use"
    ON_TOOL_RESULT = "on_tool_result"

    ON_MESSAGE = "on_message"

    AFTER_RUN = "after_run"

    NEW_SESSION = "new_session"


class HookContext:
    """Hook 与 Agent 之间的数据桥梁"""

    def __init__(self):
        self.agent = None
        self.data: Dict[str, Any] = {}

    def set(self, key: str, value: Any):
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def break_loop(self):
        self.data['_control'] = HookControl.BREAK

    def get_control(self) -> HookControl:
        return self.data.get('_control', HookControl.NORMAL)

    def reset_control(self):
        self.data['_control'] = HookControl.NORMAL


@dataclass
class Hook:
    hook_type: HookType
    handler: Callable
    priority: int = 100
    name: str = None

    def __post_init__(self):
        if self.name is None:
            self.name = getattr(self.handler, '__name__', str(self.handler))

    async def execute(self, context: HookContext, *args, **kwargs) -> Any:
        try:
            if asyncio.iscoroutinefunction(self.handler):
                return await self.handler(context, *args, **kwargs)
            else:
                return self.handler(context, *args, **kwargs)
        except Exception as e:
            print(f"[Hook Error] {self.name}: {e}")
            return None


class AgentHook:
    DEFAULT_PRIORITY = 150

    def __init__(self):
        self._hooks: Dict[HookType, List[Hook]] = {
            hook_type: [] for hook_type in HookType
        }
        self._context: Optional[HookContext] = None
        self._enabled = True

    @property
    def context(self) -> HookContext:
        if self._context is None:
            self._context = HookContext()
        return self._context

    def set_context(self, agent):
        self.context.agent = agent

    def hook(self, hook_type: HookType, priority: int = None):
        """装饰器：注册 Hook"""
        if priority is None:
            priority = self.DEFAULT_PRIORITY

        def decorator(func: Callable) -> Callable:
            h = Hook(
                hook_type=hook_type,
                handler=func,
                priority=priority,
                name=getattr(func, '__name__', str(func))
            )
            self._register(h)
            return func
        return decorator

    def register(self, hook_type: HookType, func: Callable,
                 priority: int = None):
        """函数方式注册 Hook"""
        if priority is None:
            priority = self.DEFAULT_PRIORITY

        h = Hook(
            hook_type=hook_type,
            handler=func,
            priority=priority
        )
        self._register(h)

    def unregister(self, hook_type: HookType, name: str = None):
        """注销 Hook，不指定 name 则注销该类型下的所有 Hook"""
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

    def should_break(self) -> bool:
        if self.context.get_control() == HookControl.BREAK:
            self.context.reset_control()
            return True
        return False

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    def list_hooks(self) -> Dict[HookType, List[str]]:
        return {
            hook_type: [h.name for h in hooks]
            for hook_type, hooks in self._hooks.items()
            if hooks
        }

    def clear(self):
        for hook_type in self._hooks:
            self._hooks[hook_type] = []
        self._context = None
