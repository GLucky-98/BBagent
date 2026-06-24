# `bbagent/core/agent.py` 设计文档

> 适用版本：`bbagent/core/agent.py`（截至 2026-06-24）
> 目标读者：需要扩展 Agent 行为、定制 hook 链、或集成 sub-agent 的开发者。

## 1. 模块定位

`agent.py` 是 BBagent 的"对话执行核心"。它把 `Model`（推理）、`Session`（记忆）、`Tool` / `Skill`（行动）、`AgentHook`（生命周期）、`InputChannel`（事件源）这几条线串成一个可运行的实体：

- **`Agent`** — 完整的有状态长生命周期 agent：维护 session、流式推理、工具往返、hook 链、事件循环、中断恢复。
- **`SubAgent`** — 轻量级一次性 agent：无 session、不开事件循环、一次性 `async_invoke` + 工具循环，由父级（通常是 `built_in_tool/sub_agent`）当工具调用。
- **`AgentConfig`** — 构造 `Agent` 的配置包。
- **`AgentState`** — 状态机枚举（`Ready` / `Waiting` / `Running` / `Error`）。

## 2. 整体结构

```
AgentConfig (dataclass)   ← 配置入口
       │
       ▼
AgentState (dataclass)    ← 状态枚举
       │
       ▼
Agent (class)             ← 完整长生命周期 agent
   ├── 会话管理  (Session / load_session / new_session)
   ├── 模型调用  (construct_model_input → Model → stream_tool_loop)
   ├── 工具执行  (tool_execute, 并行 task)
   ├── Hook 链   (AgentHook: NEW_SESSION / BEFORE_STREAM / ON_TOOL_* / ON_MESSAGE / ON_ERROR / AFTER_RUN …)
   ├── 事件循环  (start / _handle_event / stop / interrupt)
   ├── Runtime prompt 层  (set / remove / render, 带 order)
   ├── Timer 调度  (add_timer / list / update / start / stop / cancel)
   └── 状态机  (state: Ready / Waiting / Running / Error)

SubAgent (class)          ← 轻量子 agent（无 session、无事件循环）
```

---

## 3. `AgentConfig`

`@dataclass`，构造 `Agent` 的配置包。

| 字段 | 类型 | 默认 | 作用 |
| --- | --- | --- | --- |
| `model` | `Model` | 必填 | 推理后端 |
| `base_dir` | `Path \| str` | `Path.cwd()` | agent 工作目录（含 `system_prompt.md` / `runtime_prompts.md` / `session/`） |
| `system_prompt` | `str` | `""` | 系统提示词；首次构造时写入 `system_prompt.md` |
| `name` | `str` | `""` | agent 名称；空时 `__post_init__` 自动生成 `Agent_{timestamp}_{8hex}` |
| `session` | `Session` | `None` | 预加载的会话；空时首次 `run` / `start` 时通过 `_ensure_session` 懒建 |
| `tools` | `List[Tool]` | `None → []` | 工具列表；`add_tools` 时按名字注册并排序 |
| `skills` | `List[Skill]` | `None → []` | 技能列表；存在时自动注册内置 `load_skill` 工具 |

`__post_init__` 还会在 `base_dir` 不是以 `name` 结尾时，把 `base_dir` 自动拼接成 `base_dir / name`——即"同一个 base_dir 可以承载多个 agent"。

---

## 4. `AgentState`

`@dataclass`，状态机枚举（实际是字符串常量）。

| 状态 | 含义 |
| --- | --- |
| `Ready` | 空闲，可接收 `run` 或 `start` |
| `Waiting` | `start` 已启动事件循环、正在 `input.queue.get()` 阻塞等待事件 |
| `Running` | 正在处理一个事件（`run` / `_handle_event` 中） |
| `Error` | 事件循环异常退出 |

状态由 `start` / `run` / `_handle_event` / `stop` 流转；`stream_tool_loop` 异常时也会被设为 `Error`。

