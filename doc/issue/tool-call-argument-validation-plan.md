# 模型工具调用参数校验方案

## 背景

当前工具调用链路中，`input_schema` 主要用于发送给模型，执行工具时并没有把它作为统一的运行时校验依据。实际执行路径主要依赖函数签名和 Pydantic `TypeAdapter`：

- 模型适配层从 provider 响应中解析 tool call。
- `Agent.tool_execute()` 根据 tool name 查找工具。
- `Tool.invoke()` / `Tool.async_invoke()` 按函数签名提取参数并做 Python 类型转换。
- 工具函数执行，异常被包装成 `Tool invocation error: ...` 返回。

这套机制能处理缺少必填参数、基本类型转换等问题，但没有完整覆盖 JSON Schema 语义，也没有把解析失败、非对象参数、MCP schema 降级等情况统一表达为“可恢复的工具调用错误”。

本文档整理一个完整但分阶段的方案。核心原则是：

> 正确的工具调用执行；错误的工具调用在 tool 执行阶段返回错误信息给模型，让模型自行修正；系统不因为单次错误工具调用中断运行。

## 当前代码路径

### 工具 schema 和执行

**`Tool.__init__`** (`bbagent/core/tool.py`)：

```python
if input_schema:
    self.input_schema = input_schema
else:
    self.input_schema = self.generate_input_schema_from_func(func)
```

**`Tool.invoke()` / `Tool.async_invoke()`** (`bbagent/core/tool.py`)：

```python
for param_name, param in sig.parameters.items():
    if param_name not in input_dict:
        if param.default != inspect.Parameter.empty:
            continue
        raise ValueError(f"Missing required parameter: '{param_name}'")

    value = input_dict[param_name]
    param_type = type_hints.get(param_name, Any)
    adapter = TypeAdapter(param_type)
    kwargs[param_name] = adapter.validate_python(value)
```

现状：执行时没有按 `self.input_schema` 做 JSON Schema 校验。

### 模型响应解析

**OpenAI 非流式解析** (`bbagent/core/model.py`)：

```python
try:
    arguments = json.loads(func["arguments"])
except (json.JSONDecodeError, TypeError):
    arguments = func["arguments"]
tool_calls.append(ToolUseBlock(..., input=arguments))
```

**OpenAI 流式解析** (`bbagent/core/model.py`)：

```python
try:
    args = json.loads(tc["arguments"])
except json.JSONDecodeError:
    args = tc["arguments"]
tool_use = ToolUseBlock(..., input=args)
yield {"type": "completed_tool_use", "content": tool_use}
```

现状：参数 JSON 解析失败时，字符串会继续进入 `ToolUseBlock.input`，后续执行时才报错。

### MCP 工具包装

**`MCPTool.create_tool_from_config()`** (`bbagent/core/mcp.py`)：

```python
schema = config["inputSchema"]
properties = schema.get("properties", {})

type_mapping = {
    "string": str,
    "integer": int,
    "boolean": bool,
    "number": float,
}
```

现状：MCP `inputSchema` 被降级为简单函数签名，复杂 schema 约束没有保留到运行时，也没有完整暴露给模型。

### Agent 执行入口

**`Agent.tool_execute()`** (`bbagent/core/agent.py`)：

```python
try:
    if tool.is_async:
        raw_result = await tool.async_invoke(tool_use.input)
    else:
        raw_result = await asyncio.to_thread(tool.invoke, tool_use.input)
except Exception as e:
    content = f"Tool invocation error: {str(e)}"
```

现状：这里已经具备“错误工具调用返回给模型”的恢复机制，应沿用并强化，而不是在模型流式解析阶段中断。

## 问题

### 1. `input_schema` 不是运行时权威

手写 schema 或 MCP schema 中的约束不会被执行端完整检查。例如：

- `enum`
- `minimum` / `maximum`
- `pattern`
- `minItems` / `maxItems`
- 嵌套 object / array
- MCP 服务端声明的复杂输入结构

如果函数签名足够宽松，违反 schema 的参数仍可能进入工具函数。

### 2. 错误 tool call 缺少统一的错误结果格式

当前很多错误会落到 Python 异常，再由 `Agent.tool_execute()` 包成字符串。这能避免系统崩溃，但错误来源不清晰：

