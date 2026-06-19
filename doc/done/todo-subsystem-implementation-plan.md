# Todo 子系统实现方案

## 背景

当前 Agent 在执行长程任务时，缺少一个显式的任务规划和进度跟踪机制。模型可以在自然语言里描述计划，但这些计划没有结构化状态，也不会在工具循环中稳定提醒模型继续按计划推进。

本文档整理一个完整的 Todo 子系统方案。目标是让 Agent 能在复杂任务开始前创建 todo list，在执行过程中更新 todo item 状态，并在工具调用后把 todo 变化发送给前端或调用方展示。

核心定位：

> Todo 是 Agent 当前任务的运行时工作台，不是长期记忆，也不是 Session 持久状态。

## 设计目标

- 支持模型在任务开始前创建一个完整 todo list。
- 支持模型在执行过程中更新 todo item 的状态。
- 支持 todo item 之间的依赖关系，即 `blocked_by` 表示当前 item 被哪些其他 item 阻塞。
- 支持在 todo list 或 todo item 变化后，通过 hook 发送展示事件。
- 支持在模型把最后一个 active item 更新为完成态时，返回 `Todo list completed and cleared`。
- 支持在模型上下文中适度注入当前 todo 状态，帮助长程任务继续推进。
- 不把 todo 绑定到 session；new session 或 switch/load session 时自动清除当前 todo。
- 默认不持久化 todo；进程重启后 todo 消失。

## 非目标

- 不把 todo 做成长久记忆。
- 不把 todo 写入 session `.jsonl` 或 `.md`。
- 不在第一阶段支持跨 session 恢复 todo。
- 不把 `ready` 作为持久化状态。
- 不让 hook 代替模型自动完成业务判断或自动修改任务内容。

## 和 Memory 的关系

Todo 可以采用类似 memory 的子系统组织方式，但语义不同：

```text
memory: agent-level, long-term, persistent, cross-session
todo: runtime-level, short-term, non-persistent, cleared on session changes
```

推荐目录：

```text
bbagent/built_in_hook/todo/
  __init__.py
  todo.py
  todo_tool.py
  todo_hook.py
  runtime.py
```

其中：

- `todo.py`：数据模型和 `TodoManager`。
- `todo_tool.py`：创建模型可调用的 todo 工具。
- `todo_hook.py`：创建上下文注入 hook、展示事件 hook、清理 hook。
- `runtime.py`：保存 dirty flag、注入节流、上次展示版本等运行态。

## Todo 生命周期

Todo 生命周期以 `TodoList` 为单位，而不是以单个 item 为单位。

一个 `TodoList` 从 `todo_create` 开始，到所有 item 都进入终态后结束。

状态分为：

```text
active:
- pending
- in_progress
- blocked

terminal:
- done
- cancelled
```

当所有 item 都处于 `done` 或 `cancelled` 时：

- 当前 todo list 自动结束。
- `TodoManager` 清空当前 list。
- hook 后续不再注入该 list。
- `todo_update` 如果是触发清空的那次调用，应在工具结果中附上：

```text
Todo list completed and cleared.
```

## Session 关系

Todo 不绑定 session。

Session 仍然承载 todo 执行过程中产生的所有消息、模型输出、工具调用结果和上下文压缩信息，但 session 不拥有 todo 状态。

Session 生命周期事件对 todo 的影响：

- `new_session`：清空当前 todo list。
- `load_session` / switch session：清空当前 todo list。
- fork session：不复制 todo list。

当前代码中 `Agent.new_session()` 已触发 `HookType.NEW_SESSION`。如果 `load_session()` 或其他 session switch 路径没有触发 session 切换 hook，需要在实现中补齐等价触发点，或者新增更精确的 hook 类型。

## 数据模型

建议第一阶段使用 dataclass，保持轻量可测。