---

## 5. `Agent` — 实例属性

按职责分组。

### 5.1 基础属性

| 属性 | 作用 |
| --- | --- |
| `name` | agent 名字 |
| `model` | 推理后端，可通过 `change_model` 切换 |
| `base_dir` | 工作目录；`change_base_dir` 时会把 `system_prompt.md` / `runtime_prompts.md` / `session/` 整体迁过去 |
| `system_prompt` / `system_prompt_path` | 系统提示词与其落盘文件 |
| `session_dir` | session 子目录 |
| `session` | 当前会话；可由 `set_session` / `load_session` / `new_session` 替换 |
| `state` | 状态机当前值 |

### 5.2 工具 / 技能

| 属性 | 作用 |
| --- | --- |
| `tools: dict[str, Tool]` | 按名字索引的工具表，名字有序 |
| `skills: dict[str, Skill]` | 按名字索引的技能表 |
| `skill_prompt` | 技能摘要（`name` + `description` 列表），作为 runtime prompt 注入 |

### 5.3 Runtime prompt 层

| 属性 | 作用 |
| --- | --- |
| `runtime_prompts: dict[str, dict]` | key → `{content, order}`，按 `(order, key)` 排序后拼到 system prompt 后面 |
| `runtime_prompts_path` | 渲染结果落盘到 `runtime_prompts.md`，**只供检查**，不参与回读 |
| `team_prompt` / `teammate_prompt` | 团队模式下由 `team.py` 注入 |
| `runtime_context_providers: list[Callable[[], str]]` | 每次构造 `Model_Input` 时回调，按"最近一条 HumanMessage 的内容前缀"插入 |

### 5.4 调度与生命周期

| 属性 | 作用 |
| --- | --- |
| `hook: AgentHook` | 生命周期扩展点（详见 `hook.py`） |
| `input: InputChannel` | 事件源（用户消息、timer、外部事件） |
| `_output_callback` | 注册一个 chunk 回调（同步或 async 都可） |
| `_loop_running` | 事件循环在跑标志 |
| `_interrupt_event` | 单次中断（流式 / 工具往返中途） |
| `_stop_event` | 整体停止（终止事件循环） |
| `_active_tool_tasks: set[asyncio.Task]` | 当前正在执行的工具任务集合，用于 `interrupt` / `stop` 时统一 cancel |
| `logger: AgentLogger` | 结构化日志，绑定 `base_dir` |

---

## 6. `Agent` — 方法分类

按职责分组，标注核心入口。

### 6.1 会话管理

| 方法 | 作用 |
| --- | --- |
| `_ensure_session()` | session 为空时 `Session.create(self.session_dir)` 懒建 |
| `set_session(session)` | 直接替换 session |
| `load_session(session_file_path)` | 触发 `NEW_SESSION` hook → 保存旧 session → 从 `session_file_path` 复制 `*.jsonl` + `*.md` 到 `session_dir` → `Session.load` 反序列化 |
| `new_session()` | 触发 `NEW_SESSION` hook → 保存旧 session → 开启新 session |

### 6.2 Runtime prompt

| 方法 | 作用 |
| --- | --- |
| `set_runtime_prompt(key, prompt, order=100)` | 写入/更新一个 runtime prompt；空 prompt 等价于 remove |
| `remove_runtime_prompt(key)` | 移除 |
| `render_runtime_prompts() → str` | 按 `(order, key)` 排序拼接，空内容跳过，返回 `""` 或 `"\n\n...\n\n..."` |
| `_write_runtime_prompts_file()` | 把 runtime prompts 序列化为 `runtime_prompts.md`，只读不写回 |

### 6.3 工具 / 技能

