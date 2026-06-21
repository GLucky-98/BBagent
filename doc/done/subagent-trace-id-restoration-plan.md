# SubAgent 共享 Logger 时 Trace ID 覆盖修复方案

## 背景

当前日志系统通过 `AgentLogger` 在每条结构化日志里注入 `trace_id` 和 `span_id`。`trace_id` 存在 logger 实例字段上：

```python
self._trace_id = ""

def set_trace_id(self, trace_id: str = ""):
    self._trace_id = trace_id or uuid().hex[:12]

def clear_trace_id(self):
    self._trace_id = ""
```

主 `Agent` 的事件循环处理输入事件时，会把事件的 `correlation_id` 设为当前 trace：

```python
self.logger.set_trace_id(event.correlation_id)
```

`SubAgent.run()` 也会在运行开始时无条件设置新的 trace，并在结束时清空：

```python
self.logger.set_trace_id()
...
self.logger.clear_trace_id()
```

如果 `SubAgent` 和主 `Agent` 共享同一个 `AgentLogger` 实例，subagent 的运行会覆盖主 agent 当前事件循环的 trace id，并在结束时清空它。

## 当前代码路径

### AgentLogger 是实例级可变状态

`bbagent/core/logger.py`：

```python
record.trace_id = self._logger.trace_id
...
self._trace_id = ""
```

`trace_id` 不是 `contextvars.ContextVar`，也不是栈结构。只要同一个 `AgentLogger` 被多个嵌套调用共享，后一次 `set_trace_id()` 就会覆盖前一次值。

### 主 Agent 事件处理使用事件 correlation_id

`bbagent/core/agent.py` 的 `_handle_event()`：

```python
self.logger.set_trace_id(event.correlation_id)
with self.logger.span("event_handle"):
    ...
finally:
    ...
    self.logger.clear_trace_id()
```

这意味着一次外部输入事件应该在整个处理期间保持同一个 trace id。

### SubAgent.run 无条件创建并清理 trace

`bbagent/core/agent.py` 的 `SubAgent.run()`：

```python
self.logger.set_trace_id()
self.logger.info("SubAgent run started", ...)
try:
    ...
finally:
    self.logger.clear_trace_id()
```

该逻辑适用于独立 subagent，但对共享父 logger 的嵌套 subagent 不安全。

### 内置 sub_agent 工具暂不触发该问题

`bbagent/built_in_tool/sub_agent.py` 创建 `SubAgent` 时没有传入 logger：

```python
sub = SubAgent(
    model=model,
    tools=sub_tools,
    system_prompt=system_prompt,
    name=f"sub_{uuid().hex[:8]}",
)
```

因此它会使用 `_NullLogger`，不会覆盖主 agent 的 trace。

### Hook 内部 subagent 会触发该问题

以下路径会显式复用外部 logger：

- `bbagent/built_in_hook/ctx_compress_hook.py` 的 `ContextCompressor`
- `bbagent/built_in_hook/memory/memory_hook.py` 的 `MemoryExtractor`
- `bbagent/built_in_hook/memory/memory_tool.py` 内部 memory injection subagent

这些 subagent 如果运行在主 agent 一次事件处理过程中，会修改同一个 `AgentLogger._trace_id`。

## 问题

### 1. 父事件循环 trace id 会被覆盖

事件处理开始时：

```text
trace_id = event.correlation_id
```

进入共享 logger 的 `SubAgent.run()` 后：

```text
trace_id = random_subagent_trace_id
```

因此 subagent 运行期间，父事件链路内的日志会被归到新的 trace id 下。

### 2. SubAgent 结束后不会恢复父 trace

`SubAgent.run()` 的 `finally` 调用 `clear_trace_id()`，所以 subagent 返回后：

```text
trace_id = ""
```

父 `_handle_event()` 后续日志，例如 `AFTER_RUN` hook、session save、`Event handling completed`，会丢失原本的 `event.correlation_id`。

### 3. 嵌套或并发 subagent 更容易产生串扰

由于 trace id 和 span stack 都是 logger 实例字段，同一 logger 被多个异步任务共享时存在串扰风险：

- 一个 subagent 清空 trace，影响另一个仍在运行的调用。
- 多个 subagent 并行时，最后一次 `set_trace_id()` 决定共享 logger 当前 trace。
- span stack 也可能在共享 logger 的并发任务中交错。

本 issue 聚焦 trace id 覆盖；span stack 并发隔离可以作为相邻问题单独处理。

## 影响