- JSON 解析失败
- tool input 不是 object
- schema 校验失败
- 函数签名校验失败
- 工具运行时异常

这些情况应该保留可恢复行为，但需要更稳定的错误文案和日志字段，便于模型修正和开发者排查。

### 3. MCP 工具 schema 和名称需要谨慎迁移

MCP 工具当前持久化和前后端展示依赖 `ToolConfig.name`：

```python
class ToolConfig(BaseModel):
    id: str
    name: str
    source: Literal["built_in", "hook", "mcp", "team"] = "built_in"
    description: str = ""
    mcpServerId: str | None = None
```

注释中也说明：

- `id` 是机器身份，MCP 工具由 `(mcpServerId, rawName)` 派生。
- `name` 对 MCP 工具来说是 MCP server 上的 rawName。

因此不能直接把运行时工具名从 `mcp:{server}::{tool}` 改成新格式，而不检查：

- 后端 `ToolFactory` 的懒加载。
- `MCPFactory` 注册和刷新工具。
- Agent config 中 `toolIds` 的持久化。
- 前端工具列表展示。
- 会话中已保存的 tool call 名称。
- 模型 payload 中 OpenAI function name 的合法性。

### 4. 内置工具 schema 中存在 `number` / `integer` 语义不一致

JSON Schema 的 `number` 允许整数和浮点数。行数、结果数、超时时间等参数需要逐个判断：

- `limit`、`offset`、`context`、`max_results`、`max_chars` 语义上应是 `integer`。
- `timeout` 如果允许小数秒，可以是 `number`；如果按秒整数处理，应改成 `integer`。

例如 read 工具当前 schema：

```python
"limit": {
    "type": "number",
    "description": "Maximum number of lines to read",
}
```

这在 JSON Schema 中是允许的，但语义不准确。模型可能生成 `1.5`，而函数签名是 `Optional[int]`，运行时会依赖 Pydantic 再判断和转换。更好的做法是 schema 和函数签名一致，改为 `integer`。

## 非目标

### 不在第一阶段强制拒绝额外参数

本方案第一阶段不要求默认增加 `"additionalProperties": false`。理由：

- 模型一般不会主动给出额外输入参数。
- 当前函数签名只取需要的参数，额外字段不会进入工具函数。
- 一上来强制拒绝额外字段可能对历史 MCP 工具或宽松工具造成兼容风险。

后续如果需要更严格模式，可以作为可选策略加入：

```python
strict_extra_args: bool = False
```

默认保持兼容。

### 不修改 `ToolUseBlock`

本方案不在 `ToolUseBlock` 上增加 `__post_init__` 或强类型运行时约束。

原因：

- `ToolUseBlock` 当前承担的是消息内容块和持久化结构，不适合作为主要执行校验点。
- 修改它可能影响 session 反序列化、历史消息、测试 fixture 和前端消息展示。
- 更合理的边界是在 `Agent.tool_execute()` / `Tool` 执行入口把参数校验成可恢复 tool result。

### 不在流式解析阶段中断

模型流式输出中出现非法 JSON 或非对象参数时，不应直接中断 `async_stream_invoke()`。

推荐行为：

- 流式层继续产出 `completed_tool_use`。
- 在 tool use 上保留原始参数或解析错误元信息。
- `Agent.tool_execute()` 阶段返回工具错误信息给模型。

### 暂不处理文件工具路径边界

文件工具的 `Policy.cwd` 是否应作为沙箱边界，是另一个安全议题。本文档聚焦模型工具调用参数校验。

## 目标

1. `input_schema` 成为工具参数校验的运行时依据。
2. 错误工具调用不终止系统运行，而是返回清晰的 tool result。
3. schema 校验失败、JSON 解析失败、非对象参数都在 `tool_execute` 阶段统一处理。
4. MCP 工具保留原始 `inputSchema`，不再把复杂 schema 降级丢失。
5. MCP 工具命名迁移前先完成前后端、持久化、懒加载路径检查。
6. 内置工具的 schema 类型与函数签名保持一致。
7. 日志保留足够信息，便于定位模型输出问题和 schema 问题。

## 总体设计

### 运行链路