```python
TodoStatus = Literal[
    "pending",
    "in_progress",
    "blocked",
    "done",
    "cancelled",
]

@dataclass
class TodoItem:
    id: str
    content: str
    status: TodoStatus = "pending"
    blocked_by: list[str] = field(default_factory=list)
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

@dataclass
class TodoList:
    id: str
    title: str
    items: list[TodoItem]
    created_at: str
    updated_at: str = ""
```

### `blocked_by`

`blocked_by` 表示 todo item 之间的依赖关系。

例如：

```json
{
  "id": "run-tests",
  "content": "Run focused tests for todo subsystem",
  "status": "blocked",
  "blocked_by": ["implement-manager", "implement-tools"]
}
```

含义是：`run-tests` 被 `implement-manager` 和 `implement-tools` 阻塞。

约束：

- `blocked_by` 存 item id。
- `blocked_by` 中引用的 id 必须存在于同一个 todo list。
- item 不能被自己阻塞。
- 禁止循环依赖。
- 当 item 有未完成依赖时，应保持或转为 `blocked`。
- 当前置项全部进入终态后，item 可以自动解除阻塞并转为 `pending`。

### `ready` 的含义

`ready` 不是状态，不应写入数据模型。

`ready` 是展示和调度视图，表示：

```text
status == pending
and blocked_by 中所有依赖项都已进入 terminal 状态
```

展示文案可以使用：

```text
Ready to work on
```

避免让模型误解为存在 `ready` 状态。

## TodoManager

`TodoManager` 负责所有状态读写和一致性校验。

建议接口：

```python
class TodoManager:
    def create_list(self, title: str, items: list[TodoItemInput]) -> TodoMutationResult: ...
    def update_item(
        self,
        item_id: str,
        status: TodoStatus | None = None,
        content: str | None = None,
        blocked_by: list[str] | None = None,
        notes: str | None = None,
    ) -> TodoMutationResult: ...
    def clear(self, reason: str = "") -> TodoMutationResult: ...
    def current(self) -> TodoList | None: ...
    def snapshot(self) -> dict: ...
    def format_for_model(self) -> str: ...
```

`TodoMutationResult` 建议包含：

```python
@dataclass
class TodoMutationResult:
    changed: bool
    message: str
    completed_and_cleared: bool = False
    snapshot: dict | None = None
```

`TodoManager` 内部应在每次变更后：

- 重新计算依赖关系。
- 自动把已解除依赖的 `blocked` item 转回 `pending`。
- 检查 todo list 是否全部进入终态。
- 如果 list 完成，清空 current list，并返回 `completed_and_cleared=True`。

## Runtime

`TodoRuntime` 只保存运行态，不保存业务数据。

建议字段：

```python
@dataclass
class TodoRuntime:
    dirty: bool = False
    version: int = 0
    last_emitted_version: int = -1
    last_injected_version: int = -1
    stream_count_since_inject: int = 0
```

规则：

- todo create/update/clear 后设置 `dirty=True` 并增加 `version`。
- 展示 hook emit 成功后更新 `last_emitted_version`，并清除 dirty。
- 注入 hook 可根据 `last_injected_version` 和节流配置决定是否注入。

## 工具设计

第一阶段建议提供 4 个工具。

### `todo_create`

创建新的 todo list。若当前已有 todo list，替换旧 list。

输入：

```python
async def todo_create(title: str, items: list[TodoItemInput]) -> str:
    ...
```

`TodoItemInput`：

```python
class TodoItemInput(BaseModel):
    id: str
    content: str
    blocked_by: list[str] = []
    notes: str = ""
```

行为：

- 校验 id 唯一。
- 校验依赖存在。
- 校验无自依赖和循环依赖。
- 有依赖且依赖未完成的 item 初始状态为 `blocked`。
- 无依赖的 item 初始状态为 `pending`。
- 标记 runtime dirty。
- 返回简短摘要。

### `todo_update`

更新单个 todo item。

输入：

```python
async def todo_update(
    item_id: str,
    status: TodoStatus | None = None,
    content: str | None = None,
    blocked_by: list[str] | None = None,
    notes: str | None = None,
) -> str:
    ...
```

