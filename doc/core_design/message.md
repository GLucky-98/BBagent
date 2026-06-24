# `bbagent/core/message.py` 设计文档

> 适用版本：`bbagent/core/message.py`（截至 2026-06-24）
> 目标读者：需要扩展消息类型、修改会话持久化格式、或维护上层 `Agent` 对话历史消费的开发者。

## 1. 模块定位

定义 BBagent 框架中**所有对话数据**的内部表示：消息块（`ContentBlock` 家族）、消息（`Message` 家族）、轮次（`Turn`）、会话（`Session`），以及消息序列化、归一化、token 估算等工具方法。它是上层 `Agent` / `Model` / 上下文压缩 hook 共同依赖的数据契约层。

## 2. 类继承关系

```
ContentBlock (基础类)
   ├── TextBlock           # 文本块
   ├── ImageBlock          # 图像块（base64）
   ├── AudioBlock          # 占位（未实现）
   ├── DocumentBlock       # 占位（未实现）
   └── ToolUseBlock        # 工具调用

ContentOrigin = Literal["user", "model", "tool", "system"]

Message (基础类)
   ├── HumanMessage        # 用户输入
   ├── ModelMessage        # 模型输出（唯一有 tool_calls / thinking / usage）
   └── ToolMessage         # 工具执行结果

Turn (dataclass)           # 一轮对话：user → assistant（+ 工具往返）
Session (class)            # 多轮会话：Turn 列表 + 持久化 + 窗口 + fork
```

模块级还有工具函数 `estimate_message_tokens(msg)`，按"序列化 JSON 字节数 / 3"估算 token。

---

## 3. `ContentBlock` 家族

`ContentBlock` 是消息 `content` 字段的最小单元，`@dataclass` 装饰。

### 3.1 基础类 `ContentBlock`

| 成员 | 作用 |
| --- | --- |
| `origin: ContentOrigin` | 标记这个块由谁产生（user / model / tool / system），驱动 `_normalize_content` 的归一化方向 |
| `to_dict() → dict` | 抽象方法，由子类实现 |
| `from_dict(data, default_origin) → ContentBlock` (static) | 反序列化工厂；按 `data['type']` 分发到具体子类 |

### 3.2 子类对比

| 子类 | 关键字段 | `type` | `origin` 默认 | 用途 |
| --- | --- | --- | --- | --- |
| `TextBlock` | `text: str` | `"text"` | `"user"` | 纯文本 |
| `ImageBlock` | `data: str`（base64）、`image_type: str` | `"image"` | `"user"` | 图像 |
| `AudioBlock` | （未实现） | — | — | 占位 |
| `DocumentBlock` | （未实现） | — | — | 占位 |
| `ToolUseBlock` | `id: str`、`name: str`、`input: dict` | `"tooluse"` | `"model"` | 工具调用 |

`from_dict` 内的 `block_type` ↔ 子类映射：

```
"text"    → TextBlock
"image"   → ImageBlock
"tooluse" → ToolUseBlock
```

未知类型抛 `ValueError`。`AudioBlock` / `DocumentBlock` 当前不参与反序列化路径。

---

## 4. `Message` 家族

`Message` 不是 dataclass，但子类都是。它承载一段对话，并提供**类级别静态方法**做内容归一化与序列化——所有子类共享。

### 4.1 基础类 `Message` 提供的工具方法（全部 `@staticmethod`）

| 方法 | 作用 |
| --- | --- |
| `_serialize_content(content) → List[dict]` | 把 `str` 转为 `[{type:text,...}]` 或直接序列化 `List[ContentBlock]`；空字符串返回 `[]` |
| `_deserialize_content(content_data, default_origin) → List[ContentBlock]` | 反向操作；列表里若已是 `ContentBlock` 实例则原样保留 |
| `_normalize_content(content, default_origin) → List[ContentBlock]` | 把 `str / List[ContentBlock] / List[dict]` 统一归一化为 `List[ContentBlock]`；缺 `origin` 的块会被补成 `default_origin` |

`Message.from_dict(data) → Message`（static）按 `data['role']` 分发：

```
"user"  → HumanMessage._from_dict
"model" → ModelMessage._from_dict
"tool"  → ToolMessage._from_dict
```

未知 role 抛 `ValueError`。

### 4.2 子类对比

| 字段 | `HumanMessage` | `ModelMessage` | `ToolMessage` |
| --- | --- | --- | --- |
| `role` | `"user"` | `"model"` | `"tool"` |
| `id` | — | `str`（vendor 响应 id） | `str`（对应的 tool_use id） |
| `name` | — | — | `str`（工具名） |
| `content` | `List[ContentBlock] \| str` | `List[ContentBlock] \| str` | `List[ContentBlock] \| str` |
| `stop_reason` | — | `str` | — |
| `usage_data` | — | `dict` | — |
| `raw_json` | — | `str` | — |
| `thinking` | — | `str` | — |
| `thinking_signature` | — | `str` | — |
| `tool_calls` | — | `List[ToolUseBlock]` | — |
| `input_tokens` | — | `int` | — |
| `output_tokens` | — | `int` | — |
| `timestamp` | `int`（now） | `int`（now） | `int`（now） |
| `__post_init__` | `_normalize_content(content, "user")` | `_normalize_content(content, "model")` + 把 `user` 块改成 `model` + 归一化 `tool_calls` | `_normalize_content(content, "tool")` + 把 `user` 块改成 `tool` |

