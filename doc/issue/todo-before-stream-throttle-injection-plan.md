# Todo Before Stream 节流注入修复方案

## 背景

当前 Todo 子系统已经有 `TodoRuntime.last_injected_version`、`stream_count_since_inject` 和 `todo_stream_inject_interval`，并且在 `HookType.BEFORE_STREAM` 注册了 `remind_before_stream()`。

但实际模型上下文注入并不受这些状态控制。

当前链路是：

```text
Agent.run()
  session.add_message(human_msg)
  AFTER_INPUT
  stream_tool_loop()
    BEFORE_STREAM
    construct_model_input()
      runtime_context_providers()
```

Todo 子系统在 setup 时把 `todo_context_provider` 加入：

```python
agent.runtime_context_providers.append(todo_context_provider)
```

而 `Agent.construct_model_input()` 每次都会调用所有 provider。只要 provider 返回非空文本，就会把文本 prepend 到最后一个 `HumanMessage` 前。

现在的 `todo_context_provider()` 只看 `manager.format_for_model()`，不看 `TodoRuntime`。因此只要存在 active todo list，每次 stream 前都会注入 todo context。`BEFORE_STREAM` hook 里的节流计数只更新 runtime 状态，但没有控制 provider 是否返回内容。

## 问题

现有实现的实际语义：

- active todo list 存在时，每次 `construct_model_input()` 都注入 todo context。
- `todo_stream_inject_interval` 配置不会影响模型输入。
- `last_injected_version` 和 `stream_count_since_inject` 只被维护，没有真正参与注入决策。
- 测试只覆盖了 provider 会注入且不污染 session，没有覆盖节流行为。

期望语义：

- 用户输入后的首次模型调用应能看到 active todo list。
- 工具调用改变 todo 后，下一次模型 stream 应能看到新的 todo list。
- todo 没有变化时，不应每次工具循环都重复注入；应按 `todo_stream_inject_interval` 节流提醒。
- 注入仍应是 runtime-only，不写回 session。

## 设计目标

- 让 `BEFORE_STREAM` 的节流决策真正控制 todo context 是否进入下一次 `model_input`。
- 保持当前 transient runtime context 机制，不把 todo context 写入 session。
- 避免 `AFTER_INPUT` 和紧跟着的 `BEFORE_STREAM` 造成双份 todo 文本。
- 保留工具更新后的版本变化触发注入。
- 让配置项 `todo_stream_inject_interval` 可以被测试证明有效。

## 非目标

- 不改变 todo tool 的 schema。
- 不改变前端 `todo_list` 展示事件格式。
- 不把 todo list 持久化到 session。
- 不把 todo context 改成 system prompt。
- 不在本方案中处理更复杂的 token budget 或上下文裁剪策略。

## 推荐方案

### 1. 在 `TodoRuntime` 中增加一次性注入请求

新增字段：

```python
inject_next_stream: bool = False
```

新增方法：

```python
def request_injection(self) -> None:
    self.inject_next_stream = True

def clear_injection_request(self) -> None:
    self.inject_next_stream = False
```

调整或保留 `mark_injected()`，让它代表“provider 已经真正向模型输入返回了 todo context”：

```python
def mark_injected(self) -> None:
    self.last_injected_version = self.version
    self.stream_count_since_inject = 0
    self.inject_next_stream = False
```

这样可以区分两个概念：

- `request_injection()`：预约下一次模型输入注入。
- `mark_injected()`：provider 已实际返回 context。

### 2. 让 provider 闭包读取 runtime

`create_todo_hook(manager, runtime, ...)` 里定义的 `todo_context_provider` 可以通过闭包直接持有同一个 `runtime` 引用。

改造前：

```python
def todo_context_provider() -> str:
    return _format_todo_context(manager)
```

改造后：

```python
def todo_context_provider() -> str:
    if not runtime.inject_next_stream:
        return ""

    context = _format_todo_context(manager)
    if not context:
        runtime.clear_injection_request()
        return ""

    runtime.mark_injected()
    return context
```

这会让 `Agent.construct_model_input()` 继续保持通用，不需要知道 TodoRuntime 的存在。

### 3. `AFTER_INPUT` 只预约注入

用户输入刚进入 session 时，应保证下一次模型调用可以看到当前 active todo。

建议逻辑：

```python
async def inject_after_input(ctx: HookContext):
    if manager.current() is None:
        runtime.clear_injection_request()
        return
    runtime.request_injection()
```

这里不要调用 `mark_injected()`，因为此时 `construct_model_input()` 还没有发生，todo context 还没有真正进入模型输入。

### 4. `BEFORE_STREAM` 做节流决策

`BEFORE_STREAM` 会在每次模型 stream 前触发，包括用户输入后的首次 stream 和工具结果后的后续 stream。

建议逻辑：

```python
async def remind_before_stream(ctx: HookContext):
    if manager.current() is None:
        runtime.clear_injection_request()
        runtime.stream_count_since_inject = 0
        return

    if runtime.inject_next_stream:
        return

    runtime.tick_stream()
    interval = max(1, stream_inject_interval)

    if runtime.last_injected_version != runtime.version:
        runtime.request_injection()
        return

    if runtime.stream_count_since_inject >= interval:
        runtime.request_injection()
```