行为：

- 如果没有当前 todo list，返回可恢复错误消息。
- 如果 item 不存在，返回可恢复错误消息。
- 如果更新 `blocked_by`，执行依赖校验。
- 如果模型把有未完成依赖的 item 更新为 `in_progress`，默认拒绝，并提示仍被哪些 item 阻塞。
- 如果状态变更导致其他 item 解除阻塞，则自动把这些 item 从 `blocked` 转为 `pending`。
- 如果本次更新导致整个 todo list 完成并清空，工具结果末尾附上：

```text
Todo list completed and cleared.
```

### `todo_list`

查看当前 todo list。

输入：

```python
async def todo_list() -> str:
    ...
```

行为：

- 没有 todo list 时返回 `No active todo list.`
- 有 todo list 时返回分组视图：
  - `In progress`
  - `Ready to work on`
  - `Blocked`
  - 可选 `Completed in this list`，但第一阶段可以不展示终态项或只简短展示。

### `todo_clear`

显式清除当前 todo list。

输入：

```python
async def todo_clear(reason: str = "") -> str:
    ...
```

行为：

- 清空当前 list。
- 标记 runtime dirty。
- 返回清除结果。

## Hook 设计

Todo 子系统需要三类 hook：

1. 模型上下文注入 hook。
2. 工具结果后的展示事件 hook。
3. session 变化或 list 生命周期结束后的清理 hook。

### `AFTER_INPUT`

用户输入刚进入 session 后触发。

用途：

- 把当前 todo list 作为用户请求上下文的一部分注入。
- 适合每个用户 turn 只注入一次。

语义：

```text
用户刚给出新请求，模型需要知道当前是否已有 active todo list。
```

示例注入：

```text
[Current Todo List]
Title: Implement todo subsystem

In progress:
- implement-manager: Implement TodoManager

Ready to work on:
- implement-tools: Add todo tools

Blocked:
- run-tests: Run focused tests
  blocked_by: implement-manager, implement-tools
```

### `BEFORE_STREAM`

每次模型流式调用前触发，在工具循环中可能触发多次。

用途：

- 在没有新用户输入，但工具调用已经改变 todo 状态时提醒模型。
- 适合节流注入。

和 `AFTER_INPUT` 的区别：

- `AFTER_INPUT` 是用户 turn 级别提醒。
- `BEFORE_STREAM` 是模型工具循环级别提醒。
- 工具调用后，模型会再次进入 `BEFORE_STREAM`，此时 todo 可能已变化。

建议策略：

- todo 版本变化后下一次 `BEFORE_STREAM` 注入。
- 或每 N 次 stream 注入一次。
- 没有 todo list 时不注入。

### `ON_TOOL_RESULT`

工具执行完成后触发，当前代码中 `Agent.tool_execute()` 会传入 `ToolMessage`：

```python
await self.hook.trigger(HookType.ON_TOOL_RESULT, tool_msg)
```

展示 todolist 的 hook 应放在 `ON_TOOL_RESULT`。

用途：

- 当 `TodoRuntime.dirty=True` 时，通过 `agent._emit()` 发送 todo 展示事件。
- 这类事件面向前端或调用方，不是模型上下文注入。
- 只有当前存在 active todo list 时才发送；没有 todo list 时不发送任何 todo 展示事件。

建议事件格式：

```python
await agent._emit({
    "type": "todo_list",
    "content": manager.snapshot(),
})
```

注意事项：

- `ON_TOOL_RESULT` 传入的是任意工具结果，不只有 todo 工具。
- hook 不应解析自然语言 tool result 判断是否变化。
- todo 工具通过 `TodoRuntime` 标记 dirty，展示 hook 只看 dirty/version。
- emit 成功后清除 dirty。

### `NEW_SESSION`

当前 todo 不绑定 session。

`NEW_SESSION` 触发时：

- 清空当前 todo list。
- 标记 dirty。
- 不发送 todo 展示事件。