```text
Model stream / response
  -> parse provider tool call as best effort
  -> create ToolUseBlock without interrupting stream
  -> Agent.tool_execute()
  -> validate tool input shape
  -> validate against tool.input_schema
  -> invoke function or MCP server
  -> return success or Tool invocation error to model
```

关键点：

- 流式解析层不做硬中断。
- 执行边界负责把错误调用变成模型可读的错误反馈。
- 工具函数只接收已经通过校验和类型转换的参数。
- 日志记录具体错误类型和原始输入。

## 方案一：新增工具参数校验层

### 推荐依赖

在 `pyproject.toml` 中增加：

```toml
dependencies = [
    "pydantic>=2.6,<3",
    "httpx>=0.27",
    "PyYAML>=6.0",
    "jsonschema>=4.21",
]
```

选择 `jsonschema` 的原因：

- 直接执行 JSON Schema，和 `input_schema` 语义一致。
- 对 MCP 原始 `inputSchema` 兼容性更好。
- 避免为每个工具动态生成 Pydantic model。

### 新增异常类型

在 `bbagent/core/tool.py` 中新增：

```python
class ToolInputValidationError(ValueError):
    """Raised when a model-provided tool input is not valid for the tool schema."""
```

### 新增 `Tool.validate_input_schema`

建议在 `Tool` 类中加入：

```python
def validate_input_schema(self, input_data: object) -> dict:
    if not isinstance(input_data, dict):
        raise ToolInputValidationError(
            f"Tool '{self.name}' arguments must be a JSON object, got {type(input_data).__name__}"
        )

    validator = Draft202012Validator(self.input_schema)
    errors = sorted(validator.iter_errors(input_data), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.path) or "<root>"
        raise ToolInputValidationError(
            f"Invalid arguments for tool '{self.name}' at {path}: {first.message}"
        )

    return input_data
```

### 调用位置

在 `Tool.invoke()` 和 `Tool.async_invoke()` 开头调用：

```python
input_dict = self.validate_input_schema(input_dict)
```

然后继续沿用当前函数签名校验：

```python
adapter = TypeAdapter(param_type)
kwargs[param_name] = adapter.validate_python(value)
```

这样校验分两层：

1. JSON Schema 校验：保证模型参数符合工具声明。
2. Pydantic 类型校验：保证传入 Python 函数的是合适类型。

### 额外参数策略

第一阶段不自动注入 `"additionalProperties": false`。

如果某个工具显式在 schema 里声明了：

```json
{"additionalProperties": false}
```

则 `jsonschema` 应尊重它。否则保持宽松。

### 错误返回格式

`Agent.tool_execute()` 当前会返回：

```text
Tool invocation error: ...
```

建议保持这个前缀，细化错误内容：

```text
Tool invocation error: Invalid arguments for tool 'read' at limit: 1.5 is not of type 'integer'
```

这样模型能直接看到如何修正。

### 日志

`Agent.tool_execute()` 捕获 `ToolInputValidationError` 时记录：

```python
context={
    "tool_name": tool_use.name,
    "tool_input": tool_use.input,
    "error_type": "ToolInputValidationError",
}
```

运行时异常仍按当前逻辑记录 `error_type`。

## 方案二：模型解析层 best-effort，不中断流式

### 目标

模型解析层不直接中断系统运行。即使 provider 返回了坏的 `arguments`，也把问题带到 `tool_execute` 阶段转成 tool result。

### 非流式 OpenAI

当前逻辑 JSON 解析失败时把字符串作为 input。可以保留这种 best-effort 行为，但建议给 `ToolUseBlock.input` 放入一个明确结构，避免执行层无法区分“模型传了字符串参数”和“JSON 解析失败”。

推荐结构：

```python
arguments = {
    "__tool_call_parse_error__": "Invalid JSON arguments",
    "__raw_arguments__": func.get("arguments", ""),
}
```

然后 `Tool.validate_input_schema()` 会按 schema 校验失败，`Agent.tool_execute()` 返回错误信息给模型。

### 流式 OpenAI

流式路径同理：

```python
try:
    args = json.loads(tc["arguments"])
except json.JSONDecodeError as e:
    args = {
        "__tool_call_parse_error__": f"Invalid JSON arguments: {e.msg}",
        "__raw_arguments__": tc["arguments"],
    }
```

