# InputChannel 队列所有权重构

## 背景

当前 `Agent` 和 `InputChannel` 之间存在职责边界模糊的问题：`Agent` 创建、传递、消费、重置事件队列，而 `InputChannel` 只是被动持有队列引用。

### 当前代码路径

**`Agent.__init__`** (`bbagent/core/agent.py#L95`)：
```python
self._event_queue: asyncio.Queue = asyncio.Queue()
self.input = InputChannel()
```

**`Agent.start()`** (`bbagent/core/agent.py#L545`)：Agent 把自己的队列传给 input
```python
await self.input.start(self._event_queue)
```

**`InputChannel.start()`** (`bbagent/core/input.py#L40-41`)：input 只是存一下引用
```python
async def start(self, output_queue: asyncio.Queue):
    self._queue = output_queue
```

**`Agent._stream_loop`** (`bbagent/core/agent.py#L559`)：Agent 从自己的队列消费
```python
event_task = asyncio.create_task(self._event_queue.get())
```

**`Agent._stream_loop` finally** (`bbagent/core/agent.py#L615`)：Agent 重置队列
```python
self._event_queue = asyncio.Queue()
```

**`Agent._drain_event_queue`** (`bbagent/core/agent.py#L347-350`)：Agent 排空队列
```python
def _drain_event_queue(self):
    while True:
        try:
            self._event_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
```

### 问题

1. **职责分散**：队列的完整生命周期（创建、消费、排空、重建）分散在 `Agent` 和 `InputChannel` 两个类中，但队列本质上是输入通道的内部实现细节。
2. **需要传参**：`input.start()` 需要外部传入队列，增加了耦合。
3. **重复管理**：`Agent` 在 `finally` 块中手动 `self._event_queue = asyncio.Queue()`，而 `InputChannel.stop()` 也做了 `self._queue = None`，两边的重置逻辑不统一。
4. **`_drain_event_queue` 独立存在**：排空逻辑在 `Agent` 上，但真正理解队列状态的是 `InputChannel`。

## 目标

将事件队列的所有权完全移交给 `InputChannel`，让生产者管理自己的通道，消费者只管读取。

## 方案

### 对照

| 当前（Agent 管） | 改后（InputChannel 管） |
|---|---|
| `Agent.__init__` 创建 `self._event_queue` | `InputChannel.__init__` 创建 `self._queue` |
| `agent.input.start(queue)` 传入 | `agent.input.start()` 不需要参数 |
| `agent._event_queue.get()` 消费 | `agent.input.queue` 只读访问 |
| `agent._event_queue = Queue()` 重置 | `input.stop()` 内重建队列 |
| `agent._drain_event_queue()` 排空 | 合并到 `input.stop()` |

### 改动清单

#### 1. `InputChannel.__init__` — 初始化自有队列

```python
def __init__(self):
    self._queue: asyncio.Queue = asyncio.Queue()
    self._running = False
    ...
```

#### 2. `InputChannel.start` — 去掉 `output_queue` 参数

```python
async def start(self):
    self._queue = self._queue or asyncio.Queue()  # 防御性重建
    self._running = True
    self._timers = []
    for seconds, name, hint in self._timer_configs:
        task = self._create_timer_task(seconds, name, hint)
        self._timers.append((name, task))
```

#### 3. `InputChannel.stop` — 统一重置逻辑

```python
async def stop(self):
    self._running = False
    for _, task in self._timers:
        task.cancel()
    self._timers.clear()
    # Drain + reset
    while True:
        try:
            self._queue.get_nowait()
        except asyncio.QueueEmpty:
            break
    self._queue = asyncio.Queue()
```

#### 4. 暴露只读属性

```python
@property
def queue(self) -> asyncio.Queue:
    return self._queue
```

#### 5. `Agent` — 移除 `_event_queue`，改用 `self.input.queue`

- 删除 `self._event_queue = asyncio.Queue()` (L95)
- `self.input.start(self._event_queue)` → `self.input.start()`
- `self._event_queue.get()` → `self.input.queue.get()`
- 删除 `self._event_queue = asyncio.Queue()` (L615)
- 删除 `_drain_event_queue` 方法 (L347-350) 及其调用点 (L645)

### 不涉及的改动

- `InputChannel.push()` — 逻辑不变，只是 `self._queue` 现在由自己创建
- 后端 WebSocket handler 中对 `agent.input.push()` 的调用 — 接口不变
- timer 逻辑 — 不变

## 收益

1. **单一职责**：`InputChannel` 全权管理自己的消息通道
2. **减少耦合**：`Agent` 不需要关心队列的创建和重置
3. **代码更干净**：`Agent._stream_loop` 的 `finally` 块更短，`_drain_event_queue` 消失
4. **接口更简洁**：`input.start()` 无需传参

## 风险

- 低风险重构：改动集中在 `Agent` 和 `InputChannel` 两个文件，不涉及后端 API 或前端
- 需确保 `input.start()` 的幂等性（agent 的 `start()` 可能被多次调用）
