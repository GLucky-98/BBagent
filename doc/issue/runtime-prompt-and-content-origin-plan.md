# Runtime Prompt 与 Content Origin 重构方案

## 背景

当前 Agent 的模型输入由多处逻辑隐式拼接和修改：

- `Agent.system_prompt` 是用户配置的基础系统提示词，但部分 built-in hook 会直接调用 `change_system_prompt()` 追加内容。
- `team_prompt`、`teammate_prompt`、`skill_prompt` 是 Agent 上的独立字符串字段，最终在 `construct_model_input()` 中直接拼到 system prompt 后面。
- `runtime_context_providers` 在 `construct_model_input()` 中被调用，用来把 todo 等运行时上下文临时前置到最近的用户消息。
- memory hook 会在 `AFTER_INPUT` 中把检索到的记忆直接前置到用户消息中。
- session JSONL 当前记录的是 session message 状态，但不总是完整表达“模型每次真实收到的内容”和这些内容的来源。

这带来几个问题：

- runtime prompt 来源不可追踪，hook 重装或更新时容易重复 append。
- 构建模型输入时既负责组装，又负责调用 runtime context provider，职责不清。
- 字符串 content 和 `list[ContentBlock]` 混用，导致大量 `str | list` 分支。
- memory/todo 等系统注入内容与用户原文没有统一来源标记，后续记忆抽取、压缩、调试和回放容易混淆。

本方案的目标是把模型输入拆成两条清晰链路：

1. system prompt 侧：基础 `system_prompt` + 有序 `runtime_prompts`。
2. message 侧：session 中保存的结构化 `ContentBlock`，每个 block 通过 `origin` 表示内容来源。

## 设计共识

### ContentBlock origin

统一使用 `origin` 字段，而不是 `source`。

原因：

- `source` 容易与 Anthropic image payload 中的 provider-specific `source` 字段混淆。
- `origin` 更明确表示 BBagent 内部的内容来源元数据。
- `origin` 字段只用于框架内部处理、持久化和调试，不传给模型 provider。

建议 origin 取值：

```python
ContentOrigin = Literal["user", "model", "tool", "system"]
```

含义：

- `user`: 用户原始输入。
- `model`: 模型输出文本。
- `tool`: 工具返回内容。
- `system`: hook 或框架系统注入内容，例如 memory 注入、todo 注入。

### Message.content 统一为 list[ContentBlock]

任意 `Message` 实例化后，`content` 都应是 `list[ContentBlock]`。

输入可以继续接受 `str | list[ContentBlock]`，但应在 `__post_init__` 中归一化：

- `HumanMessage("hello")` -> `[TextBlock(text="hello", origin="user")]`
- `ModelMessage("hello")` -> `[TextBlock(text="hello", origin="model")]`
- `ToolMessage(..., "result")` -> `[TextBlock(text="result", origin="tool")]`
- hook 注入内容显式使用 `TextBlock(text="...", origin="system")`

本方案不考虑旧 session 兼容；可以同步更新测试 fixture。

### Provider payload 不感知 origin

`origin` 是内部字段，不进入 OpenAI / Anthropic 请求 payload。

当前 provider 解析逻辑本身按 block 类型读取字段：

- `TextBlock` -> provider text part
- `ImageBlock` -> provider image part

新增 `origin` 后，只要 `content_block_parse()` 不调用 `block.to_dict()` 直接透传，就不会把 `origin` 发给 provider。当前逻辑大体满足这一点，后续实现时需要用测试固定这个契约。

### Runtime prompts

新增 `Agent.runtime_prompts`，用来统一管理运行时 system prompt 片段。

它替代这些独立字段或直接 append 行为：

- `team_prompt`
- `teammate_prompt`
- `skill_prompt`
- built-in memory system prompt
- built-in todo system prompt

`Agent.system_prompt` 只代表用户配置的基础系统提示词。

构建模型输入时：

```python
prompt = agent.system_prompt + agent.render_runtime_prompts()
messages = agent.session.get_visible_context()
return Model_Input(prompt=prompt, tools=tools, messages=messages)
```