不要在这里 `raise`，继续 yield：

```python
yield {"type": "completed_tool_use", "content": tool_use}
```

### Anthropic

Anthropic 流式路径在 `content_block_stop` 时执行：

```python
block["input"] = json.loads(block["partial_json"])
```

建议同样改成 best-effort：

```python
try:
    block["input"] = json.loads(block["partial_json"])
except json.JSONDecodeError as e:
    block["input"] = {
        "__tool_call_parse_error__": f"Invalid JSON arguments: {e.msg}",
        "__raw_arguments__": block.get("partial_json", ""),
    }
```

### 执行阶段统一识别 parse error

在 `Tool.validate_input_schema()` 前可以先识别：

```python
if isinstance(input_data, dict) and "__tool_call_parse_error__" in input_data:
    raise ToolInputValidationError(
        f"Model produced invalid JSON arguments: {input_data['__tool_call_parse_error__']}"
    )
```

这样返回给模型的错误更直接，而不是额外字段或 required 缺失造成的间接错误。

## 方案三：MCP 工具保留原始 schema

### 当前风险

`MCPTool` 当前用 MCP `inputSchema` 生成函数签名，然后让 `Tool` 重新生成 schema。这会丢失复杂约束。

### 目标

- LLM-facing schema 使用 MCP 原始 `inputSchema`。
- runtime validation 使用 MCP 原始 `inputSchema`。
- MCP server call 使用服务端 raw tool name。
- 对外工具命名要满足 OpenAI function name 约束，但不能破坏持久化和懒加载。

### 第一阶段：不改持久化 `ToolConfig.name`

第一阶段保持：

```python
ToolConfig.name == MCP rawName
ToolConfig.id == uuid5(mcpServerId, rawName)
```

也就是不改前后端持久化合同。只改运行时 `MCPTool` 内部：

```python
class MCPTool(Tool):
    def __init__(self, mcp_client: MCPClient, config: dict[str, Any]):
        self.mcp_server_name = mcp_client.name
        self.raw_name = config["name"]
        self.runtime_name = make_safe_mcp_runtime_name(mcp_client.name, config["name"])
        self.input_schema = config.get("inputSchema", {"type": "object", "properties": {}})
        ...
```

当前已采用的小步迁移是：把 `Tool.name` 改成 `runtime_name`，但不改 `ToolConfig.name`、`ToolConfig.id` 和 MCP server call 使用的 rawName。

### MCP 命名影响检查清单

修改 MCP 工具运行时名称前，必须逐项检查：

#### 后端持久化和懒加载

- `backend/schemas.py`
  - `ToolConfig.name` 当前表示 MCP rawName。
  - 如果新增运行时安全名，应该新增字段还是运行时派生，需明确。
- `backend/factories/tool_factory.py`
  - `on_mcp_added()` 用 `t.name` 注册工具。
  - `build_tool()` 通过 `tool.raw_name == config.name` 匹配 MCP 工具。
  - 这里依赖 `config.name` 是 rawName。
- `backend/factories/mcp_factory.py`
  - 工具发现、注册、刷新、持久化时如何构造 `ToolConfig`。
  - `_mcp_tool_id(mcp_id, tool_name)` 是否继续使用 rawName。
- `backend/factories/agent_factory.py`
  - Agent config 通过 `toolIds` 关联工具。
  - runtime tool list 由 `ToolFactory.build_tool()` 懒加载。

#### 前端展示和选择

- `frontend/src/lib/api.ts`
- `frontend/src/types/index.ts`
- Agent 配置弹窗里的工具选择组件。
- MCP server 页面中的工具列表展示。

前端应继续展示 rawName 或友好 display name，而不是强迫用户看到编码后的 OpenAI-safe name。

#### 会话和消息

- `bbagent/core/message.py`
  - `ToolUseBlock.name`
  - `ToolMessage.name`
- `backend/factories/agent_factory.py`
  - `get_messages()` 展示历史 tool use / tool result。

如果运行时工具名变化，历史会话里的 `tool_calls.name` 可能无法匹配当前 `self.tools`。本轮明确暂不处理历史会话兼容；后续如果要支持旧 session，再补别名或迁移策略。

