# Runtime Tool Use Replay Implementation Plan

## 背景

当前前端在 agent 切换时会重新调用 `GET /agents/{id}/messages` 拉取该 agent 的消息列表，并用返回结果整体替换前端 `agent.messages`。

这会导致一个运行中显示问题：

1. 用户在 `agent1` 的 ChatWindow 输入一条命令。
2. 模型输出 6 个 `completed_tool_use`，前端通过 WebSocket 实时显示 6 条 `tool_use`。
3. 用户切到 `agent2`，再切回 `agent1`。
4. `ChatWindow` 重新调用 `loadAgentMessages(agent1)`，用 HTTP 返回的 session history 覆盖前端消息。
5. 如果此时工具还没完成，后端 session 里还没有把 `pending_model_message` 提交进去，HTTP history 不包含这 6 条 `tool_use`。
6. 结果是用户切回后看不到之前已经显示过的 6 条 `tool_use`。

这个问题不是简单的后端没有读取最新消息，而是当前系统中存在两类消息来源：

- committed session history：已经进入 `agent.session.turns` 的正式消息。
- runtime stream events：当前 run/turn 中通过 WebSocket 推送的运行态事件。

`tool_use` 在 interrupt 前不应该立即进入 session history，因为如果用户中断，本轮 pending tool use 应该被丢弃，不应污染上下文。因此正确方向不是提前保存 `tool_use` 到 session，而是让前端在切换回来时能够恢复未完成 turn 的 runtime events。

## 目标

- 切换到其他 agent 后再切回，未完成 turn 中已经出现过的 `tool_use` 仍能显示。
- 保持 interrupt 语义：未完成 turn 的 `tool_use` 不进入 session history。
- 正常完成后，正式 session history 接管 UI 展示，runtime replay 缓存清空。
- HTTP `getAgentMessages` 只返回完整 turn，避免 committed history 与当前 runtime replay 重叠。
- 对 WebSocket replay/live 事件使用稳定 id，避免重复 replay 时重复渲染。
- 尽量复用现有 `AgentOutputDispatcher._round_buffer`，避免引入复杂持久化。

## 非目标

- 不改变模型上下文构造语义。
- 不把未完成 turn 写入 `.jsonl` session 文件。
- 不要求 runtime events 在后端重启后恢复。
- 不在本方案中重构整个 ChatWindow 消息渲染架构。

## 当前行为分析

### 1. 后端 session 提交时机

位置：

- `bbagent/core/agent.py`

当前 `stream_tool_loop()` 在收到 `completed_tool_use` 时，会立即启动工具任务并 yield chunk 给 WebSocket：

```python
if chunk_type == 'completed_tool_use':
    tool_use = content
    task = asyncio.create_task(self.tool_execute(tool_use))
    tool_tasks.append(task)
    yield chunk
```

但在收到 `completed_message` 且 `stop_reason == "tool_use"` 时，并不会立即写入 session：

```python
if stop_reason == 'tool_use':
    pending_model_message = content
else:
    self.session.add_message(content)
```

只有工具结果完成后，才写入：

```python
tool_results = await self._wait_for_tool_results(tool_tasks)
yield {'type': 'tool_results', 'content': tool_results}
self.session.add_message([pending_model_message, *tool_results])
```

因此在工具运行期间，WebSocket 已经发出了 `tool_use`，但 `GET /messages` 仍不会返回这些 `tool_use`。

### 2. dispatcher replay buffer 清空过早

位置：

- `backend/dispatcher.py`

当前 dispatcher 在收到任何 `completed_message` 时都会清空 `_round_buffer`：

```python
if serializable.get("type") == "completed_message":
    self._round_buffer.clear()
```

但工具调用场景中，`completed_message.stop_reason == "tool_use"` 只代表模型当前片段结束，并不代表整个 turn 结束。此时清空 replay buffer 会让切回 agent 时无法 replay 已经出现的 `tool_use`。

### 3. 前端消息 id 不稳定

位置：

- `frontend/src/store/index.ts`
- `frontend/src/components/ChatWindow.tsx`

HTTP history 加载时，前端用数组下标生成 UI id：

```ts
id: `hist-${i}`
```

WebSocket runtime 消息通常使用随机 id：