### 4.3 关键设计点

- **`ModelMessage` 是唯一带 `tool_calls` / `thinking` / token 计量的子类**——这些字段是模型调用产物，`HumanMessage` / `ToolMessage` 不需要。
- **`raw_json` 保留 vendor 原始响应字符串**，便于排查 vendor 协议问题。
- **`stop_reason` 是对话状态机的关键信号**：`"end_turn"` 表示本轮结束，`"tool_use"` 表示模型在等工具结果。
- **`timestamp` 在 `__post_init__` 用 `default_factory` 注入**——每次构造自动取当前时间，不需要调用方传。

---

## 5. `Turn` — 一轮对话

`@dataclass`，承载一次"用户输入 → 模型输出（+ 工具往返）"的完整序列。

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| `messages` | `List[Message]` | 本轮所有消息（按时间序） |
| `key_content` | `List[str]` | 关键信息（被压缩时保留的"必须留"内容） |
| `is_summarized` | `bool` | 是否已被压缩为 summary |
| `summary` | `str` | 压缩后的摘要 |
| `summary_group_id` | `str` | 同组压缩轮次的分组 id（`get_visible_context` 用它去重） |
| `skip_summary` | `bool` | True 时只保留 `key_content`，不显示 summary |
| `token_count` | `int` | 本轮新增消耗的 token |
| `ever_used_tools` | `List[str]` | 本轮调用过的工具名 |
| `start_timestamp` | `int` | 起始时间 |
| `end_timestamp` | `int` | 结束时间（`end_turn` 时填） |
| `memory_extracted` | `bool` | 是否已抽到 memory hook |

### 5.1 关键属性与方法

| 成员 | 作用 |
| --- | --- |
| `is_complete` (property) | True 当且仅当 `messages` 非空 + 最后一条是 `ModelMessage` + `stop_reason == 'end_turn'` |
| `add_message(msg)` | 追加消息到 `messages` |
| `to_merged_blocks(header=None) → List[ContentBlock]` | 把本轮消息合并成"系统视角"的内容块（带角色前缀），用于"前轮未完成时合并进本轮"的场景 |
| `DEFAULT_MERGE_HEADER` | `"[Context from an incomplete previous turn - merged into this message]"` |
| `CURRENT_REQUEST_LABEL` | `"[Current request]"` |

合并策略（`to_merged_blocks`）：

- 每条 `HumanMessage` 文本前加 `[User]`
- `ModelMessage` 文本前加 `[Assistant]`，每个 `tool_calls` 项加 `[Assistant] [ToolCall name(input)]`
- `ToolMessage` 文本前加 `[Tool(name)]`，无 name 时退化为 `[Tool]`
- 所有块的 `origin` 强制改为 `"system"`，避免被误判为用户/模型来源

---

## 6. `Session` — 多轮会话

`Session` 不是 dataclass，构造时签名 `(dir, id, turns)`，全部可选。`Session.create(session_dir)` 是工厂方法，自动分配 id、建目录、写元数据。

### 6.1 实例属性

| 属性 | 作用 |
| --- | --- |
| `id` | 会话 id，文件名后缀（`{id}.jsonl` + `{id}.md`） |
| `dir` | 会话目录；None 表示内存 session（不可持久化 / 不可 fork） |
| `turns` | `List[Turn]`，所有轮次 |
| `timestamp` | 创建时间字符串 |
| `window_start` | 上下文窗口起点索引（压缩过的轮次被切掉） |
| `compress_turn_count` | 已压缩的轮次数 |
| `total_input_cost_tokens` / `total_output_cost_tokens` | 累计 token 计量 |
| `_prev_context_total` | 内部：上次 `end_turn` 时的累计 token，用于计算 `turn.token_count` |
| `parent_session_id` / `fork_turn_index` | Fork 来源追踪 |

### 6.2 只读属性（property）

| 属性 | 作用 |
| --- | --- |
| `messages` | 拼接 `turns[window_start:]` 的所有消息 |
| `ever_used_tools` | 按出现顺序去重后的所有工具名 |
| `turn_count` | `len(turns)` |

### 6.3 关键方法

