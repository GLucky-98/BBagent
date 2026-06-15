# Memory System Optimization Implementation Plan

## 背景

当前 `built_in.memory` 已具备长期记忆写入、检索注入、会话切换提取、压缩前提取和清理能力，但还有几个语义和体验问题需要继续优化：

1. 同一段记忆可能在同一个 session 内被多次召回并注入。
2. 长 session 如果不触发压缩、也不切换 session，记忆提取会滞后。
3. `memory_extracted` 是 session/turn 级状态，但 memory store 是 agent 级状态；跨 Agent fork 时直接继承该状态会导致目标 Agent 跳过本应重新提取的 turn。
4. 后台提取需要避免重复排队和重复提取同一批 turn。

本文档整理完整修改方案。

## 目标

- 同一个 session 内，同一段记忆最多注入一次。
- 每满 5 个完整未提取 turn 后，后台触发一次记忆提取。
- `NEW_SESSION` / switch session 继续保持后台提取，不阻塞 UI。
- 跨 Agent fork 后重置新 session 的 `memory_extracted`，让目标 Agent 可以写入自己的 memory store。
- 不新增 session 级持久字段记录已召回 memory id。
- 避免依赖可复用的数字 memory id。

## 非目标

- 本方案不处理 `runtime_system_prompt`。
- 本方案不改变压缩前同步提取语义，`BEFORE_STREAM` 压缩前提取仍保持同步。
- 本方案不把 memory context 改成 ephemeral model input；当前仍基于注入到 user message 的前缀工作。

## 方案一：Session 内同一段记忆最多召回一次

### 问题

使用 memory id 记录已召回记忆不可靠。当前 memory id 由现存 ChromaDB id 最大值推导：

```python
next_id = max(existing_ids) + 1
```

当最大 id 被删除后，进程重启可能复用旧 id。因此不能用 `session_id -> memory_ids` 来表达“这个 session 已经召回过哪些记忆”。

### 方案

使用 memory 内容指纹作为去重 key：

```text
memory_key = blake2b(normalize(memory.content), digest_size=16)
```

同一 session 内，如果某个 `memory_key` 已出现过，则后续召回候选中过滤掉该记忆。

### 为什么不需要新增持久字段

当前 memory context 会被注入到 user message 前缀中：

```text
[Relevant memories from past messages]
- User prefers dark mode.
- User works with FastAPI.

原始用户消息...
```

因此可以从 session 历史消息中恢复该 session 已经注入过的 memory 内容，再计算 fingerprint。fork 时也天然正确：fork 复制了哪些 turn，就只继承这些 turn 中实际出现过的 memory prefix。

### 实现细节

新增工具函数，建议放在 `bbagent/built_in_hook/memory/memory_tool.py` 或新建 `bbagent/built_in_hook/memory/fingerprint.py`：

```python
def normalize_memory_text(text: str) -> str:
    return " ".join(text.split()).strip()


def memory_fingerprint(text: str) -> bytes:
    normalized = normalize_memory_text(text)
    return hashlib.blake2b(normalized.encode("utf-8"), digest_size=16).digest()
```

在 `MemoryRuntime` 中维护运行时 cache：

```python
seen_memory_keys_by_session: dict[str, set[bytes]]
scanned_turn_count_by_session: dict[str, int]
```

提供方法：

```python
def get_seen_memory_keys(session) -> set[bytes]:
    # cache miss 时扫描全部 turn
    # cache hit 时只扫描新增 turn

def mark_memory_keys_seen(session_id: str, keys: list[bytes]):
    # 成功注入后写入 runtime cache
```

解析逻辑：

- 只扫描 user message。
- 只处理以 `INJECT_USER_PREFIX` 前缀开头的文本块。
- 对 `- ` 开头的 memory bullet 提取内容。
- 对提取出的内容计算 fingerprint。

当前注入内容建议也统一格式化，避免多行 memory 影响解析：

```python
def format_memory_for_injection(content: str) -> str:
    return normalize_memory_text(content)
```

### 召回流程调整

`inject_memory_context()` 增加参数：

```python
session_id: str
seen_memory_keys: set[bytes]
```

候选过滤流程：

```text
1. 读取 seen_memory_keys
2. hybrid search oversampling 召回候选
3. 为每个 candidate.content 计算 memory_key
4. 过滤掉 memory_key in seen_memory_keys 的候选
5. 截断到 max_candidates
6. 交给 MemoryInjector selector
7. selector 选中的 memory 成功注入后，mark_memory_keys_seen()
```

### Oversampling

为避免已召回记忆占满候选池，需要 oversampling：

```python
oversample_factor = 3
candidate_fetch = min(max_candidates * oversample_factor, 200)
```