### Runtime prompt 顺序稳定

`runtime_prompts` 内存结构使用轻量 dict，不额外引入 RuntimePrompt 类。

推荐结构：

```python
runtime_prompts: dict[str, dict[str, str | int]]

runtime_prompts["team"] = {
    "content": "...",
    "order": 20,
}
```

渲染规则：

1. `set_runtime_prompt()` 时传入 `order`，默认值建议为 `100`。
2. 渲染时按 `(order, key)` 排序。
3. 如果多个 runtime prompt 使用相同 `order`，按 key 字典序保证稳定输出。
4. 每段之间使用双换行分隔，避免不同 prompt 黏连。

示例：

```python
agent.set_runtime_prompt("team", prompt, order=20)
agent.set_runtime_prompt("teammates", prompt, order=30)
agent.set_runtime_prompt("skills", prompt, order=40)
agent.set_runtime_prompt("built_in.memory", prompt, order=100)
agent.set_runtime_prompt("built_in.todo", prompt, order=110)
```

### Runtime prompts 落盘

新增 `runtime_prompts.md`，作为用户查看用的镜像文件。

该文件不参与反序列化，不作为运行时权威数据源。Agent 仍通过配置、team 创建、skill 列表和 hook 安装过程重建 runtime prompts。

每次 runtime prompt 新增、更新、删除时，立即重写 `runtime_prompts.md`。

建议格式：

```markdown
# Runtime Prompts

This file is generated for inspection only. Runtime prompts are rebuilt from agent/team/skill/hook configuration and are not loaded from this file.

## team

...

## teammates

...

## skills

...

## built_in.memory

...
```

## 目标

- `ContentBlock` 增加 `origin` 字段，并序列化到 JSONL。
- 所有 `Message.content` 在实例化后统一为 `list[ContentBlock]`。
- provider payload 构建忽略 `origin`，模型不感知该字段。
- memory extraction 过滤 `origin == "system"` 的 block，避免把系统注入内容再次抽取为长期记忆。
- 新增有序 `runtime_prompts` 字典，统一管理 team、teammates、skills、memory、todo 等 system prompt 片段。
- 新增 `runtime_prompts.md`，在 runtime prompt 新增、更新、删除时同步重写，方便用户查看。
- `construct_model_input()` 在 prompt 侧只做基础 system prompt 与有序 runtime prompts 的组装，不再直接拼多个独立 prompt 字段。
- todo runtime context 注入在本阶段暂时保留现状，后续 phase 再把 message 侧 runtime provider 从 `construct_model_input()` 中移除。

## 非目标

- 不考虑旧 session JSONL 兼容。
- 不设计前端 UI 如何特殊展示 `origin`。
- 不在本阶段重构 todo 的 runtime context 注入方式；todo 的 `runtime_context_providers` 可后续单独处理。
- 不考虑 hook 动态更新的完整语义；后续方向是不再允许 hook 动态更新。
- 不把 `runtime_prompts.md` 用作反序列化输入。

## 当前代码路径

### 消息和 ContentBlock

- `bbagent/core/message.py`
  - `ContentBlock`
  - `TextBlock`
  - `ImageBlock`
  - `ToolUseBlock`
  - `HumanMessage`
  - `ModelMessage`
  - `ToolMessage`
  - `Session.get_visible_context()`

### 模型输入构建

- `bbagent/core/agent.py`
  - `Agent.__init__`
  - `Agent._load_skill_prompt()`
  - `Agent.add_skills()`
  - `Agent.remove_skills()`
  - `Agent.construct_model_input()`
  - `Agent._prepend_runtime_context()`
  - `SubAgent._load_skill_prompt()`

### Provider payload

- `bbagent/core/model.py`
  - Anthropic `payload_construct()`
  - Anthropic `content_block_parse()`
  - OpenAI `payload_construct()`
  - OpenAI `content_block_parse()`
  - response parse 中创建 `TextBlock` / `ImageBlock`

### Team prompt