#### 模型 provider 限制

OpenAI function name 通常要求只包含字母、数字、下划线和连字符，长度也有限制。当前 `mcp:{server}::{tool}` 风格有冒号，存在不兼容风险。

Anthropic tool name 也应检查允许字符和长度，避免只修 OpenAI。

### 推荐 MCP 命名方案

引入运行时安全名，但不改变持久化 rawName。当前采用不带 hash 的两级命名：

```python
def make_safe_mcp_runtime_name(server_name: str, raw_name: str) -> str:
    # example: mcp__server_slug__tool_slug
```

生成规则：

- 格式固定为 `mcp__{server_slug}__{tool_slug}`。
- 非 `[A-Za-z0-9_-]` 字符替换成 `_`。
- 连续 `_` 合并成单个 `_`。
- 去掉片段首尾 `_`。
- server/tool 片段清洗后为空时，分别回退为 `server` / `tool`。
- 当前不追加 hash；如果 slug 化后发生重名，通过运行时重复工具名检查报错，避免静默覆盖。

字段语义：

| 字段 | 含义 | 是否持久化 |
|---|---|---|
| `ToolConfig.id` | 稳定机器身份，继续由 `(mcpServerId, rawName)` 生成 | 是 |
| `ToolConfig.name` | MCP rawName / 展示名 | 是 |
| `MCPTool.raw_name` | MCP server call 使用的真实名称 | 否 |
| `MCPTool.name` | provider payload 使用的安全工具名 | 否，运行时派生 |

### 重名保护策略

`Agent.tools` 当前是：

```python
self.tools[t.name] = t
```

如果 `MCPTool.name` 改成安全名，则模型返回安全名可以找到工具。由于当前不处理历史会话兼容，不为 rawName 或旧 `mcp:{server}::{tool}` 名称注册别名，避免把同一个工具重复暴露到 provider payload。

为避免 safe name 碰撞导致静默覆盖，`Agent.add_tools()` 和 `SubAgent.add_tools()` 应增加重复名检查：

```python
existing = self.tools.get(t.name)
if existing is not None and existing is not t:
    raise ValueError(f"Duplicate tool name: {t.name}")
self.tools[t.name] = t
```

注意：

- 对模型暴露的 `tools` 列表只应包含安全名。
- 日志中同时记录 `tool_name` 和 `raw_tool_name`。
- 当前不做 rawName 别名，避免 rawName 与内置工具或其他 MCP 工具重名时引入二义性。
- 两级命名不带 hash，冲突概率低但非零；冲突时必须显式报错，不能覆盖已有工具。

### MCPTool 执行结构

推荐让 `MCPTool` 覆盖 `async_invoke()`，不再依赖动态函数签名表达所有 schema：

```python
class MCPTool(Tool):
    def __init__(self, mcp_client: MCPClient, config: dict[str, Any]):
        async def _placeholder(**kwargs):
            return kwargs

        self.mcp_client = mcp_client
        self.raw_name = config["name"]
        safe_name = make_safe_mcp_runtime_name(mcp_client.name, self.raw_name)

        super().__init__(
            _placeholder,
            name=safe_name,
            description=config.get("description", ""),
            input_schema=config.get("inputSchema", {"type": "object", "properties": {}}),
            source="mcp",
        )

    async def async_invoke(self, input_dict: dict):
        arguments = self.validate_input_schema(input_dict)
        result = await self.mcp_client.call_tool(self.raw_name, arguments)
        return json.dumps(result)
```

如果第一阶段暂不改 `Tool.name`，也可以先只传原始 `input_schema`，让校验系统先落地。

## 方案四：内置工具 schema 类型纠偏

### 原则

schema 中的类型应表达模型应该生成什么，而不是只依赖 Pydantic 兜底。

### 建议修改

| 工具 | 参数 | 当前 schema | 建议 schema | 说明 |
|---|---|---|---|---|
| `read` | `offset` | `number` | `integer` | 行号必须是整数 |
| `read` | `limit` | `number` | `integer` | 行数必须是整数 |
| `grep` | `context` | `number` | `integer` | 上下文行数必须是整数 |
| `grep` | `max_results` | `number` | `integer` | 结果数必须是整数 |
| `find` | `max_results` | `number` | `integer` | 结果数必须是整数 |
| `fetch_url` | `max_chars` | `number` | `integer` | 字符数必须是整数 |
| `web_search` | `max_results` | `number` | `integer` | 结果数必须是整数 |
| `bash` | `timeout` | `number` | 待定 | 如果允许小数秒保留 number；否则改 integer |