```ts
id: crypto.randomUUID()
```

这意味着同一条 tool call 如果通过 HTTP history 和 WebSocket replay 各出现一次，前端无法识别它们是同一个工具调用，容易重复渲染。

## 总体方案

采用轻量的 runtime replay 方案：

```text
GET /agents/{id}/messages
  只返回 complete turns 的 committed session history

AgentOutputDispatcher._round_buffer
  缓存当前未完成 turn 的 WebSocket runtime events

WebSocket switch_agent replay
  切回 agent 时 replay 当前未完成 turn 的 events

前端 messages
  通过稳定 id/upsert 去重，避免 live/replay 重复事件重复显示
```

关键原则：

- session history 是事实记录。
- dispatcher buffer 是运行中现场。
- HTTP history 不返回未完成 turn；未完成 turn 只由 dispatcher replay 恢复。
- interrupt 清空运行中现场。
- end_turn 后清空运行中现场。
- replay 不应该导致重复 UI message。

## 后端修改方案

## 方案一：调整 dispatcher buffer 清空条件

### 目标

只在完整 turn 结束时清空 runtime replay buffer。

### 修改位置

- `backend/dispatcher.py`

### 推荐行为

当前：

```python
if serializable.get("type") == "completed_message":
    clear_buffer()
```

修改为：

```python
if is_completed_end_turn(serializable):
    clear_buffer()
elif serializable.get("type") == "interrupted":
    clear_buffer()
elif is_agent_error(serializable):
    clear_buffer()
```

其中：

```python
def is_completed_end_turn(chunk: dict) -> bool:
    if chunk.get("type") != "completed_message":
        return False
    content = chunk.get("content") or {}
    return content.get("stop_reason") == "end_turn"
```

注意：`content` 已经经过 `_make_serializable()`，dataclass 会被转换为 dict。

同时删除 dispatcher replay buffer 的静默截断逻辑：

```python
_MAX_BUFFER_ENTRIES = ...
_MAX_BUFFER_BYTES = ...

while len(self._round_buffer) > ... or self._buffer_bytes > ...:
    evicted = self._round_buffer.pop(0)
```

本方案要求 `_round_buffer` 完整保存当前未完成 turn 的 runtime chunks。否则用户切回 agent 时可能只能恢复一半现场，仍然会出现缺失消息。

### 为什么不能在 `tool_use` 的 `completed_message` 清空

`stop_reason == "tool_use"` 表示：

```text
模型完成了一段输出，并要求调用工具。
```

此时真实 turn 仍未结束，工具结果和后续模型输出还会继续发生。这个阶段的 runtime events 必须保留，才能在用户切换回来时 replay。

### 中断和错误

保持以下行为：

- `interrupted`：清空 buffer。
- `agent_state == error`：清空 buffer。

这样 interrupt 后，未提交的 `tool_use` 不会再 replay 到 UI。

## 方案二：`get_messages()` 只返回完整 turn

### 目标

让 HTTP history 和 WebSocket replay 的职责完全分开：

- HTTP `GET /agents/{id}/messages`：只返回已经完成的 turn。
- WebSocket dispatcher replay：只负责恢复当前未完成 turn 的 runtime events。

这样可以从源头上避免 streaming text/thinking 以及 tool_use/tool_result 的大部分重复渲染问题。

### 修改位置

- `backend/factories/agent_factory.py#get_messages()`

### 推荐行为

遍历 session turns 时，跳过未完成 turn：

```python
for turn in agent.session.turns:
    if not turn.is_complete:
        continue
    for msg in turn.messages:
        ...
```

这表示：

- 如果当前 turn 已经产生了 `tool_use`，但尚未最终 `end_turn`，HTTP 不返回该 turn 的任何消息。
- 如果当前 turn 中部分 tool result 已经写入 session，但整个 turn 仍未完成，HTTP 也不返回该 turn。
- 当前运行现场统一由 dispatcher buffer replay。
- turn 最终 `end_turn` 后，下一次 HTTP load 才返回该完整 turn。

### 为什么要按 turn 过滤，而不是只过滤 tool_use

一个未完成 turn 可能同时包含：

- 用户输入
- streaming text
- thinking
- completed_tool_use
- tool_results
- 多轮 tool loop 的中间结果