- 日志链路无法稳定按一次用户输入事件聚合。
- hook 内部产生的 subagent 日志可能和父事件日志分裂到不同 trace。
- subagent 返回后的父 agent 日志可能没有 trace id。
- 如果未来内置 `sub_agent` 工具开始复用主 logger，该问题会扩展到用户显式调用的 subagent。

## 目标

- `SubAgent.run()` 在共享 logger 时不破坏父调用已有 trace id。
- 独立 subagent 仍然可以在没有父 trace 时创建自己的 trace id。
- subagent 结束后恢复进入前的 trace id。
- 保持现有结构化日志字段兼容，不改日志 JSON 格式。
- 增加回归测试，覆盖共享 logger 的 trace 恢复行为。

## 非目标

- 不改变 `AgentEvent.correlation_id` 的生成和传递语义。
- 不重构整个 logger 为分布式 tracing 系统。
- 不修改日志 JSON schema。
- 不在本 issue 中解决 `span_stack` 的异步并发隔离问题。
- 不要求内置 `sub_agent` 工具立刻开始输出日志。

## 推荐方案

### 1. 给 AgentLogger 增加 trace 保存/恢复能力

最小改法是在 `AgentLogger` 上增加一个上下文管理器：

```python
@contextmanager
def trace(self, trace_id: str = "", inherit: bool = True):
    previous = self._trace_id
    if not (inherit and previous):
        self.set_trace_id(trace_id)
    try:
        yield
    finally:
        self._trace_id = previous
```

语义：

- 如果当前已有 trace 且 `inherit=True`，subagent 继承父 trace。
- 如果当前没有 trace，则创建一个新 trace。
- 离开上下文后恢复进入前的 trace，即使 subagent 抛异常也恢复。

### 2. SubAgent.run 使用 trace 上下文

把：

```python
self.logger.set_trace_id()
...
finally:
    self.logger.clear_trace_id()
```

改为：

```python
with self.logger.trace(inherit=True):
    self.logger.info(...)
    ...
```

这样共享 logger 的 hook subagent 会保持父事件 trace，不再覆盖或清空。

### 3. Agent.run / _handle_event 可逐步迁移

主 `Agent.run()` 和 `_handle_event()` 当前也手写 `set_trace_id()` / `clear_trace_id()`。可以先只改 `SubAgent.run()`，降低风险。

后续可以把主 agent 入口也迁移到同一个上下文管理器：

```python
with self.logger.trace(event.correlation_id, inherit=False):
    with self.logger.span("event_handle"):
        ...
```

这样异常路径和未来嵌套行为会更一致。

### 4. 并发隔离的后续方向

如果需要彻底解决同一 logger 在异步任务之间的 trace/span 串扰，应该考虑把 `trace_id` 和 `span_stack` 改为 `contextvars.ContextVar`。

建议分阶段：

1. 先做 trace 保存/恢复，修复当前父 trace 被清空的问题。
2. 再评估是否把 trace/span 迁移到 `contextvars`。
3. 最后补并发 subagent 的隔离测试。

## 测试建议

### AgentLogger trace 上下文

新增或扩展 `tests/unit/core/test_logger.py`：

- 当前无 trace 时，`with logger.trace()` 会生成非空 trace。
- 当前已有 trace 时，`with logger.trace(inherit=True)` 不覆盖父 trace。
- `with logger.trace(inherit=False)` 会临时覆盖，并在退出后恢复。
- 上下文内抛异常时也恢复原 trace。

### SubAgent.run 共享 logger 恢复 trace

新增或扩展 `tests/unit/core/test_agent.py`：

- 构造 fake model，返回 `end_turn`。
- 创建真实 `AgentLogger` 或测试 logger。
- 先设置 `logger.set_trace_id("parent-trace")`。
- 运行 `SubAgent(..., logger=logger).run(...)`。
- 断言运行后 `logger.trace_id == "parent-trace"`。

### SubAgent.run 无父 trace 时仍可生成 trace

可以通过捕获日志 handler 或测试 logger 验证：

- 进入 subagent 时日志有非空 trace id。
- run 结束后恢复为空字符串。

## 验收标准

- 共享 logger 的 `SubAgent.run()` 不再覆盖并清空父 trace id。
- hook subagent 日志能继续归入父事件的 `correlation_id`。
- 独立 subagent 行为不退化。
- 新增测试覆盖 trace 继承、临时覆盖和异常恢复。
- baseline 测试通过：

```bash
python -m pytest tests/unit/core
ruff check bbagent tests
```