如果实现补齐 load/switch session hook，也应执行同样逻辑。

### `AFTER_RUN`

可选。

用途：

- 兜底检查 todo list 是否已经完成但未清空。
- 兜底发送 dirty 的展示事件。

第一阶段如果 `TodoManager` 在每次更新后都能完成清理，`AFTER_RUN` 可以只作为防御性 hook。

## System Prompt

注册 todo 子系统时，应向 agent system prompt 追加一段说明。

建议内容要点：

- 复杂、多步骤任务开始前使用 `todo_create` 创建 todo list。
- 执行过程中及时使用 `todo_update` 更新进度。
- `blocked_by` 表示 todo item 之间的依赖，不表示被用户或外部系统阻塞。
- 如果任务被外部条件阻塞，使用 `notes` 说明原因，并保持合适状态。
- `ready` 不是状态；可以执行的任务由系统在展示中归入 `Ready to work on`。
- Todo 是当前任务的运行时工作台，不是长期记忆。
- Todo list 全部完成或取消后会自动清空。

## 注册方式

在 `bbagent/built_in_hook/__init__.py` 中新增 `_setup_todo`。

示意：

```python
def _setup_todo(agent: Agent, config: BuiltinHookConfig | dict = None) -> None:
    if config is None:
        config = BuiltinHookConfig()
    elif isinstance(config, dict):
        config = BuiltinHookConfig(**config)

    manager = TodoManager()
    runtime = TodoRuntime()

    agent.add_tools(create_todo_tools(manager, runtime))

    (
        inject_after_input,
        remind_before_stream,
        emit_on_tool_result,
        clear_on_new_session,
        cleanup_after_run,
    ) = create_todo_hook(manager, runtime, config)

    hook = agent.hook
    hook.register(func=inject_after_input, hook_type=HookType.AFTER_INPUT, priority=110)
    hook.register(func=remind_before_stream, hook_type=HookType.BEFORE_STREAM, priority=110)
    hook.register(func=emit_on_tool_result, hook_type=HookType.ON_TOOL_RESULT, priority=100)
    hook.register(func=clear_on_new_session, hook_type=HookType.NEW_SESSION, priority=90)
    hook.register(func=cleanup_after_run, hook_type=HookType.AFTER_RUN, priority=110)

    agent.change_system_prompt(agent.system_prompt + config.todo_system_prompt)
```

并在 `HOOK_CREATOR` 中加入：

```python
HOOK_CREATOR = {
    "built_in.memory": _setup_memory,
    "built_in.compress": _setup_compress,
    "built_in.todo": _setup_todo,
}
```

## 配置项

可在 `BuiltinHookConfig` 增加 todo 相关字段：

```python
todo_system_prompt: str = TODO_SYSTEM_PROMPT
todo_auto_inject: bool = True
todo_inject_on_after_input: bool = True
todo_remind_on_before_stream: bool = True
todo_before_stream_interval: int = 3
todo_emit_on_tool_result: bool = True
todo_clear_on_new_session: bool = True
```

默认行为：

- 开启上下文注入。
- 开启 `ON_TOOL_RESULT` 展示事件。
- new session 清除 todo。
- 不持久化 todo。

## 错误处理

工具错误应作为可恢复 tool result 返回给模型，不中断 agent 运行。

典型错误：

- 没有 active todo list 时调用 `todo_update`。
- item id 不存在。
- `blocked_by` 引用不存在。
- 自依赖。
- 循环依赖。
- 有未完成依赖时试图进入 `in_progress`。
- 非法状态值。

错误文案应短而明确，例如：

```text
Todo update failed: item 'run-tests' is blocked by unfinished items: implement-manager, implement-tools.
```

## 前端和事件消费者

第一阶段可以只发送统一事件：