| 方法 | 作用 |
| --- | --- |
| `add_tools(tools)` | 按名字注册，重名抛 `ValueError`；最后按名字排序 |
| `remove_tools(tool_names)` | 移除并对 `session.ever_used_tools` 做"找不到工具"告警 |
| `add_skills(skills)` / `remove_skills(skill_names)` | 维护 `skills` + 刷新 `skill_prompt` + 同步 `set_runtime_prompt("skills", ..., order=40)` |
| `_add_load_skills_tool()` | 内部：注册内置 `load_skill(skill_name)` 工具（首次有 skill 时调用） |
| `_load_skill_prompt()` | 构造 skill 摘要文本，注入 system prompt |

### 6.4 配置变更

| 方法 | 作用 |
| --- | --- |
| `change_name(name)` | 改名 |
| `change_model(model)` | 切模型 |
| `change_base_dir(path)` | 整体迁移 `system_prompt.md` / `runtime_prompts.md` / `session/` 到新目录 |
| `change_system_prompt(prompt)` | 改写 system prompt 并落盘 |

### 6.5 Timer

| 方法 | 作用 |
| --- | --- |
| `add_timer(seconds, name, hint)` | 注册一个周期性 timer |
| `list_timers() → list[dict]` | 列出所有 timer |
| `update_timer(name, seconds, hint)` | 更新已有 timer（按 name 查找并重置） |
| `start_timer(name)` / `stop_timer(name)` | 启停单个 timer |
| `cancel_timer(name)` | 取消单个 |
| `clear_timers()` | 清空全部 |

### 6.6 模型输入构造

| 方法 | 作用 |
| --- | --- |
| `construct_model_input() → Model_Input` | 拼装 `Model_Input`：`prompt = system_prompt + render_runtime_prompts()`、`tools = list(self.tools.values())`、`messages = session.get_visible_context()`，再叠加 `runtime_context_providers` 输出（作为最近一条 HumanMessage 的内容前缀） |
| `_prepend_runtime_context(messages, context)` | 在最近一条 HumanMessage 的 content 头部插入 `TextBlock(origin="system")`；若 messages 为空或全无 HumanMessage，则新建一条 HumanMessage 承载 |

### 6.7 工具执行

| 方法 | 作用 |
| --- | --- |
| `tool_execute(tool_use) → ToolMessage` | 触发 `ON_TOOL_USE` hook → 同步/异步分发执行（`tool.is_async` 决定 `await tool.async_invoke` 或 `asyncio.to_thread(tool.invoke)`）→ 结果归一化（`str` / `list` 直传，其他 `json.dumps`）→ 触发 `ON_TOOL_RESULT` hook → 返回 `ToolMessage` |

### 6.8 核心调用链（最关键的方法）

| 方法 | 作用 |
| --- | --- |
| `stream_tool_loop()` (async generator) | 主体循环：触发 `BEFORE_STREAM` → `construct_model_input` → `model.async_stream_invoke` → 按 chunk 类型分派：`text`/`thinking` 直接 yield + 触发对应 hook；`completed_tool_use` 起 `asyncio.create_task(tool_execute(...))` 并加入 `_active_tool_tasks`；`completed_message` 根据 `stop_reason` 分支：tool_use 时缓存 `pending_model_message`、end_turn 时直接把消息写进 session。其他 stop_reason 抛错。流结束 / 中断后，tool_use 分支 `_wait_for_tool_results`（带中断监听）→ 把 `pending_model_message` + `tool_results` 一次性 `add_message` 进 session。 |
| `run(human_msg)` (async generator) | 一次性入口：`_interrupt_event.clear` → `state = Running` → `session.add_message(human_msg)` → 触发 `AFTER_INPUT` hook → 调 `stream_tool_loop` → 退出时 `state = Ready` + 触发 `AFTER_RUN` + `session.save()` |
| `start()` | 启动事件循环：进入 `Waiting` → 监听 `input.queue.get()` 与 `_stop_event.wait()` → 拿到事件后进入 `_handle_event` |
| `_handle_event(event)` | 触发 `AFTER_INPUT` hook（reset hook control）→ 把 `event.to_human_message()` 写进 session → 跑 `stream_tool_loop` → 触发 `AFTER_RUN` hook + save |
| `interrupt()` | 触发单次中断：set `_interrupt_event` + cancel 所有 `_active_tool_tasks` |
| `stop()` | 整体停止：set `_stop_event` + 取消 `_loop_running` + interrupt 活跃工具 + 停 `input` |
| `on_output(callback)` | 注册 chunk 输出回调 |
| `_emit(chunk)` / `_emit_state()` | 内部派发：若 callback 是 coroutine function 则 await；`agent_state` chunk 会附 `context_tokens = session.get_visible_token_count()` |