- `bbagent/core/team.py`
  - `AgentTeam.create()`
  - `_build_team_prompt()`
  - `_build_teammate_prompt()`
  - `_clear_team_runtime()` 的调用方在 `backend/factories/team_factory.py`

### Built-in hook prompt

- `bbagent/built_in_hook/__init__.py`
  - `_setup_memory()`
  - `_setup_todo()`
  - `_setup_compress()`

### Memory hook

- `bbagent/built_in_hook/memory/memory_hook.py`
  - `_format_message_content()`
  - `_format_messages_for_extraction()`
  - `inject_memory_hook()`

### 后端消息 API

- `backend/factories/agent_factory.py`
  - `get_messages()`
- `backend/schemas.py`
  - `MessageItem`

### 前端受影响文件

- `frontend/src/types/index.ts`
  - `Message`
  - 可选新增 `ContentBlock` 类型
- `frontend/src/store/index.ts`
  - `loadAgentMessages()` 中历史消息 content 归一化
- `frontend/src/components/ChatWindow.tsx`
  - 当前仍可继续接收 string content；暂不做 UI 特殊显示

## 推荐实现方案

### 1. 重构 ContentBlock

在 `bbagent/core/message.py` 中给所有 content block 增加 `origin`。

建议实现：

```python
ContentOrigin = Literal["user", "model", "tool", "system"]

class ContentBlock:
    origin: ContentOrigin

    @staticmethod
    def from_dict(data: dict) -> "ContentBlock":
        ...
```

`TextBlock`：

```python
@dataclass
class TextBlock(ContentBlock):
    text: str
    origin: ContentOrigin = "user"
    type: str = "text"

    def to_dict(self) -> dict:
        return {"type": self.type, "text": self.text, "origin": self.origin}
```

`ImageBlock`：

```python
@dataclass
class ImageBlock(ContentBlock):
    data: str
    image_type: str = "base64"
    origin: ContentOrigin = "user"
    type: str = "image"

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "data": self.data,
            "image_type": self.image_type,
            "origin": self.origin,
        }
```

`ToolUseBlock` 是否加 `origin` 要谨慎。它既是 content block，又有独立语义，通常表示模型产生的 tool use。建议也加默认 `origin="model"`，并在 provider payload 中继续按现有 tool call 结构输出。

### 2. 统一 Message.content 归一化

在 `Message` 或每个 message dataclass 中增加统一归一化 helper：

```python
@staticmethod
def _normalize_content(content, default_origin: ContentOrigin) -> list[ContentBlock]:
    if isinstance(content, str):
        return [TextBlock(text=content, origin=default_origin)] if content else []
    result = []
    for block in content:
        if getattr(block, "origin", None) is None:
            block.origin = default_origin
        result.append(block)
    return result
```

然后：

- `HumanMessage.__post_init__`: 默认 `origin="user"`
- `ModelMessage.__post_init__`: 默认 `origin="model"`
- `ToolMessage.__post_init__`: 默认 `origin="tool"`

完成后，实例化后的 `msg.content` 不再是 string。

需要同步清理或简化这些位置的 `isinstance(content, str)` 分支：

- `Message._serialize_content()`
- `Turn._normalize_content()`
- `Turn._message_to_blocks()`
- `Session.get_visible_context()`
- `Agent._prepend_runtime_context()`
- `memory_hook._format_message_content()`
- provider `content_block_parse()`

其中 `_deserialize_content()` 可以直接反序列化为 block list；本方案不处理旧 string session。

### 3. Provider payload 保持忽略 origin

`bbagent/core/model.py` 中 provider 解析函数应继续从对象属性读取 provider 所需字段。

Anthropic text：

```python
{"type": "text", "text": block.text}
```

Anthropic image：

```python
{
    "type": "image",
    "source": {
        "type": "base64",
        "data": block.data,
        "media_type": block.image_type,
    },
}
```

OpenAI text：

```python
{"type": "text", "text": block.text}
```

OpenAI image：

```python
{"type": "image_url", "image_url": {"url": data_url}}
```