过滤后再截断到 `max_candidates`，确保 selector prompt 不膨胀。

### 性能和内存

使用 incremental cache 后，通常每轮只扫描新增 turn。缓存可随时丢弃，因为可以从 session prefix 恢复。

粗略内存估算：

```text
每个 fingerprint 使用 16 bytes digest，Python set 有额外开销。
500 条已召回 memory / session 通常在几十 KB 量级。
100 个缓存 session 通常在数 MB 到十 MB 量级。
```

可选优化：

- 对 `seen_memory_keys_by_session` 做 LRU。
- 超过最大 session cache 数后丢弃最旧项，下次按 session 历史重建。

## 方案二：每 5 轮自动触发记忆提取

### 问题

当前记忆提取主要发生在：

- `NEW_SESSION`
- 压缩前 `BEFORE_STREAM`

如果用户长期停留在同一个 session，且上下文未触发压缩，记忆写入会滞后。

### 方案

新增 `AFTER_RUN` hook：每当完整未提取 turn 数达到阈值时，后台触发提取。

默认阈值：

```python
extract_turn_interval: int = 5
```

加入 `BuiltinHookConfig`，并暴露到 hook config descriptor。

### 实现细节

在 `create_memory_hook()` 返回值中新增第五个 hook：

```python
extract_memory_after_interval
```

注册：

```python
hook.register(func=extract_memory_after_interval, hook_type=HookType.AFTER_RUN, priority=100)
```

判断逻辑：

```python
completed_unextracted = [
    (idx, turn)
    for idx, turn in enumerate(session.turns)
    if turn.is_complete and not turn.memory_extracted
]

if len(completed_unextracted) >= extract_turn_interval:
    claimed = runtime.claim_turns(session.id, completed_unextracted)
    if len(claimed) >= extract_turn_interval:
        runtime.schedule(...)
```

复用 `NEW_SESSION` 后台提取 job，避免重复实现。

### 与 NEW_SESSION 的关系

- `AFTER_RUN`：只提取完整 turn。
- `NEW_SESSION`：提取所有未提取 turn，作为兜底。
- 两者都使用 `runtime.claim_turns()`，同一 turn 不会重复排队。

## 方案三：避免重复提取同一批 turn

### 当前基础

已有 `MemoryRuntime`：

```python
inflight_turns: set[tuple[str, int]]
completed_turns: set[tuple[str, int]]
```

继续强化这套机制：

```python
claim_turns(session_id, indexed_turns)
release_turns(session_id, indexes)
mark_turns_completed(session_id, indexes)
```

### 规则

- turn 已在 `inflight_turns` 中：不重复排队。
- turn 已在 `completed_turns` 中：本进程内不重复排队。
- 后台提取成功后：
  - 标记 turn.memory_extracted = True。
  - 保存 metadata 或更新当前活跃 session 对象。
  - 调用 `mark_turns_completed()`。
- 后台提取失败后：
  - 不标记 completed。
  - 释放 inflight，下次可重试。

### 持久化注意

`completed_turns` 只是运行时缓存，最终持久状态仍是 session metadata 中的 `memory_extracted`。

如果后台任务完成时该 session 当前活跃：

- 只更新活跃 session 对象。
- 不直接用旧对象覆盖 metadata。
- 由后续正常 session save 持久化。

如果该 session 非活跃：

- 从磁盘重新加载最新 session。
- 只标记对应 turn 的 `memory_extracted`。
- 保存 metadata。

## 方案四：跨 Agent fork 时重置 memory_extracted

### 问题

`memory_extracted` 是 session/turn 级状态，但 memory store 是 agent 级状态。

跨 Agent fork 时，如果新 session 继承了源 session 的 `memory_extracted=True`，目标 Agent 会认为这些 turn 已经提取过，从而跳过提取。但目标 Agent 的 memory store 中并没有这些记忆。

### 方案

在 `SessionFactory.fork_at_turn()` 中，后端已经知道：

- 源 session 属于哪个 agent：`src_idx.agent_id`
- 目标 agent：`target_agent_id`

fork 后判断：

```python
source_agent_id = src_idx.agent_id if src_idx else None

if source_agent_id and target_agent_id != source_agent_id:
    for turn in new_session.turns:
        turn.memory_extracted = False
```

然后保存新 session。

### 修改位置

文件：

```text
backend/factories/session_factory.py
```

位置：

```python
# 3. 执行 fork
new_session = source.fork(session_root=fork_root, at=turn_index)

# 4. 写入 fork 来源信息
new_session.parent_session_id = session_id
new_session.fork_turn_index = turn_index
new_session.save()
```

调整为：