如果 HTTP 返回其中一部分，WebSocket replay 又返回同一 turn 的 runtime chunks，前端就需要处理大量重叠。按 turn 过滤可以保持边界清晰：完整 turn 归 HTTP，未完成 turn 归 replay。

### replay buffer 表达当前未完成 turn

配合方案一调整清空条件后，dispatcher buffer 会从当前 turn 的第一批 runtime chunk 开始保留，直到最终 `end_turn` 或 interrupt。

buffer 覆盖：

- streaming text
- thinking
- completed_tool_use
- tool_results
- 中间多轮 tool loop 的 runtime events

### end_turn 后的接管流程

当最终 `completed_message.stop_reason == "end_turn"` 到达：

1. 后端 session 中当前 turn 变为 complete。
2. dispatcher buffer 清空。
3. 前端收到最终完成事件后重新 `loadAgentMessages(agentId)`。
4. HTTP complete history 接管 UI 展示。

### interrupt 后的丢弃流程

当收到 interrupt：

1. 后端丢弃未提交 pending turn。
2. dispatcher buffer 清空。
3. HTTP complete history 不包含被中断 turn。
4. 前端清理当前 runtime 状态或通过下一次 load/replay 自然恢复。

## 方案三：HTTP messages 返回稳定 tool id

### 目标

让前端能够稳定识别 tool_use/tool_result，避免同一 WebSocket chunk 因 replay、重连或重复订阅被追加多次。

### 修改位置

- `backend/factories/agent_factory.py`
- `frontend/src/types/index.ts`
- `frontend/src/store/index.ts`
- `frontend/src/components/ChatWindow.tsx`

### 后端 `get_messages()` 增加字段

对于 `tool_use`：

```python
result.append({
    "role": "system",
    "chunkType": "tool_use",
    "messageId": msg_dict.get("id", ""),
    "toolCallId": tc.get("id", ""),
    "toolName": tc.get("name", ""),
    "toolInput": tc_input,
    "content": json.dumps(tc_input, indent=2, ensure_ascii=False),
    "source_agent": agent.name,
    "timestamp": ts,
})
```

对于 `tool_result`：

```python
result.append({
    "role": "system",
    "chunkType": "tool_result",
    "toolCallId": msg_dict.get("id", ""),
    "toolName": tool_name,
    "content": content_str,
    "source_agent": agent.name,
    "timestamp": ts,
})
```

说明：

- `ModelMessage.id` 标识一条模型消息。
- `ToolUseBlock.id` 标识一个具体工具调用。
- `ToolMessage.id` 通常对应 `ToolUseBlock.id`，适合做 `tool_result` 的 `toolCallId`。

一个 `ModelMessage` 可能包含多个 tool calls，因此单独复用 `ModelMessage.id` 不足以区分 6 个 tool_use。前端需要 `toolCallId`。

### 非 tool 消息的 id

可以同步传递：

```python
"messageId": msg_dict.get("id", "")
```

但本 issue 的最小必要改动是 tool use/result 的稳定 id。

## 前端修改方案

## 方案一：扩展 Message 类型

### 修改位置

- `frontend/src/types/index.ts`

新增字段：

```ts
export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  sourceAgent?: string;
  chunkType?: "text" | "thinking" | "tool_use" | "tool_result" | "error" | "input_event";
  toolName?: string;
  toolInput?: Record<string, unknown>;
  messageId?: string;
  toolCallId?: string;
  runtime?: boolean;
}
```

字段含义：

- `id`：前端 UI message 的唯一 id。
- `messageId`：后端 `ModelMessage.id` 或其他后端 message id。
- `toolCallId`：后端 `ToolUseBlock.id` / `ToolMessage.id`。
- `runtime`：该消息是否来自 WebSocket runtime/replay，而非 HTTP committed history。

## 方案二：生成稳定 UI id

### 新增 helper

建议放在 `frontend/src/store/index.ts` 或新建 `frontend/src/lib/messages.ts`：