### 是否允许 `number`

允许，但语义不同：

- `integer`：只允许整数。
- `number`：允许整数和浮点数。

所以 `limit` 用 `number` 在 JSON Schema 层面是合法的，但对“最大行数”这个字段不准确。建议改成 `integer`。

### 可选范围约束

可以逐步增加范围约束，例如：

```json
{
  "type": "integer",
  "minimum": 1
}
```

但第一阶段可以只修类型，不强行引入所有范围规则，降低回归风险。

## 方案五：Agent 执行阶段错误恢复

### 目标

所有工具调用错误统一在 `Agent.tool_execute()` 中转换为 `ToolMessage`，继续进入对话，让模型有机会修正。

### 推荐错误分类

| 错误类型 | 来源 | 返回给模型 |
|---|---|---|
| Unknown tool | `self.tools.get(tool_use.name)` 失败 | `Unknown tool: ...` |
| Parse error | arguments JSON 解析失败元信息 | `Tool invocation error: Model produced invalid JSON arguments: ...` |
| Schema error | `jsonschema` 校验失败 | `Tool invocation error: Invalid arguments for tool ...` |
| Type error | Pydantic / 函数签名校验失败 | `Tool invocation error: ...` |
| Runtime error | 工具函数执行异常 | `Tool invocation error: ...` |

### 不变行为

- `asyncio.CancelledError` 继续抛出，用于中断和停止。
- 其他异常继续被捕获成 tool result。
- `ON_TOOL_RESULT` hook 仍触发。
- tool result 仍写入 session。

### 日志建议

保留当前 error log，同时增强 context：

```python
context={
    "tool_name": tool_use.name,
    "tool_input": tool_use.input,
    "tool_source": getattr(tool, "source", None),
    "raw_tool_name": getattr(tool, "raw_name", None),
    "error_type": type(e).__name__,
}
```

这样既不打断系统，也能审计模型输出和工具 schema 问题。

## 实施步骤

### 阶段 1：基础校验和错误恢复

1. 增加 `jsonschema` 依赖。
2. 新增 `ToolInputValidationError`。
3. 在 `Tool` 中新增 `validate_input_schema()`。
4. `Tool.invoke()` / `Tool.async_invoke()` 开始处调用 schema 校验。
5. 模型解析失败时使用 `__tool_call_parse_error__` 结构，不在流式层 `raise`。
6. `Agent.tool_execute()` 对校验错误保留当前错误返回机制，并增强日志。

### 阶段 2：内置工具 schema 纠偏

1. 把明确整数语义的 `number` 改成 `integer`。
2. 可选增加 `minimum` 等低风险约束。
3. 保持工具函数签名与 schema 一致。

### 阶段 3：MCP schema 保真

1. `MCPTool` 保留并暴露原始 `inputSchema`。
2. `MCPTool.async_invoke()` 先校验原始 schema，再调用 `mcp_client.call_tool(raw_name, arguments)`。
3. 暂不改变 `ToolConfig.name` 的持久化语义。
4. 确认 MCP 工具懒加载仍通过 rawName 匹配。

### 阶段 4：MCP 工具安全命名迁移

1. 完成 MCP 命名影响检查清单。
2. 引入 `make_safe_mcp_runtime_name()`。
3. 明确 rawName、display name、runtime safe name 的字段边界。
4. `Agent.tools` / `SubAgent.tools` 增加重复工具名检查，避免 safe name 碰撞时静默覆盖。
5. 确保 provider payload 只暴露安全名。
6. 确保前端继续展示 rawName / display name。
7. 本轮暂不处理历史 session 兼容；如后续需要，再设计别名或迁移策略。

## 测试计划

### Core Tool

新增或更新 `tests/unit/core/test_tool.py`：