不要把 `block.to_dict()` 直接用于 provider payload，避免 `origin` 泄漏。

### 4. Memory extraction 过滤 system origin

`bbagent/built_in_hook/memory/memory_hook.py` 的 `_format_message_content()` 应过滤系统注入块。

建议：

```python
def _format_message_content(msg: Message, include_system: bool = True) -> str:
    texts = []
    for block in msg.content:
        if not isinstance(block, TextBlock):
            continue
        if not include_system and block.origin == "system":
            continue
        texts.append(block.text)
    return " ".join(texts)
```

`_format_messages_for_extraction()` 调用时使用：

```python
text = _format_message_content(msg, include_system=False)
```

这样 memory 注入写入 session 后，不会在后续提取时被当成用户新事实。

`inject_memory_hook()` 注入时应使用：

```python
TextBlock(text=prefix, origin="system")
```

### 5. 新增 Agent.runtime_prompts

Agent 初始化：

```python
self.runtime_prompts: dict[str, dict[str, str | int]] = {}
self.runtime_prompts_path = self.base_dir / "runtime_prompts.md"
```

新增方法：

```python
def set_runtime_prompt(self, key: str, prompt: str, order: int = 100) -> None:
    ...

def remove_runtime_prompt(self, key: str) -> None:
    ...

def render_runtime_prompts(self) -> str:
    ...

def _write_runtime_prompts_file(self) -> None:
    ...
```

建议行为：

- `set_runtime_prompt()` 收到空字符串时等价于 remove。
- 每次 set/remove 后重写 `runtime_prompts.md`。
- `render_runtime_prompts()` 按 `(order, key)` 稳定输出 prompt。
- `runtime_prompts.md` 不存在时可以在 Agent 初始化时写一个空文件，或首次 set 时创建。

### 6. 替换 team/teammate/skill prompt 字段

逐步移除或废弃：

- `agent.team_prompt`
- `agent.teammate_prompt`
- `agent.skill_prompt`

对应替换：

`AgentTeam.create()`：

```python
agent.set_runtime_prompt("team", cls._build_team_prompt(config.team_description))
agent.set_runtime_prompt("teammates", cls._build_teammate_prompt(contacts))
```

`Agent.add_skills()` / `Agent.remove_skills()`：

```python
self.set_runtime_prompt("skills", self._load_skill_prompt())
```

如果没有 skills：

```python
self.remove_runtime_prompt("skills")
```

`construct_model_input()`：

```python
prompt = self.system_prompt + self.render_runtime_prompts()
messages = self.session.get_visible_context()
return Model_Input(prompt=prompt, tools=tools, messages=messages)
```

本阶段可暂时保留旧字段作为兼容壳，但不再参与最终 prompt 拼接。

### 7. 替换 built-in hook 的 system prompt append

`bbagent/built_in_hook/__init__.py`

memory：

```python
prompt = config.memory_system_prompt.format(...)
agent.set_runtime_prompt("built_in.memory", prompt)
```

todo：

```python
agent.set_runtime_prompt("built_in.todo", config.todo_system_prompt)
```

compress 不设置主 Agent runtime prompt。它继续只把 `compress_prompt` 用作 `ContextCompressor` SubAgent 的 system prompt。

### 8. 暂不重构 todo runtime context provider

本阶段保留：

- `agent.runtime_context_providers`
- `create_todo_hook()` 的 `todo_context_provider`
- `Agent.construct_model_input()` 中调用 runtime context provider 的逻辑

但需要把 `_prepend_runtime_context()` 改为使用 `origin="system"` 的 `TextBlock`。

后续单独 issue 再把 todo runtime context 注入移动到 hook 中，并写入 session JSONL。

### 9. 后端消息 API 影响

`backend/factories/agent_factory.py:get_messages()` 目前会把结构化 message 转成前端 `content: str`。

本阶段可以有两种选择：

1. 保持 API 返回 string content，内部把 block text 拼接。
2. 同时返回原始 blocks，例如新增 `contentBlocks` 字段。