```ts
function buildMessageUiId(m: {
  role?: string;
  chunkType?: string;
  messageId?: string;
  toolCallId?: string;
}, fallback: string) {
  if (m.chunkType === "tool_use" && m.toolCallId) {
    return `tool_use:${m.toolCallId}`;
  }
  if (m.chunkType === "tool_result" && m.toolCallId) {
    return `tool_result:${m.toolCallId}`;
  }
  if (m.chunkType === "thinking" && m.messageId) {
    return `thinking:${m.messageId}`;
  }
  if ((!m.chunkType || m.chunkType === "text") && m.messageId) {
    return `${m.role || "message"}:${m.messageId}:text`;
  }
  return fallback;
}
```

### HTTP history 使用稳定 id

当前：

```ts
id: `hist-${i}`
```

调整为：

```ts
const messageId = m.messageId as string | undefined;
const toolCallId = m.toolCallId as string | undefined;

id: buildMessageUiId(
  {
    role: m.role as string,
    chunkType: m.chunkType as string | undefined,
    messageId,
    toolCallId,
  },
  `hist-${i}`,
),
messageId,
toolCallId,
```

`hist-${i}` 只保留为最后 fallback，不再作为 tool_use/tool_result 的主 id。

### WebSocket runtime 使用稳定 id

`completed_tool_use` 当前使用随机 id。调整为：

```ts
const toolCallId = (ct?.id as string) || "";
const id = toolCallId ? `tool_use:${toolCallId}` : crypto.randomUUID();
```

创建 message：

```ts
{
  id,
  role: "system",
  content: JSON.stringify(ct?.input || {}, null, 2),
  timestamp: Date.now(),
  chunkType: "tool_use",
  toolName: (ct?.name as string) || "",
  toolInput: (ct?.input as Record<string, unknown>) || {},
  toolCallId,
  runtime: true,
}
```

`tool_results` 同理：

```ts
const toolCallId = (rDict.id as string) || "";
const id = toolCallId ? `tool_result:${toolCallId}` : crypto.randomUUID();
```

## 方案三：addMessage 改为 upsert 或新增 upsertMessage

### 问题

如果 replay 回来的是同一条 `tool_use`，当前 `addMessage()` 会直接 append，造成重复。

### 推荐实现

新增：

```ts
upsertMessage: (agentId: string, message: Message) => void;
```

行为：

```ts
const idx = a.messages.findIndex((m) => m.id === message.id);
if (idx === -1) {
  append;
} else {
  patch existing;
}
```

对于 runtime replay/live 事件使用 `upsertMessage()`。

保留 `addMessage()` 用于明确必须追加的新消息，例如用户手动输入的新 user message。

### 为什么不直接把 addMessage 全部改成 upsert

有些消息目前没有稳定 id，直接全局改成 upsert 可能隐藏其他问题。更稳妥的是：

- runtime tool_use/tool_result 使用 upsert。
- streaming assistant/thinking 继续使用当前 `currentAssistantMsgIdRef` / `currentThinkingMsgIdRef` patch 逻辑。
- HTTP history 整体替换 committed messages，不走 upsert。

## 方案四：处理重复 replay/live event

### 场景

即使 HTTP 已经不返回未完成 turn，WebSocket 层仍可能出现重复事件：

- 用户切换 agent 后又切回，dispatcher replay 同一批 runtime chunks。
- WebSocket 重连后重新订阅，replay 同一批 runtime chunks。
- 前端已经实时收到某条 `completed_tool_use`，之后又通过 replay 收到同一条。

### 解决方式

使用相同稳定 UI id：

```text
tool_use:{toolCallId}
tool_result:{toolCallId}
```

所以重复事件到达时，`upsertMessage()` 会更新现有 message，而不是追加重复 message。

### runtime 字段处理

如果现有 message 已经是 committed message，而 replay 又来了 runtime message：

- 可以保留 committed message 的 `runtime: false`。
- upsert 时建议不要用 runtime message 覆盖 committed message 的 `runtime` 为 true。

推荐 merge 规则：

```ts
const next = existing.runtime === false
  ? { ...message, runtime: false }
  : { ...existing, ...message };
```

或者更简单：

```ts
runtime: existing.runtime === false ? false : message.runtime
```

## WebSocket 切换流程

当前位置：

- `backend/api/chat.py`

`subscribe_to(agent_id)` 已经使用：

```python
holder.queue = new_disp.subscribe(subscriber_id, replay=True)
```