### 6.9 中断/等待辅助

| 方法 | 作用 |
| --- | --- |
| `_interrupt_requested() → bool` | 若 `hook.should_break()` 则 set `_interrupt_event` |
| `_cancel_tool_tasks(tasks)` | 取消并 `gather(..., return_exceptions=True)` |
| `_wait_for_tool_results(tasks)` | 用 `asyncio.wait(..., return_when=FIRST_COMPLETED)` 同时监听工具结果与中断事件；中断时取消工具任务返回 `None` |
| `is_running` (property) | 返回 `_loop_running` |

---

## 7. `SubAgent` — 轻量子 agent

由 `built_in_tool/sub_agent.py` 当工具调用，**没有 session、没有事件循环、没有 AgentHook**，只做"一次推理 + 工具循环"。

### 7.1 实例属性

| 属性 | 作用 |
| --- | --- |
| `name` | 子 agent 名，默认 `sub_{id(self)}` |
| `model` | 复用父 agent 的 model |
| `system_prompt` | 子 agent 自己的 system prompt |
| `logger` | 默认 `_NullLogger`（不写盘），可注入 |
| `skills` / `skill_prompt` | 与 `Agent` 同形，但提示词模板用 `Path: {path}/SKILL.md` 而非 `load_skill` 工具 |
| `tools` | 工具表 |
| `_force_stop` | `stop()` 标志位，`run` 主循环里检查 |

### 7.2 方法

| 方法 | 作用 |
| --- | --- |
| `stop()` | 设 `_force_stop = True`；下一次主循环检查时退出 |
| `add_tools(tools)` | 注册工具（重名抛错） |
| `add_skills(skills)` / `remove_skills(names)` | 维护 skills + 刷新 `skill_prompt`（直接 append / 重生） |
| `tool_execute(tool_use) → ToolMessage` | 与 `Agent.tool_execute` 几乎相同，**不触发 hook**；同步/异步分支、结果归一化、错误处理一致 |
| `_normalize_input(messages) → List[Message]` | 接受 `str` / `Message` / `List[Message]` 三种入参，统一为 list |
| `run(messages) → str` | 主循环：`Model_Input = system_prompt + skill_prompt + tools + messages` → `await model.async_invoke` → 追加 `ModelMessage` → `stop_reason == 'tool_use'` 时遍历 `tool_calls` 逐个 `tool_execute` 并 append `ToolMessage`，中途检查 `_force_stop`；`end_turn` 退出；其他抛错。最终把 `result.content` 里的 `TextBlock` 拼成 `str` 返回 |

### 7.3 SubAgent 与 Agent 的关键差异