因为暂不考虑前端 UI 特殊展示，建议第一阶段保持 `content: str`，避免前端展示大改。

但如果要让前端也能看到 origin，后续可扩展：

```python
{
    "content": "...",
    "contentBlocks": [
        {"type": "text", "text": "...", "origin": "system"},
        {"type": "text", "text": "...", "origin": "user"}
    ]
}
```

`backend/schemas.py:MessageItem` 可后续增加 `contentBlocks`。本阶段如果 API 不返回该字段，则无需改 schema。

### 10. 前端影响

本阶段前端不需要设计新展示，但需要关注类型影响。

如果后端仍返回 `content: string`：

- `frontend/src/types/index.ts` 暂不必改 `Message.content`。
- `frontend/src/store/index.ts:loadAgentMessages()` 继续把历史消息归一成 string。
- `frontend/src/components/ChatWindow.tsx` 无需改展示逻辑。

如果选择暴露 `contentBlocks`：

- `frontend/src/types/index.ts` 新增：

```ts
export type ContentOrigin = "user" | "model" | "tool" | "system";

export interface TextContentBlock {
  type: "text";
  text: string;
  origin: ContentOrigin;
}

export interface ImageContentBlock {
  type: "image";
  data: string;
  image_type: string;
  origin: ContentOrigin;
}

export type ContentBlock = TextContentBlock | ImageContentBlock;
```

- `Message` 可新增：

```ts
contentBlocks?: ContentBlock[];
```

但 UI 可继续只渲染 `content`。

## 修改文件清单

### 必改后端文件

- `bbagent/core/message.py`
  - `ContentBlock` 增加 `origin`。
  - `TextBlock` / `ImageBlock` / `ToolUseBlock` 序列化包含 `origin`。
  - `HumanMessage` / `ModelMessage` / `ToolMessage` `__post_init__` 统一 content 为 list。
  - 清理 `str | list` 分支。

- `bbagent/core/agent.py`
  - 新增 `runtime_prompts`、`runtime_prompts_path` 和 set/remove/render/write 方法。
  - `construct_model_input()` 改为 `system_prompt + render_runtime_prompts()`。
  - `_prepend_runtime_context()` 使用 `TextBlock(origin="system")`。
  - skill prompt 改为 runtime prompt。

- `bbagent/core/team.py`
  - team/teammate prompt 改为 `set_runtime_prompt()`。
  - 后续清理旧字段引用。

- `bbagent/built_in_hook/__init__.py`
  - memory/todo hook 安装时改为 `set_runtime_prompt()`。
  - 不再 `change_system_prompt(agent.system_prompt + prompt)`。

- `bbagent/built_in_hook/memory/memory_hook.py`
  - memory 注入 block 使用 `origin="system"`。
  - memory extraction 过滤 `origin="system"`。

- `bbagent/core/model.py`
  - 确认 provider payload 不透传 `origin`。
  - 响应解析创建 `TextBlock(origin="model")` / `ImageBlock(origin="model")`，或依赖 `ModelMessage.__post_init__` 补默认值。

- `backend/factories/team_factory.py`
  - `_clear_team_runtime()` 从清旧字段改为 remove runtime prompt key。

### 可能改后端文件

- `backend/factories/agent_factory.py`
  - `get_messages()` 如仍返回 string，可只适配 content list 的内部读取。
  - 如果暴露 `contentBlocks`，则新增字段。

- `backend/schemas.py`
  - 如果 API 暴露 `contentBlocks`，则更新 `MessageItem`。

### 可能改前端文件

- `frontend/src/types/index.ts`
  - 如果 API 暴露 `contentBlocks`，新增 block 类型。

- `frontend/src/store/index.ts`
  - 如果 API 暴露 `contentBlocks`，保留并转存该字段。
  - 如果 API 仍只返回 string，只需确认历史消息加载不受影响。

- `frontend/src/components/ChatWindow.tsx`
  - 本阶段不改 UI。

## 测试计划

### Core message tests