```python
new_session = source.fork(session_root=fork_root, at=turn_index)

source_agent_id = src_idx.agent_id if src_idx else None
if source_agent_id and target_agent_id != source_agent_id:
    for turn in new_session.turns:
        turn.memory_extracted = False

new_session.parent_session_id = session_id
new_session.fork_turn_index = turn_index
new_session.save()
```

### 与 memory prefix 去重的关系

跨 Agent fork 后，user messages 中已有的 memory prefix 会被复制。方案一会从这些 prefix 恢复“已召回过的 memory fingerprint”。

这不会和重置 `memory_extracted` 冲突：

- `memory_extracted=False`：允许目标 Agent 从 fork 历史中重新提取长期记忆到自己的 memory store。
- prefix fingerprint：避免目标 Agent 在同一个 fork session 中重复注入已经出现在上下文里的记忆文本。

二者解决的是不同问题。

## 配置变更

新增 `BuiltinHookConfig` 字段：

```python
extract_turn_interval: int = 5
inject_oversample_factor: int = 3
inject_oversample_cap: int = 200
```

建议暴露到 `backend/api/hooks.py`：

- `extract_turn_interval`: number
- `inject_oversample_factor`: number
- `inject_oversample_cap`: number

默认值放在 `bbagent/built_in_hook/__init__.py`。

## 测试计划

### 1. Session 内同一段记忆只注入一次

场景：

1. 创建 session。
2. Memory store 中有 memory A。
3. 第一条用户消息召回并注入 A。
4. 第二条用户消息仍与 A 强相关。

期望：

- 第二次候选过滤时 A 被过滤。
- A 不再进入 selector prompt。
- 用户消息中不会再次注入 A。

### 2. Fork 后从 prefix 恢复已召回记忆

场景：

1. 源 session 前 3 个 turn 中注入过 memory A。
2. 从第 3 个 turn fork。
3. fork session 中发送相关问题。

期望：

- A 从 fork 后 session 历史 prefix 中恢复为 seen。
- A 不会再次注入。

### 3. Fork 到注入前的 turn

场景：

1. 源 session 第 5 个 turn 才注入 memory A。
2. 从第 3 个 turn fork。

期望：

- fork session 不包含 A 的 prefix。
- A 可以在 fork session 中被召回。

### 4. 每 5 轮自动提取

场景：

1. 同一 session 完成 5 个 turn。
2. 不触发 new session，不触发压缩。

期望：

- `AFTER_RUN` hook 投递后台提取任务。
- 5 个 turn 被 claim。
- 提取完成后标记 `memory_extracted=True`。

### 5. 未满 5 轮不提取

场景：

1. 同一 session 完成 4 个 turn。

期望：

- 不投递 interval extraction job。

### 6. NEW_SESSION 与 AFTER_RUN 不重复提取

场景：

1. 第 5 轮后 `AFTER_RUN` 已投递提取。
2. 用户立即 new session。

期望：

- `NEW_SESSION` 通过 `runtime.claim_turns()` 跳过 inflight turn。
- 同一 turn 不重复提取。

### 7. 跨 Agent fork 重置 memory_extracted

场景：

1. Agent A 的 session turn 均为 `memory_extracted=True`。
2. fork 到 Agent B。

期望：

- 新 session 的所有 turn `memory_extracted=False`。
- Agent B 后续可以提取这些 turn 到自己的 memory store。

### 8. 同 Agent fork 保留 memory_extracted

场景：

1. Agent A 的 session fork 到 Agent A。

期望：

- 新 session 保留原 turn 的 `memory_extracted` 状态。

## 实施顺序

1. 实现 memory fingerprint 与 prefix parser。
2. 扩展 `MemoryRuntime` 的 session seen cache。
3. 修改 `inject_memory_context()`，支持 seen filter 与 oversampling。
4. 在 `inject_memory_hook()` 中传入 session，并在成功注入后标记 seen keys。
5. 增加 `extract_turn_interval` 配置。
6. 增加 `AFTER_RUN` 自动提取 hook。
7. 修改 `SessionFactory.fork_at_turn()`，跨 Agent fork 时重置 `memory_extracted`。
8. 补充测试。

## 风险与注意事项

- Prefix parser 依赖当前注入格式。如果未来改为 ephemeral memory context，需要替换为显式 session metadata 或 runtime state 恢复机制。
- 如果 memory 内容非常长或包含多行，建议注入前统一 `normalize_memory_text()`，确保 fingerprint 和 prefix parser 稳定。
- Oversampling 不应无限扩大 selector prompt，过滤后仍应截断到 `max_candidates`。
- `memory_extracted` 跨 Agent reset 只应发生在 fork 目标 Agent 与源 Agent 不同的情况下；同 Agent fork 应保留原状态。