| 维度 | `Agent` | `SubAgent` |
| --- | --- | --- |
| 会话持久化 | 有（`Session` + `add_message` + jsonl/md 落盘） | 无（纯内存 `messages: List[Message]`） |
| 调用方式 | 流式 `async_stream_invoke` + chunk 派发 | 一次性 `async_invoke` |
| 工具执行 | 并行（`asyncio.create_task`） | 串行（顺序遍历 `tool_calls`） |
| Hook 链 | 完整（`NEW_SESSION` / `BEFORE_STREAM` / `ON_TOOL_*` / `ON_MESSAGE` / `ON_ERROR` / `AFTER_RUN`） | 无（连 `AgentHook` 都没有） |
| 事件循环 | 有（`start` / `_handle_event`） | 无 |
| Runtime prompt | 有（多层、按 order 排序） | 无（只有 `system_prompt + skill_prompt`） |
| Timer | 有 | 无 |
| 中断机制 | `_interrupt_event` + `_stop_event` | 仅 `_force_stop` 软标志 |
| 工具调用能力 | 可调用 sub-agent（通过 `built_in_tool/sub_agent`） | 不应再嵌 sub-agent |
| 日志 | `AgentLogger`（绑 `base_dir`） | `_NullLogger` 或注入 |
| 输出形式 | async generator 吐 chunk 事件 | 直接 `return str` |

---

## 8. 关键设计点

1. **`Agent` 是"装配体"，`SubAgent` 是"组件"**：`Agent` 拥有完整的运行时基础设施（session / hook / event loop / runtime prompts），适合做顶层对话入口；`SubAgent` 只做"小段推理 + 工具"，适合被父 agent 当工具调用。
2. **两套执行入口**：`run(human_msg)` 用于"一次性同步一次对话"，`start()` 用于"开启事件循环持续接收 input"。二者**不重叠**——`start` 启动后就不会自己调 `run`。
3. **流式 + 工具并行**：`stream_tool_loop` 里 `completed_tool_use` 立即起 `asyncio.create_task(tool_execute)` 并加入 `_active_tool_tasks`，等所有 chunk 吐完再 `_wait_for_tool_results`——所以**多个 tool call 是并行的**，由 `model.async_invoke` 里的信号量层兜底。
4. **Hook 触发点遍布关键边界**：`BEFORE_STREAM` / `ON_TEXT_CHUNK` / `ON_THINKING_CHUNK` / `ON_TOOL_USE` / `ON_TOOL_RESULT` / `ON_MESSAGE` / `ON_ERROR` / `AFTER_INPUT` / `AFTER_RUN` / `NEW_SESSION`——压缩、memory、上下文注入等扩展全靠 hook 挂载。
5. **Runtime prompt 与 system prompt 解耦**：`render_runtime_prompts` 拼出可观察、可排序、可热插拔的扩展层；落盘 `runtime_prompts.md` 只供人检查，**不**回读——避免"改文件改 agent 行为"这种隐式副作用。
6. **中断两级**：`interrupt()` 触发 `_interrupt_event` 用于"打断当前推理或工具"，`stop()` 触发 `_stop_event` 用于"终止整个事件循环"。`interrupt` 不退出事件循环，事件循环还能再接下一个事件。
7. **`session.add_message` 是记忆入口**：所有消息（`HumanMessage` / `ModelMessage` / `ToolMessage`）都通过它进 session，触发 jsonl flush + token 计量。`stream_tool_loop` 在 tool_use 结束后会**把 `ModelMessage` + 所有 `ToolMessage` 一次性 add_message**，避免中间的 `tool_use` 状态让 session 误判轮次边界。
8. **构造 `Model_Input` 时把 runtime context 注入到最近 HumanMessage 的内容前缀**：这是 `Agent` 与 `Team` 协同的关键——`team.py` 可以注册一个 `runtime_context_providers`，让每轮 model 调用都自动看到队友上下文。
9. **`SubAgent.run` 的 tool loop 串行**：和 `Agent` 的并行不同，`SubAgent` 按 `result.tool_calls` 顺序串行执行——这是有意的简化，子任务量小、串行更易追踪。
10. **新扩展方向 checklist**：若要新增 agent 能力（如多模态输出、tool 流式回执、嵌套 sub-agent 配额），优先考虑挂在 hook 上或加到 `AgentConfig`；实在需要改主循环时，改 `stream_tool_loop` 这一处即可。