| 方法 | 作用 |
| --- | --- |
| `Session.create(session_dir) → Session` (classmethod) | 工厂：分配 id、建目录、touch messages 文件、写元数据 |
| `fork(session_root=None, at=None) → Session` | 基于当前 Session 创建独立副本；`at` 支持负数索引；纯内存 session 不能 fork |
| `add_message(message \| List[message])` | 把消息分发到对应 turn；遇 `HumanMessage` 时若上一 turn 未完成则把旧 turn 合并进新 turn |
| `get_turn(n) → Turn` | 按索引取 turn（支持负数）；越界抛 `IndexError` |
| `get_visible_context() → List[Message]` | 返回"喂给模型的可见上下文"：已压缩 turn 用 summary / key_content 注入到下一 turn 开头 |
| `get_visible_token_count() → int` | 估算可见上下文的 token |
| `save()` | 写元数据到 `{id}.md`（messages 已在 `add_message` 时增量 flush） |
| `Session.load(session_id, session_dir) → Session` (classmethod) | 从 `{id}.jsonl` + `{id}.md` 反向构造完整 Session |
| `_write_metadata()` | 把 Session 状态写成可读 markdown |
| `_flush_turn(turn)` | 把 turn 的消息追加写 `{id}.jsonl` |
| `_rebuild_token_counts()` | 重算每个 turn 的 `token_count`（基于 `end_turn` 边界） |
| `_parse_metadata(md_path) → dict` (static) | 解析 `{id}.md` 的 markdown 元数据 |

### 6.4 持久化文件

| 文件 | 格式 | 写入时机 |
| --- | --- | --- |
| `{id}.jsonl` | 每行一条消息的 `to_dict()` JSON | `add_message` 遇到 `end_turn` 的 `ModelMessage` 时 `_flush_turn` |
| `{id}.md` | 可读 markdown 元数据 | `Session.create` / `fork` / `save` |

**两文件都是兼容性表面**：扩展消息字段时必须考虑旧 `jsonl` 的 `_from_dict` 兼容与旧 `md` 的 `_parse_metadata` 兼容。

### 6.5 `add_message` 的轮次边界规则

```
收到 HumanMessage：
  若上一 turn 未完成（!=end_turn）：
    → 把上一 turn 通过 to_merged_blocks() 合并成本轮 HumanMessage 的前缀
    → 继承上一 turn 的 ever_used_tools
    → 移除上一 turn，开启新 turn
  否则：
    → 直接开新 turn

收到 ModelMessage / ToolMessage：
  若没有 turn 或上一 turn 已完成：忽略（孤儿消息）
  否则：追加到上一 turn 末尾
  ModelMessage 触发 token 计量与 end_turn 检查
  ToolMessage 触发 ever_used_tools 登记
```

### 6.6 `get_visible_context` 的注入策略

1. 顺序遍历 `turns[window_start:]`
2. 遇到已压缩 turn：
   - `skip_summary=True`：只把 `key_content` 收集到 `collected_keys`（去重）
   - 否则：把 `summary` 收集到 `collected_summaries`（按 `summary_group_id` 去重），同时收集 `key_content`
3. 遇到第一个**未压缩** turn：把累积的 `collected_summaries` + `collected_keys` 拼成一段 `[Historical Conversation Summary] / [Key Information Preserved]` 注入到该 turn 第一条 `HumanMessage` 的开头
4. 该 turn 之后的所有 turn 原样保留

```
格式：
[Historical Conversation Summary]
---
summary1
---
summary2

[Key Information Preserved]
- key1
- key2
```

---

## 7. 关键设计点

1. **`origin` 字段驱动归一化**：`ContentBlock.origin` 在 `__post_init__` 里被强制改成"消息角色对应的默认值"，避免上游错误地把 model 块标成 user。系统注入的块一律改成 `"system"`。
2. **`Message` 的类级静态方法是公共工具**：`_normalize_content` / `_serialize_content` / `_deserialize_content` 是协议层与序列化层共用的转换函数，子类不应绕过。
3. **`ModelMessage` 字段是 vendor 协议的"翻译结果"**：`raw_json` 保原始响应便于排查，`tool_calls` / `thinking` / `usage_data` 是结构化产物；其他两个 `Message` 子类刻意保持精简。
4. **`Turn` 是压缩与 token 计量的基本单位**：`is_complete` 决定轮次边界，`token_count` 在 `end_turn` 处增量累加，`summary` + `key_content` 共同决定 `get_visible_context` 的注入内容。
5. **`Session.add_message` 是轮次边界与可见上下文的唯一入口**：所有消息进 Session 都要走它，所以 turn 划分、token 计量、ever_used_tools 累积、jsonl flush 都集中在这里。
6. **持久化是双向兼容的边界**：`{id}.jsonl` 是行式追加（按 turn flush），`{id}.md` 是可读元数据（手写可修改）。修改字段时**必须**同步考虑 `_from_dict` / `_parse_metadata` 的向后兼容。
7. **`fork` 复制时通过 `deepcopy` 隔离 turn**：fork 出的 Session 与原 Session 之后各自独立演进；`parent_session_id` / `fork_turn_index` 仅作来源标记，不影响后续行为。
8. **`estimate_message_tokens` 是粗估**：用 `len(utf-8 bytes) // 3` 近似，仅用于上层 token 预算预判；不替代真实 vendor 计量。