因此 dispatcher buffer 清空条件修复后，切回 agent 会自动 replay 未完成 turn 的 chunks。

推荐继续保持切换顺序：

1. 前端调用 `loadAgentMessages(id)` 拉 complete turn history。
2. 前端发送 `switch_agent`。
3. 后端订阅 dispatcher，`replay=True`。
4. replay chunks 到前端。
5. 前端 upsert runtime messages。

这样 HTTP complete history 是底座，runtime replay 是当前未完成 turn 的 overlay。

## 数据流示例

### 正常工具调用进行中

```text
agent1: completed_tool_use call_a
agent1: completed_tool_use call_b
agent1 dispatcher buffer:
  completed_tool_use call_a
  completed_tool_use call_b

前端显示:
  tool_use:call_a
  tool_use:call_b

用户切到 agent2
用户切回 agent1

GET /messages:
  不包含 call_a/call_b，因为还没提交 session

WS replay:
  completed_tool_use call_a
  completed_tool_use call_b

前端 upsert:
  tool_use:call_a
  tool_use:call_b
```

结果：切回后仍能看到 2 条 tool_use。

### 工具结果已写入 session 但 turn 未结束

```text
GET /messages:
  不返回当前未完成 turn，所以不包含 call_a

WS replay:
  completed_tool_use call_a
  tool_results call_a
```

结果：HTTP 与 replay 不重叠，不会因为同一 turn 的部分提交产生重复渲染。

### interrupt

```text
agent1: completed_tool_use call_a
agent1 dispatcher buffer:
  completed_tool_use call_a

用户 interrupt
后端发送 interrupted
dispatcher 清空 buffer

用户切走再切回
GET /messages:
  不包含 call_a
WS replay:
  空
```

结果：未完成 tool_use 被丢弃，符合 interrupt 语义。

### final end_turn

```text
agent1 最终 completed_message stop_reason=end_turn
后端 session 已提交完整 turn
dispatcher 清空 buffer

用户切回
GET /messages:
  返回 complete turn history，包含刚完成的 turn
WS replay:
  空
```

结果：UI 展示正式历史，不再依赖 runtime replay。

## 测试方案

### 后端单测

新增或扩展：

- `tests/unit/backend/test_dispatcher.py`

覆盖：

1. `completed_message` 且 `stop_reason == "tool_use"` 不清空 buffer。
2. `completed_message` 且 `stop_reason == "end_turn"` 清空 buffer。
3. `interrupted` 清空 buffer。
4. `agent_state == error` 清空 buffer。
5. `subscribe(replay=True)` 能 replay 未完成 turn buffer。
6. 未完成 turn 的 replay buffer 不因条数或字节数限制被静默截断。

新增或扩展：

- `tests/unit/backend/test_agent_factory_messages.py`

覆盖：

1. `get_messages()` 跳过未完成 turn。
2. `get_messages()` 返回完整 turn。
3. `get_messages()` 对 `tool_use` 返回 `toolCallId`。
4. `get_messages()` 对 `tool_result` 返回 `toolCallId`。
5. 一个 `ModelMessage` 多个 `tool_calls` 时，每个 tool_use 都有不同 `toolCallId`。

### 前端测试

如果当前没有前端测试框架，至少通过 TypeScript build 和手动 smoke 验证；如果后续引入测试，建议覆盖：

1. 前端已经实时收到 `tool_use:call_a` 后，replay 同一个 `call_a` 时不追加重复消息。
2. replay 新的 `tool_use:call_b` 时追加。
3. `tool_result:call_a` 与 `tool_use:call_a` 不互相覆盖，因为 chunkType 不同，UI id 不同。
4. `loadAgentMessages()` 返回 complete history 后，不清空当前 replay 恢复出的 runtime tool_use，或在 switch replay 后正确恢复。

### 手动验收

1. 启动后端和前端。
2. 在 `agent1` 输入会触发多个 sub_agent/tool use 的任务。
3. 看到 6 条 `tool_use` 后，立即切到 `agent2`。
4. 再切回 `agent1`。
5. 期望：6 条 `tool_use` 仍显示。
6. 对同一场景等待工具完成后再次切换。
7. 期望：不重复显示 `tool_use/tool_result`。
8. 对同一场景在工具运行中 interrupt。
9. 期望：切走再切回后，未完成 `tool_use` 不显示在历史中。