注意：

- 如果 `AFTER_INPUT` 已经预约注入，紧跟着的 `BEFORE_STREAM` 不应该清掉它。
- 版本变化优先于 interval；todo tool 更新后，下一次 stream 应注入。
- interval 只控制“todo 未变化时”的周期性提醒。

### 5. 工具结果展示事件保持不变

`ON_TOOL_RESULT` 仍然只负责向前端或调用方发送 `todo_list` 展示事件：

```python
await ctx.agent._emit({
    "type": "todo_list",
    "content": snapshot,
})
```

这条链路不应影响模型上下文注入。

## 状态机

推荐状态转移：

```text
todo_create / todo_update / todo_clear changed
  -> runtime.version += 1
  -> runtime.dirty = True

AFTER_INPUT with active todo
  -> inject_next_stream = True

BEFORE_STREAM
  -> if no active todo: clear request
  -> if request already exists: keep it
  -> if version changed since last injection: request injection
  -> else if interval reached: request injection

construct_model_input()
  -> calls provider
  -> provider returns todo context only when inject_next_stream=True
  -> provider marks injected after returning context

ON_TOOL_RESULT
  -> emits todo_list event when dirty
  -> marks emitted
```

## 行为示例

### 用户输入后的首次调用

```text
active todo exists
user message added
AFTER_INPUT requests injection
BEFORE_STREAM sees request and leaves it unchanged
construct_model_input provider returns todo context once
runtime.mark_injected()
```

结果：首次调用注入一份 todo context，不会双重注入。

### 工具更新 todo 后的下一次调用

```text
todo_update changes item
runtime.version increments
tool result added to session
next BEFORE_STREAM sees last_injected_version != version
request injection
construct_model_input provider returns updated todo context
runtime.mark_injected()
```

结果：模型能在工具循环继续前看到最新 todo 状态。

### todo 未变化的连续工具循环

假设 `todo_stream_inject_interval = 3`：

```text
stream 1: injected, counter reset
stream 2: no version change, counter 1, no injection
stream 3: no version change, counter 2, no injection
stream 4: no version change, counter 3, injection
```

结果：todo context 周期性提醒，但不会每次都注入。

## 测试计划

### 单元测试：provider 受 runtime request 控制

新增测试：

- 创建 active todo。
- 不设置 `inject_next_stream`。
- 调用 `agent.construct_model_input()`。
- 断言模型输入不包含 `[Current Todo List]`。
- 设置 `runtime.request_injection()`。
- 再次调用 `construct_model_input()`。
- 断言模型输入包含 `[Current Todo List]`。
- 断言 session 原始 human message 没有被修改。

### 单元测试：AFTER_INPUT 预约注入

新增测试：

- 创建 active todo。
- 调用 `inject_after_input(ctx)`。
- 调用 `remind_before_stream(ctx)`。
- 调用 provider 或 `construct_model_input()`。
- 断言只返回一份 todo context。
- 断言 `runtime.last_injected_version == runtime.version`。
- 断言 `runtime.inject_next_stream is False`。

### 单元测试：版本变化触发下一次 BEFORE_STREAM 注入

新增测试：

- 先完成一次注入，让 `last_injected_version == version`。
- 修改 todo item 并 `runtime.mark_dirty()`。
- 调用 `remind_before_stream(ctx)`。
- 断言 `runtime.inject_next_stream is True`。
- 调用 provider。
- 断言返回更新后的 todo 内容。

### 单元测试：interval 对未变化 todo 生效

新增测试：

- `stream_inject_interval=3`。
- 完成一次注入。
- 连续调用 `remind_before_stream(ctx)`。
- 第 1、2 次后 provider 返回空。
- 第 3 次后 provider 返回 todo context。

### 回归测试：无 active todo 不注入

新增测试：

- 无 active todo。
- 调用 `inject_after_input(ctx)` 和 `remind_before_stream(ctx)`。
- 调用 `construct_model_input()`。
- 断言不包含 todo context。
- 断言 `inject_next_stream is False`。

## 验收标准

- `todo_stream_inject_interval` 能改变未变化 todo 的重复注入频率。
- `AFTER_INPUT` 后的首次模型调用仍能看到 active todo。
- todo tool 更新后，下一次模型调用能看到最新 todo。
- 没有 active todo 时不注入。
- todo context 仍然不写入 session `.jsonl` 或 `.md`。
- 前端 `todo_list` 展示事件行为不变。

## 建议执行顺序

1. 修改 `bbagent/built_in_hook/todo/runtime.py`，增加 `inject_next_stream` 和 request/clear 方法。
2. 修改 `bbagent/built_in_hook/todo/todo_hook.py`，让 hook 只预约注入，让 provider 负责一次性返回 context。
3. 补充 `tests/unit/built_in_hook/test_todo_subsystem.py` 覆盖上述节流行为。
4. 运行：

```bash
python -m pytest tests/unit/built_in_hook/test_todo_subsystem.py
ruff check bbagent/built_in_hook/todo tests/unit/built_in_hook/test_todo_subsystem.py
```

如果依赖缺失，按项目测试说明安装最小必要依赖后再运行。
