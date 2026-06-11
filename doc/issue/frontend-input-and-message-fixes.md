# 前端消息显示与输入保存问题修复方案

## 背景

经过对前端消息处理机制的全面审查，发现以下三个问题需要修复：

1. **多 ContentBlock 的 user message 被拆分为多条独立消息显示**：历史消息加载时，对 `HumanMessage` 的 list content 逐 block 输出，导致一条用户消息在前端表现为多条。
2. **历史消息 timestamp 显示错误**：后端使用秒级时间戳（Python `datetime.timestamp()`），前端期待毫秒级时间戳（JS `new Date()`），单位差 1000 倍导致所有历史消息显示为错误时间。
3. **切换 Agent 时输入框内容丢失**：当前 `input` 是 `ChatWindow` 的组件局部状态，在特定切换场景下会丢失。

## 目标

- 历史消息中，一条 `HumanMessage` 的多个 ContentBlock 在前端始终合并为一条消息显示。
- 历史消息的 timestamp 正确显示为实际时间。
- 每个 Agent 的输入框内容独立保存，切换 Agent（含 Team ↔ Single 切换）时不丢失已输入的文字。

---

## 修复一：HumanMessage 多 ContentBlock 合并输出

### 现状

`backend/factories/agent_factory.py` 的 `get_messages()` 方法（[L867-L883](file:///Users/gonglin/Desktop/BBagent/backend/factories/agent_factory.py#L867-L883)）：

```python
content = msg_dict.get("content", "")
display_role = "assistant" if msg_dict.get("role") == "model" else msg_dict.get("role", "")
if isinstance(content, str):
    if content.strip():
        result.append({"role": display_role, "content": content, ...})
elif isinstance(content, list):
    for block in content:
        bt = block.get("type", "")
        if bt == "text":
            text = block.get("text", "")
            if text.strip():
                result.append({"role": display_role, "content": text, ...})
```

`HumanMessage.content` 可能是 `List[ContentBlock]`（如 `[TextBlock("part1"), TextBlock("part2")]`）。上述逻辑遍历 list 后每个 text block 独立 append 到 `result`，前端收到多条 `role: "user"` 的消息，分别渲染为独立的 user turn。

### 根因

`get_messages()` 对 `HumanMessage` 和 `ModelMessage` 使用了相同的 list content 处理逻辑。`ModelMessage` 拆分是合理的（区分 text / thinking / tool_use），但 `HumanMessage` 不应该拆分。

### 修复方案

**修改文件**：`backend/factories/agent_factory.py` — `get_messages()` 方法

在处理 list content 之前，判断消息角色。对于 `role == "user"` 的 `HumanMessage`，将所有 text block 的内容合并后用 `\n` 拼接为一条消息输出。

**修改后的代码**：

```python
content = msg_dict.get("content", "")
display_role = "assistant" if msg_dict.get("role") == "model" else msg_dict.get("role", "")
if isinstance(content, str):
    if content.strip():
        result.append({"role": display_role, "content": content, "source_agent": agent.name, "timestamp": ts})
elif isinstance(content, list):
    # HumanMessage: 合并所有 text block 为一条消息，不拆分
    if msg_dict.get("role") == "user":
        merged = "\n".join(
            b.get("text", "") for b in content if b.get("type") == "text"
        )
        if merged.strip():
            result.append({"role": "user", "content": merged, "source_agent": agent.name, "timestamp": ts})
    else:
        # ModelMessage: 保持逐 block 拆分（text / thinking / tool_use 需要独立控制折叠）
        for block in content:
            bt = block.get("type", "")
            if bt == "text":
                text = block.get("text", "")
                if text.strip():
                    result.append({"role": display_role, "content": text, "source_agent": agent.name, "timestamp": ts})
```

### 影响范围

- 仅影响历史消息加载（`GET /api/agents/{id}/messages`）的返回格式
- 不影响 WebSocket 流式消息
- 不影响 `ModelMessage` 的多 block 拆分逻辑
- 前端无需改动

---

## 修复二：历史消息 timestamp 单位统一

### 现状

**后端**（`bbagent/core/message.py`）：

```python
# HumanMessage / ModelMessage / ToolMessage 均使用：
timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))
```

Python `datetime.timestamp()` 返回的是**秒级浮点数**（如 `1749600000.123`），`int()` 截断后为秒级整数（`1749600000`）。

**前端**（`frontend/src/components/ChatWindow.tsx`）：

```typescript
const ts = new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
```

JavaScript `new Date()` 构造函数期望的数值参数是**毫秒**。后端传秒级值（`1749600000`）被前端当作毫秒解析，产生错误的 1970 年日期，`toLocaleTimeString` 只提取时分后显示为固定值。

**注意**：WebSocket 流式消息中使用 `Date.now()`（前端，毫秒），这部分时间是正确的。只有 HTTP 加载历史消息时出现此问题。

### 修复方案

**方案选择**：在后端 `get_messages()` 中统一乘以 1000，不修改核心 message 模块的 timestamp 语义。

**理由**：
1. 核心 message 模块的秒级 timestamp 用于 session 持久化和内部逻辑（`Turn.start_timestamp`、`Turn.end_timestamp`），改动影响面大
2. 前端流式消息已经使用 `Date.now()`（毫秒），后端统一输出毫秒可保持一致性
3. 只需修改一个输出点，改动最小

**修改文件**：`backend/factories/agent_factory.py` — `get_messages()` 方法

在构造每条 result 时，将 `ts` 乘以 1000：

```python
def get_messages(self, agent_id: str) -> list[dict]:
    agent = self.agents.get(agent_id)
    if not agent or not agent.session:
        return []
    result = []
    for turn in agent.session.turns:
        for msg in turn.messages:
            msg_dict = msg.to_dict()
            ts = msg_dict.get("timestamp", 0) * 1000  # 秒 → 毫秒
            # ... 后续逻辑不变
```

### 影响范围

- 仅影响 `get_messages()` 的返回值
- `input_event` 的 timestamp、`tool_use`/`tool_result` 的 timestamp 也会同步修正
- 不影响 session 磁盘持久化格式（仍保持秒级）
- 前端无需改动

---

## 修复三：输入框内容按 Agent 独立保存

### 现状

`ChatWindow` 中的输入框状态：

```typescript
// frontend/src/components/ChatWindow.tsx L471
const [input, setInput] = useState("");
```

`input` 是 `ChatWindow` 组件内部的局部状态。

**当前行为**：
- Single Agent ↔ Single Agent 切换：`ChatWindow` 组件不卸载，`input` 保留 ✓
- Single Agent → Team Chat 切换：`ChatWindow` 卸载，`input` 丢失 ✗
- Session 切换：组件不卸载但需要重置（当前不重置，可能残留旧 session 的输入）

### 修复方案

将 `input` 状态提升到 Zustand store，按 `agentId` 索引存储。

#### Step 1：扩展 store 类型定义

**修改文件**：`frontend/src/store/index.ts`

在 `AppState` 接口中新增：

```typescript
// 每个 agent 的输入框草稿内容（按 agentId 索引）
agentInputs: Record<string, string>;
setAgentInput: (agentId: string, value: string) => void;
clearAgentInput: (agentId: string) => void;
```

#### Step 2：实现 store actions

```typescript
agentInputs: {},

setAgentInput: (agentId, value) =>
  set((state) => ({
    agentInputs: { ...state.agentInputs, [agentId]: value },
  })),

clearAgentInput: (agentId) =>
  set((state) => {
    const next = { ...state.agentInputs };
    delete next[agentId];
    return { agentInputs: next };
  }),
```

#### Step 3：修改 ChatWindow 使用 store 中的 input

**修改文件**：`frontend/src/components/ChatWindow.tsx`

```typescript
// 替换原来的 useState("")
const selectedAgent = useSelectedAgent();
const agentInput = useAppStore((s) => s.agentInputs[selectedAgent?.id || ""] || "");
const setAgentInput = useAppStore((s) => s.setAgentInput);

// textarea 的 value/onChange 改为：
<textarea
  value={agentInput}
  onChange={(e) => {
    const value = e.target.value;
    setAgentInput(selectedAgent?.id || "", value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }}
  // ...
/>
```

#### Step 4：Session 切换时清空输入

Session 切换应该重置输入框。在 session 切换的 `useEffect` 中增加清理：

```typescript
// useEffect for session switch
useEffect(() => {
  if (!selectedAgent) return;
  // ... 现有清理逻辑
  setAgentInput(selectedAgent.id, "");
  loadAgentMessages(selectedAgent.id);
}, [selectedAgent?.currentSessionId]);
```

### 影响范围

- `ChatWindow` 组件：`input` state → store
- `TeamChatWindow` 组件（可选）：同理迁移
- Agent 删除时需清理对应 `agentInputs` 条目（在 `removeAgent` 中调用 `clearAgentInput`）
- 不影响其他组件

---

## 涉及文件清单

| 文件 | 修改内容 |
|------|---------|
| `backend/factories/agent_factory.py` | 修复一：HumanMessage list content 合并输出 |
| `backend/factories/agent_factory.py` | 修复二：timestamp 秒→毫秒 (*1000) |
| `frontend/src/store/index.ts` | 修复三：新增 `agentInputs` state 和 actions |
| `frontend/src/components/ChatWindow.tsx` | 修复三：改用 store 中的 input，session 切换时清空 |
| `frontend/src/components/ChatWindow.tsx` | 修复三：`handleSend` 中重置输入改用 store action |

## 测试要点

### 修复一
- 构造一个包含多个 ContentBlock 的 HumanMessage（可通过修改已有 session 的 JSONL 文件），加载历史，验证前端只显示一条 user message 且内容为多 block 合并
- 验证 ModelMessage 的多 block 拆分不受影响

### 修复二
- 检查现有 session 的历史消息时间是否与消息实际发生时间一致
- 检查流式消息时间不受影响

### 修复三
- 在 Agent A 输入文字 → 切换到 Agent B → 切回 Agent A，验证输入框内容仍在
- 在 Agent A 输入文字 → 切换到 Team → 切回 Agent A，验证输入框内容仍在
- 在 Agent A 输入文字 → 清空 → 确认 store 中对应条目被删除
- 删除 Agent A → 确认 store 中 agentInputs[A] 被清理