## 实施步骤

1. 修改 `backend/dispatcher.py`，删除 `_MAX_BUFFER_ENTRIES` / `_MAX_BUFFER_BYTES` 及对应淘汰逻辑。
2. 修改 `backend/dispatcher.py`，只在 `end_turn` / interrupt / error 时清空 replay buffer。
3. 修改 `backend/factories/agent_factory.py#get_messages()`，只返回完整 turn。
4. 修改 `backend/factories/agent_factory.py#get_messages()`，为 `tool_use` 和 `tool_result` 返回 `toolCallId`，必要时返回 `messageId`。
5. 修改 `frontend/src/types/index.ts`，扩展 `Message` 字段。
6. 在前端新增稳定 UI id helper。
7. 修改 `loadAgentMessages()`，HTTP history 中 tool_use/tool_result 使用稳定 id。
8. 新增 `upsertMessage()`，用于 runtime replay/live 事件去重。
9. 修改 `ChatWindow` 中 `completed_tool_use` 和 `tool_results` 处理逻辑，使用 `toolCallId` 和 `upsertMessage()`。
10. 添加后端单测。
11. 运行验证命令。

## 建议验证命令

后端相关：

```bash
python -m pytest tests/unit/backend/test_dispatcher.py tests/unit/backend/test_agent_factory_messages.py
ruff check backend tests
```

如果前端代码被修改：

```bash
cd frontend
npm run lint
npm run build
```

完整相关 gate：

```bash
python -m pytest tests
ruff check .
mypy bbagent backend
```

## 风险与缓解

### 风险一：dispatcher buffer 变大

因为 buffer 会保留整个未完成 turn，而不是每个 `completed_message` 后清空，长时间运行的 turn 可能产生更多 chunks。

本方案要求删除 dispatcher replay buffer 的条数和字节数截断限制，避免未完成 turn 被截断后无法完整恢复 UI 现场。

缓解：

- buffer 只保留当前未完成 turn，`end_turn` / interrupt / error 后立即清空。
- 如果未来发现极长 turn 带来内存压力，再单独设计可观测的 runtime snapshot 截断策略；截断必须显式告知前端，不能静默丢弃。

### 风险二：streaming text replay 可能产生重复 assistant 文本

因为 `get_messages()` 只返回完整 turn，HTTP history 不再和当前未完成 turn 的 text/thinking replay 重叠，这个风险会明显降低。

仍然可能存在的重复来源是 WebSocket live/replay 本身：前端已经实时收到一段 text/thinking 后，切换或重连又 replay 同一批 chunks。当前前端依赖 `currentAssistantMsgIdRef` 和随机/临时 id，缺少后端稳定 `message_id` 时，无法像 tool_use 一样精确去重。

最小方案：

- 先确保 tool_use/tool_result 去重。
- text/thinking replay 保持现状。

后续增强：

- WebSocket text/thinking chunk 增加 `message_id`。
- 前端使用 `messageId` 构造稳定 id，例如 `assistant:{messageId}:text`、`thinking:{messageId}`。

### 风险三：HTTP committed message 被 runtime message 覆盖为 runtime

缓解：

- upsert merge 时 committed 优先。
- 如果 existing message 已经是 committed，runtime replay 只能补字段，不改变其 committed 性质。

### 风险四：tool result 缺少 id

`ToolMessage.id` 应对应 `ToolUseBlock.id`。如果某些旧数据缺少 id：

- `toolCallId` 为空时 fallback 到 `hist-${i}` 或随机 id。
- 去重能力只对有 `toolCallId` 的新消息生效。

## 验收标准

- agent 运行中产生多个 `tool_use` 后，切换到其他 agent 再切回，未完成 turn 的 `tool_use` 仍显示。
- 正常完成后，切换回来不重复显示 `tool_use/tool_result`。
- interrupt 后，未完成 `tool_use` 不进入 HTTP history，也不会通过 replay 再显示。
- `GET /agents/{id}/messages` 只返回完整 turn 的 committed session history。
- dispatcher replay buffer 不再因条数或字节数限制静默截断当前未完成 turn。
- 默认测试不依赖真实 LLM、MCP server 或外部 API。