新增或更新 `tests/unit/core/test_agent.py` / `tests/unit/core/test_model.py` / 新文件 `tests/unit/core/test_message_content_origin.py`：

- `HumanMessage("hi").content` 是 list，且 `origin == "user"`。
- `ModelMessage("hi").content` 是 list，且 `origin == "model"`。
- `ToolMessage(..., "ok").content` 是 list，且 `origin == "tool"`。
- `TextBlock.to_dict()` 包含 `origin`。
- `ImageBlock.to_dict()` 包含 `origin`。
- session JSONL 保存后包含 block origin。

### Provider tests

更新 `tests/unit/core/test_model.py`：

- OpenAI payload 中不包含内部 `origin` 字段。
- Anthropic payload 中 text block 不包含内部 `origin` 字段。
- Anthropic image payload 的 provider `source` 字段仍存在，且不与内部 `origin` 混淆。

### Runtime prompt tests

更新 `tests/unit/core/test_agent.py`：

- `set_runtime_prompt()` 后 `construct_model_input().prompt` 包含对应内容。
- runtime prompt 渲染顺序稳定。
- `remove_runtime_prompt()` 后 prompt 不再包含对应内容。
- `runtime_prompts.md` 在 set/remove 后被重写。
- `change_system_prompt()` 只改变基础 system prompt，不吞并 runtime prompt。

### Team tests

更新 `tests/unit/core/test_team.py`：

- `AgentTeam.create()` 后成员 Agent 的 `runtime_prompts["team"]` 和 `runtime_prompts["teammates"]` 正确设置。
- `construct_model_input()` 包含 team 和 teammates prompt。

### Built-in hook tests

更新：

- `tests/unit/built_in_hook/test_memory_optimization.py`
- `tests/unit/built_in_hook/test_todo_subsystem.py`

覆盖：

- memory hook 安装后设置 `runtime_prompts["built_in.memory"]`。
- todo hook 安装后设置 `runtime_prompts["built_in.todo"]`。
- memory 注入写入 `origin="system"` block。
- memory extraction 过滤 `origin="system"` block。

### Backend tests

更新：

- `tests/unit/backend/test_agent_factory_messages.py`
- `tests/unit/backend/test_team_factory.py`

覆盖：

- 后端 `get_messages()` 能从 list content blocks 中提取展示 string。
- team runtime 清理会移除 team/teammates runtime prompt。

## 分阶段实施建议

### Phase 1: ContentBlock origin 和 content list 统一

先完成消息模型基础重构：

- 增加 `origin`。
- message content 统一 list。
- provider payload 不泄漏 origin。
- memory extraction 过滤 system origin。
- 更新相关测试。

这一阶段尽量不改 runtime prompt 管理，降低一次性变更范围。

### Phase 2: runtime_prompts 字典和 runtime_prompts.md

再完成 prompt 管理重构：

- Agent 新增 runtime prompt API。
- team/teammates/skills 改用 runtime prompt。
- memory/todo system prompt 改用 runtime prompt。
- `construct_model_input()` 使用统一渲染。
- 写入 `runtime_prompts.md`。
- 更新测试。

### Phase 3: todo runtime context 后续重构

单独处理：

- 移除 `runtime_context_providers`。
- todo 当前列表注入改为 hook 写入 session content block。
- 确保 todo 注入进入 JSONL，且 `origin="system"`。

## 风险和关注点

- content 统一 list 会触碰基础序列化、模型 payload、后端消息 API 和测试 fixture，是最大风险点。
- `origin` 不应进入 provider payload，需要测试固定。
- memory 注入落盘后必须过滤 system origin，否则会发生记忆自我污染。
- runtime prompt 落盘文件只作为用户查看镜像，不参与反序列化；代码中不要从 `runtime_prompts.md` 读取状态。
- runtime prompt 顺序必须稳定，避免模型行为因 dict 插入顺序或 hook 安装顺序变化而抖动。
- todo runtime context 本阶段暂不彻底重构，因此 `construct_model_input()` 中仍会保留一段 provider 调用逻辑；后续 phase 再清理。