```json
{
  "type": "todo_list",
  "content": {
    "active": true,
    "id": "20260615_...",
    "title": "Implement todo subsystem",
    "version": 3,
    "groups": {
      "in_progress": [],
      "ready": [
        {
          "id": "implement-tools",
          "content": "Add todo tools",
          "status": "pending",
          "blocked_by": [],
          "notes": ""
        }
      ],
      "blocked": [
        {
          "id": "run-tests",
          "content": "Run tests",
          "status": "blocked",
          "blocked_by": ["implement-tools"],
          "notes": ""
        }
      ]
    }
  }
}
```

没有 active todo list 时：

不发送 `todo_list` 事件。

前端可以先把该事件作为可选能力处理，不影响旧会话消息渲染。

## 测试计划

### Manager 单测

- 创建 todo list 后可返回当前 list。
- item id 重复时报错。
- `blocked_by` 引用不存在时报错。
- 自依赖时报错。
- 循环依赖时报错。
- 有未完成依赖的 item 初始状态为 `blocked`。
- 前置项完成后，被阻塞项自动转为 `pending`。
- `ready` 只出现在 snapshot 分组中，不作为 item status。
- 最后一个 active item 更新为 `done` 后，manager 清空 current list。
- 最后一个 active item 更新为 `cancelled` 后，manager 清空 current list。

### Tool 单测

- `todo_create` 返回创建摘要。
- `todo_update` 成功更新状态。
- `todo_update` 完成最后一个 item 时返回 `Todo list completed and cleared.`
- `todo_update` 对不存在 item 返回可恢复错误。
- `todo_list` 无 active list 时返回 `No active todo list.`
- `todo_clear` 清除 current list 并标记 runtime dirty。

### Hook 单测

- `AFTER_INPUT` 在有 active todo 时注入 todo 摘要。
- `BEFORE_STREAM` 在 todo 版本变化后注入提醒。
- `BEFORE_STREAM` 在无变化且未达到 interval 时跳过。
- `ON_TOOL_RESULT` 在 runtime dirty 时调用 `agent._emit` 发送 `todo_list` 事件。
- `ON_TOOL_RESULT` emit 成功后清除 dirty。
- `NEW_SESSION` 清空 current todo，且不发送 `todo_list` 事件。
- todo 不写入 session 文件。

### 集成测试

- 模型创建 todo 后，工具结果正常进入 session。
- `todo_update` 后 `ON_TOOL_RESULT` 发出展示事件。
- 所有 todo 完成后，后续模型调用不再注入 todo。
- new session 后 todo 被清空，且不再发送 todo 展示事件。

## 实施阶段

### 第一阶段：核心能力

- 新增 `bbagent/built_in_hook/todo/` 子系统。
- 实现 `TodoManager`、`TodoRuntime`。
- 实现 4 个工具。
- 实现 `ON_TOOL_RESULT` 展示 hook。
- 实现 `NEW_SESSION` 清除 hook。
- 添加 manager、tool、hook 单测。

### 第二阶段：上下文注入

- 实现 `AFTER_INPUT` todo 注入。
- 实现 `BEFORE_STREAM` 节流提醒。
- 添加注入相关测试。

### 第三阶段：前端展示

- 前端识别 `type == "todo_list"` 的输出事件。
- 增加当前 todo list 展示区域。
- 展示 `In progress`、`Ready to work on`、`Blocked` 分组。
- 无 active todo 时隐藏或清空展示。

## 验收标准

- Agent 可通过工具创建、更新、查看、清除 todo list。
- `blocked_by` 表示 item 依赖，且依赖校验稳定。
- `ready` 只作为派生分组出现，不作为状态保存。
- 最后一个 active item 完成时，工具结果包含 `Todo list completed and cleared.`
- todo list 或 item 变化后，`ON_TOOL_RESULT` hook 通过 `agent._emit` 发送 `todo_list` 事件。
- new session 或 session switch 后，当前 todo 被清空，且不发送 `todo_list` 事件。
- todo 默认不持久化，不写入 session 文件。
- baseline tests 离线、确定，不依赖真实 LLM、MCP server 或外部 API。