- schema `enum` 不匹配时返回校验错误。
- schema `integer` 收到 `1.5` 时返回校验错误。
- schema nested object / array 校验有效。
- 非 dict 输入返回 `ToolInputValidationError`。
- 未设置 `additionalProperties` 时额外参数不作为第一阶段错误。
- 显式设置 `additionalProperties: false` 时额外参数会被拒绝。
- 函数签名缺少必填参数仍报错。
- Pydantic 类型转换仍保持现有行为。

### Agent Tool Execute

新增或更新 agent 相关测试：

- 错误工具参数返回 `ToolMessage`，不抛出到外层。
- `ToolMessage.content` 包含可读错误。
- `ON_TOOL_RESULT` hook 仍触发。
- `asyncio.CancelledError` 不被吞掉。

### Model Parse

新增 OpenAI / Anthropic 解析测试：

- 非流式 OpenAI arguments JSON 损坏，不中断解析，后续 tool_execute 返回错误。
- 流式 OpenAI arguments JSON 损坏，不中断 stream。
- Anthropic `partial_json` 损坏，不中断 stream。

### MCP

新增 MCP 单测或 fake client：

- MCP 原始 `inputSchema` 被保留到 `tool.input_schema`。
- MCP schema 中的 `enum`、array、object 校验有效。
- `MCPTool.async_invoke()` 使用 rawName 调用 server。
- `ToolFactory.build_tool()` 懒加载 MCP 工具仍可通过 rawName 匹配。
- 迁移安全命名后，provider-facing name 为 `mcp__server_slug__tool_slug`，不包含冒号、空格等不安全字符。
- rawName 仍用于 MCP call。
- safe name 碰撞时，`Agent.add_tools()` / `SubAgent.add_tools()` 报错而不是覆盖已有工具。

### 内置工具 schema

新增或更新 built-in tool 测试：

- `read(limit=1.5)` 返回工具参数错误。
- `grep(context=1.5)` 返回工具参数错误。
- `find(max_results=1.5)` 返回工具参数错误。
- 合法整数参数仍能执行。

## 验收标准

1. 合法工具调用行为不变。
2. 错误工具调用不会中断 agent 运行。
3. 错误工具调用会生成 `ToolMessage`，模型能看到错误原因。
4. `input_schema` 中的关键 JSON Schema 约束在运行时生效。
5. MCP 工具不再丢失原始 `inputSchema`。
6. MCP 工具命名迁移不会破坏 `ToolConfig` 持久化和前端展示。
7. 明确整数语义的参数不再声明为 `number`。
8. 测试覆盖 schema 校验、错误恢复、MCP schema 保真和流式解析坏参数场景。

## 风险和注意事项

### jsonschema 依赖

新增依赖会影响安装体积，但收益明确。若不希望加入依赖，可以先用 Pydantic 动态模型实现部分校验，但 MCP 原始 JSON Schema 的保真会更麻烦。

### MCP schema 兼容性

不同 MCP server 可能返回的 `inputSchema` 不完全符合 Draft 2020-12。实现时需要：

- 对缺失 `type` 的 schema 做兼容。
- 对空 schema 使用宽松 object schema。
- 对 schema 本身无效的 MCP 工具记录 warning，必要时退化为宽松校验。

### 额外参数兼容

第一阶段不默认拒绝额外参数，但显式 schema 约束必须尊重。后续如果需要严格模式，应作为可配置行为，而不是静默改变所有工具。

### 历史会话

MCP 工具安全命名迁移可能影响历史 `ToolUseBlock.name` 和 `ToolMessage.name`。本轮明确不处理历史会话兼容，因此旧会话中保存的 `mcp:{server}::{tool}` 工具调用名称可能无法匹配当前 runtime tool name。

如果后续要恢复历史兼容，应单独设计：

- 旧 composite name 到 safe name 的别名映射。
- rawName 别名是否允许，以及与内置工具重名时如何处理。
- provider payload 去重，避免别名把同一个工具重复暴露给模型。

## 推荐优先级

1. 先做 `Tool.validate_input_schema()` 和 agent 执行阶段错误恢复。
2. 再修内置工具 schema 的 `number` / `integer`。
3. 然后做 MCP schema 保真，但暂不急着改持久化命名。
4. 最后单独处理 MCP provider-facing 安全命名迁移。
