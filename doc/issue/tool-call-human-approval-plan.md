# 风险工具调用人工审批方案

## 背景

当前 Agent 的工具调用链路是自动执行的：

- 模型适配层从 provider 响应中解析 tool call。
- `Agent.stream_tool_loop()` 收到 `completed_tool_use` 后创建工具执行 task。
- `Agent.tool_execute()` 根据 tool name 查找工具并调用 `Tool.invoke()` / `Tool.async_invoke()`。
- 工具结果以 `ToolMessage` 写入 session，并通过 dispatcher 发送给前端。

这条链路对效率友好，但缺少“高风险操作执行前由用户确认”的控制点。尤其是：

- `bash` 可以执行任意 shell 命令。
- `write` / `edit` 会修改本地文件。
- `sub_agent` 可能间接调用高风险工具。
- MCP 工具由外部 server 提供，是否只读并不总是可知。
- hook 工具也可能修改本地状态，例如 memory/todo 类工具。

本文档整理一个完整可行的人工审批方案。核心原则是：

> 审批是 Agent 工具执行前的运行时门禁，不是前端 UI 的局部 confirm，也不应散落到每个工具实现里。

## 设计目标

- 支持三种权限模式：只读模式、自动解析/询问模式、全自动模式。
- 支持对高风险工具调用暂停执行，等待用户审批。
- 支持用户选择“通过 / 不通过 / 通过且相同命令以后不再审批”。
- 支持基于 shell AST 的命令解析，生成稳定 fingerprint，用于 allowed list。
- 支持 `cd frontend && npm run build` 这类常见目录切换命令的 `effective_cwd` 推导。
- 审批拒绝时不崩溃 Agent，而是返回可恢复的 `ToolMessage` 给模型。
- 支持单 Agent 和 Team Agent 的 WebSocket 审批事件。
- 保持 core library 可独立使用，不把审批强绑定到 FastAPI 或前端。
- 保持默认测试离线、确定性，不依赖真实 LLM、MCP server 或外部网络。

## 非目标

- 不在第一阶段实现完整 shell 语义解释器。
- 不承诺 AST 能证明命令安全；AST 只用于结构识别、风险分类和 fingerprint。
- 不在第一阶段支持跨进程/跨设备共享审批规则。
- 不在第一阶段实现复杂路径 pattern 权限系统，例如 glob path allowlist。
- 不改变 session 历史消息的基础格式；审批拒绝仍以 `ToolMessage` 进入模型上下文。

## 当前代码路径

### 工具执行入口

`Agent.tool_execute()` 是最集中的执行门禁位置：

```python
async def tool_execute(self, tool_use: ToolUseBlock) -> ToolMessage:
    tool = self.tools.get(tool_use.name)
    ...
    if tool.is_async:
        raw_result = await tool.async_invoke(tool_use.input)
    else:
        raw_result = await asyncio.to_thread(tool.invoke, tool_use.input)
```

推荐在实际调用工具前插入审批：

```text
resolve tool
analyze risk
if approval required:
    emit approval request
    wait for decision
    if denied: return ToolMessage(...)
execute tool
return ToolMessage(...)
```

### 流式事件

`Agent.stream_tool_loop()` 当前在收到模型工具调用后立即创建 task：

```python
if chunk_type == 'completed_tool_use':
    tool_use = content
    task = asyncio.create_task(self.tool_execute(tool_use))
    tool_tasks.append(task)
    yield chunk
```

审批请求可以由 `tool_execute()` 通过 Agent output callback 发送，也可以在 `stream_tool_loop()` 创建 task 前预分析并 yield。推荐第一阶段由 `tool_execute()` 内部统一处理，原因：

- 单 Agent、Team、SubAgent 未来都可以复用同一执行门禁。
- 对调用方来说，`tool_execute()` 是“执行一个 tool use”的权威边界。
- 审批拒绝可以自然返回 `ToolMessage`。

### 后端 dispatcher

`backend/dispatcher.py` 会把 dataclass 转成 JSON dict 后广播给 WebSocket 订阅者。新增审批事件时，保持普通 dict chunk 即可：

```json
{
  "type": "tool_approval_requested",
  "content": {...}
}
```

### 前端流式消息

`frontend/src/components/ChatWindow.tsx` 已处理：

- `completed_tool_use`
- `tool_results`
- `agent_state`
- `interrupted`

新增 `tool_approval_requested` / `tool_approval_resolved` 分支即可复用现有消息流。

## 权限模式

权限模式建议存储在现有 `toolPolicy` 中。

用户侧可展示为：

```text
只读模式
询问模式
全自动模式
```

内部字段建议使用：

```text
readonly
ask
auto
```

### 1. 只读模式 `readonly`

语义：

> 只自动执行明确只读的工具调用；任何可能影响本地文件、执行命令、产生外部副作用或能力未知的工具调用都需要审批。

默认放行：

- `read`
- `ls`
- `grep`
- `find`

默认审批：

- `bash`
- `write`
- `edit`
- `sub_agent`
- 所有 MCP 工具
- 可能修改本地状态的 hook 工具

`bash` 即使命令看起来是只读，也应在 `readonly` 模式下审批。理由是 shell 能力过大，第一阶段不应在最保守模式里做自动放行。

### 2. 询问模式 `ask`

语义：

> 明确只读工具自动执行；非只读工具先解析并生成 fingerprint。如果 fingerprint 已在 allowed list 中，自动放行；否则提出审批。

用户审批选项：

```text
通过
不通过
通过且相同命令以后不再审批
```

行为：

- 只读工具：直接放行。
- `bash`：基于 AST 解析，生成 normalized command 和 fingerprint。
- `write` / `edit`：基于工具名、路径、cwd、关键参数生成 fingerprint。
- MCP 工具：基于 server id、tool name、输入参数摘要生成 fingerprint。
- AST 解析失败：需要审批。
- 出现复杂或动态 shell 特性：需要审批。
- fingerprint 命中 allowed list：直接放行。

注意：这个模式产品上建议叫“询问模式”，不要叫“安全自动模式”。AST 是减少重复审批的机制，不是安全证明。

### 3. 全自动模式 `auto`

语义：

> 所有工具调用无需审批，自动执行。

第一阶段可直接让 approval gate 返回 allow。

后续可增加硬保护字段，例如：

```json
{
  "neverAllow": [
    {"toolName": "bash", "executable": "sudo"},
    {"toolName": "bash", "executable": "rm", "argsPrefix": ["-rf", "/"]}
  ]
}
```

MVP 可以先不实现 `neverAllow`，但数据结构可预留。

## 配置结构

建议扩展 `toolPolicy`：

```json
{
  "approval": {
    "permissionMode": "ask",
    "allowed": [],
    "denied": [],
    "timeoutSeconds": 300,
    "decisionOnTimeout": "deny"
  }
}
```

字段含义：

- `permissionMode`：`readonly | ask | auto`。
- `allowed`：用户选择“通过且相同命令以后不再审批”后写入的规则。
- `denied`：预留字段，第一阶段可以不使用，未来支持永久拒绝。
- `timeoutSeconds`：审批等待超时时间。
- `decisionOnTimeout`：超时默认行为，建议只支持 `deny`。

Allowed rule 建议结构：

```json
{
  "id": "sha256:...",
  "toolName": "bash",
  "toolSource": "built_in",
  "fingerprint": "sha256:...",
  "label": "python -m pytest tests/unit",
  "createdAt": 1781548800,
  "createdBy": "user",
  "scope": {
    "agentId": "..."
  },
  "match": {
    "kind": "simple",
    "effectiveCwd": "/Users/gl/Desktop/BBagent/BBagent",
    "argv": ["python", "-m", "pytest", "tests/unit"],
    "features": {
      "redirect": false,
      "pipeline": false,
      "controlOperator": false,
      "commandSubstitution": false,
      "subshell": false,
      "glob": false,
      "envExpansion": false
    }
  }
}
```

第一阶段建议 allowed list 存在 Agent config 的 `toolPolicy.approval.allowed` 内，随 `agent_config.json` 持久化。这样行为和现有 tool policy 一致。

## 核心数据模型

新增模块建议：

```text
bbagent/core/tool_approval.py
bbagent/core/tool_risk.py
bbagent/core/shell_parser.py
```

### `ToolRisk`

```python
RiskDecision = Literal["allow", "approval", "deny"]
RiskLevel = Literal["low", "medium", "high", "critical"]

@dataclass
class ToolRisk:
    decision: RiskDecision
    level: RiskLevel
    reasons: list[str] = field(default_factory=list)
    fingerprint: str = ""
    parsed: dict | None = None
```

含义：

- `decision`：风险分析的建议，不等同最终审批结果。
- `level`：用于 UI 展示风险程度。
- `reasons`：为什么需要审批或拒绝。
- `fingerprint`：用于 allowed list 匹配。
- `parsed`：解析后的结构化命令或工具调用摘要。

### `ToolApprovalRequest`

```python
@dataclass
class ToolApprovalRequest:
    id: str
    agent_name: str
    tool_call_id: str
    tool_name: str
    tool_source: str | None
    tool_input: dict
    risk: ToolRisk
    created_at: int
    timeout_seconds: int
```

发送给前端时使用 `to_dict()`。

### `ToolApprovalDecision`

```python
ApprovalDecisionValue = Literal["approve", "deny"]

@dataclass
class ToolApprovalDecision:
    request_id: str
    decision: ApprovalDecisionValue
    remember: bool = False
    reason: str = ""
```

`remember=True` 表示“通过且相同命令以后不再审批”。

### `ToolApprovalManager`

```python
class ToolApprovalManager:
    def __init__(self, policy: dict | None = None):
        self.policy = ToolApprovalPolicy.from_dict(policy or {})
        self._pending: dict[str, asyncio.Future[ToolApprovalDecision]] = {}

    async def request_approval(
        self,
        request: ToolApprovalRequest,
        emit: Callable[[dict], Awaitable[None]],
    ) -> ToolApprovalDecision: ...

    def resolve(self, decision: ToolApprovalDecision) -> bool: ...
    def cancel_all(self, reason: str = "cancelled") -> None: ...
    def is_allowed(self, risk: ToolRisk) -> bool: ...
    def remember_allowed(self, request: ToolApprovalRequest) -> None: ...
```

Core 层不应直接依赖 backend state；只通过 callback emit 事件，并由外部调用 `resolve()`。

## 命令解析方案

### 为什么需要 AST

`shlex.split()` 只能处理简单 argv，不能可靠区分：

- pipeline
- redirect
- command substitution
- subshell
- control operator
- here-doc

审批系统需要知道命令结构和动态特性，因此 `bash` 工具建议使用 AST 解析库。Python 可选 `bashlex`。如果未安装或解析失败，回退为 `kind="unknown"` 并要求审批。

### ParsedCommand 格式

内部不建议保存 raw AST。AST 只作为输入，转换成稳定的规范化结构：

```python
CommandKind = Literal["simple", "pipeline", "compound", "unknown"]

@dataclass
class ParsedCommand:
    raw: str
    normalized: str
    kind: CommandKind
    argv: list[str] = field(default_factory=list)
    commands: list["ParsedCommand"] = field(default_factory=list)
    redirects: list[dict] = field(default_factory=list)
    cwd: str = ""
    effective_cwd: str = ""
    features: dict[str, bool] = field(default_factory=dict)
    risk_reasons: list[str] = field(default_factory=list)
    fingerprint: str = ""
```

字段含义：

- `raw`：模型原始生成的命令，用于 UI 展示和审计。
- `normalized`：规范化后的命令表示，用于 fingerprint 和展示。
- `kind`：顶层结构。
- `argv`：简单命令的参数数组。
- `commands`：pipeline/compound 的子命令列表。
- `redirects`：重定向信息，例如 `> out.txt`、`2>&1`、`< input.txt`。
- `cwd`：bash tool 的基础工作目录，也就是 `Policy.cwd`。
- `effective_cwd`：当前命令实际执行目录。可静态推导时使用推导结果，否则等于 `cwd` 或标记为 unknown。
- `features`：命令特性开关。
- `risk_reasons`：解析阶段识别出的风险原因。
- `fingerprint`：基于规范化结构生成的稳定哈希。

### `kind` 判断规则

`kind` 表示 shell 命令的顶层结构，不直接等同风险等级。

```text
simple      单个命令调用
pipeline    管道命令
compound    多个命令通过 &&、||、;、换行、子 shell 等组合
unknown     解析失败，或遇到不支持/过于动态的语法
```

示例：

```bash
python -m pytest tests/unit
```

```json
{
  "kind": "simple",
  "argv": ["python", "-m", "pytest", "tests/unit"]
}
```

```bash
cat a.txt | grep hello
```

```json
{
  "kind": "pipeline",
  "commands": [
    {"kind": "simple", "argv": ["cat", "a.txt"]},
    {"kind": "simple", "argv": ["grep", "hello"]}
  ],
  "features": {"pipeline": true}
}
```

```bash
git diff && npm run build
```

```json
{
  "kind": "compound",
  "operator": "&&",
  "commands": [
    {"kind": "simple", "argv": ["git", "diff"]},
    {"kind": "simple", "argv": ["npm", "run", "build"]}
  ],
  "features": {"controlOperator": true}
}
```

```bash
echo $(date)
```

顶层可以是 `simple`，但必须标记动态特性：

```json
{
  "kind": "simple",
  "argv": ["echo"],
  "features": {"commandSubstitution": true}
}
```

这类命令需要审批。

### `cd` 和 `effective_cwd`

当前 `bash` tool 每次调用都会新开 subprocess，cwd 来自 `Policy.cwd`。因此：

```bash
cd frontend
```

不会影响下一次工具调用：

```bash
npm run build
```

如果要在另一个目录执行命令，必须在同一条 shell 命令里出现：

```bash
cd frontend && npm run build
```

解析器可以覆盖这种常见情况：

```json
{
  "kind": "compound",
  "commands": [
    {"kind": "simple", "argv": ["cd", "frontend"]},
    {
      "kind": "simple",
      "argv": ["npm", "run", "build"],
      "effective_cwd": "/Users/gl/Desktop/BBagent/BBagent/frontend"
    }
  ]
}
```

fingerprint 建议针对实际执行命令生成：

```json
{
  "toolName": "bash",
  "kind": "simple",
  "effectiveCwd": "/Users/gl/Desktop/BBagent/BBagent/frontend",
  "argv": ["npm", "run", "build"],
  "features": {
    "redirect": false,
    "pipeline": false,
    "controlOperator": false,
    "commandSubstitution": false,
    "subshell": false,
    "glob": false,
    "envExpansion": false
  }
}
```

这样用户批准过 `cd frontend && npm run build` 后，再次出现等价调用可以自动放行。

保守处理规则：

- 只推导 literal `cd <static-relative-or-absolute-path>`。
- `cd` 后路径必须能规范化到确定路径。
- `cd $DIR && ...`：不推导，审批。
- `cd $(mktemp -d) && ...`：不推导，审批。
- `pushd` / `popd`：不推导，审批。
- `source env.sh && ...`：不推导，审批。
- subshell 中的 `cd`：不跨 subshell 推导。
- `cd frontend; rm -rf dist`：可解析为 compound，但仍需要审批，因为包含非只读命令。

### features 字段

建议固定输出以下布尔字段：

```json
{
  "pipeline": false,
  "redirect": false,
  "controlOperator": false,
  "commandSubstitution": false,
  "subshell": false,
  "glob": false,
  "envExpansion": false,
  "assignment": false,
  "heredoc": false
}
```

含义：

- `pipeline`：包含 `|`。
- `redirect`：包含 `<`、`>`、`>>`、`2>`、`2>&1` 等。
- `controlOperator`：包含 `&&`、`||`、`;`、换行等控制操作。
- `commandSubstitution`：包含 `$()` 或反引号。
- `subshell`：包含 `( ... )`。
- `glob`：包含未引用的 `*`、`?`、`[...]`。
- `envExpansion`：包含 `$VAR`、`${VAR}`。
- `assignment`：包含 `FOO=bar command`。
- `heredoc`：包含 here-doc。

只要出现动态特性，第一阶段都建议审批。

### fingerprint 生成

不要直接 hash 原始字符串。应 hash 规范化后的结构：

```python
fingerprint_payload = {
    "toolName": "bash",
    "toolSource": "built_in",
    "kind": parsed.kind,
    "effectiveCwd": parsed.effective_cwd,
    "argv": parsed.argv,
    "commands": [...],
    "redirects": parsed.redirects,
    "features": selected_features,
}
fingerprint = "sha256:" + sha256(
    json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
```

这样：

```bash
python -m pytest tests
python  -m   pytest   tests
```

可以得到相同 fingerprint。

但：

```bash
python -m pytest tests > result.txt
```

因为多了重定向，应得到不同 fingerprint。

## 风险判断规则

### 工具级规则

建议第一阶段实现：

```python
READONLY_BUILTINS = {"read", "ls", "grep", "find"}
MUTATING_BUILTINS = {"write", "edit"}
CAPABILITY_BUILTINS = {"bash", "sub_agent"}
```

规则：

- `auto`：直接 allow。
- `readonly`：
  - readonly builtins allow。
  - 其他全部 approval。
- `ask`：
  - readonly builtins allow。
  - `bash` 走 AST + allowed list。
  - `write` / `edit` 走 fingerprint + allowed list，否则 approval。
  - `sub_agent` approval。
  - MCP approval，命中 allowed list 可放行。
  - hook 工具默认 approval，后续可通过 hook descriptor 标记 readonly。

### Bash 级规则

第一阶段不要试图精细区分“绝对安全命令”。建议：

- 只用 AST 生成 fingerprint。
- 所有未被 allowed list 命中的 `bash` 调用都审批。
- 如果 AST 解析失败，仍可生成 raw-string fallback fingerprint，但必须审批。
- 如果出现动态 features，必须审批，且 `remember` 只记住完整 fingerprint，不做泛化。

这样用户可以逐步把常用命令加入 allowed list，例如：

- `python -m pytest tests`
- `ruff check .`
- `mypy bbagent backend`
- `cd frontend && npm run build`

### 文件修改工具规则

`write` fingerprint 建议包含：

```json
{
  "toolName": "write",
  "effectivePath": "/abs/path/file.py",
  "contentHash": "sha256:..."
}
```

是否包含 `contentHash` 取决于产品语义：

- 包含 `contentHash`：只允许完全相同写入，最保守。
- 不包含 `contentHash`：允许以后写同一个文件，效率高但风险更大。

第一阶段建议包含 `contentHash`，避免“批准一次写文件后，未来任意内容写入同文件都放行”。

`edit` fingerprint 建议包含：

```json
{
  "toolName": "edit",
  "effectivePath": "/abs/path/file.py",
  "oldHash": "sha256:...",
  "newHash": "sha256:...",
  "partialMatch": false
}
```

## Agent 运行时行为

### 审批请求事件

发送给前端：

```json
{
  "type": "tool_approval_requested",
  "content": {
    "id": "approval_...",
    "agentName": "Coder",
    "toolCallId": "toolu_...",
    "toolName": "bash",
    "toolSource": "built_in",
    "toolInput": {
      "command": "cd frontend && npm run build"
    },
    "risk": {
      "level": "high",
      "reasons": ["bash command requires approval"],
      "fingerprint": "sha256:...",
      "parsed": {...}
    },
    "createdAt": 1781548800,
    "timeoutSeconds": 300
  }
}
```

### 审批结果事件

前端发给后端：

```json
{
  "type": "tool_approval_decision",
  "request_id": "approval_...",
  "decision": "approve",
  "remember": true,
  "reason": ""
}
```

或：

```json
{
  "type": "tool_approval_decision",
  "request_id": "approval_...",
  "decision": "deny",
  "remember": false,
  "reason": "Unexpected command"
}
```

后端可广播 resolved 事件：

```json
{
  "type": "tool_approval_resolved",
  "content": {
    "id": "approval_...",
    "decision": "approve",
    "remember": true
  }
}
```

### AgentState

建议扩展：

```python
class AgentState:
    Ready = "ready"
    Waiting = "waiting"
    Running = "running"
    WaitingApproval = "waiting_approval"
    Error = "error"
```

当至少一个工具调用等待审批时，Agent 设置为 `waiting_approval` 并 emit state。

审批完成后，如果仍在本轮执行中，恢复 `running`。

注意：如果同一轮有多个并行 tool call，可能同时产生多个 approval request。第一阶段可允许并行审批；也可以选择工具调用串行审批，降低复杂度。

### 拒绝时的 ToolMessage

拒绝不应中断 Agent。返回：

```python
ToolMessage(
    id=tool_use.id,
    name=tool_use.name,
    content=(
        "Tool call rejected by human approval. "
        "Reason: Unexpected command"
    )
)
```

这样模型下一轮会看到 tool result，并可调整计划。

### interrupt / stop / new session

- `interrupt()`：取消 active tool tasks，并 resolve/cancel 所有 pending approvals。
- `stop()`：同上。
- `new_session()` / `load_session()`：如果 Agent 正在 waiting approval，应拒绝或先 interrupt。
- 审批 future 被取消时，对应 tool task 应返回 cancellation，不写入 pending model message。

## 后端改造

### AgentFactory

职责：

- 从 `AgentConfig.toolPolicy.approval` 初始化 Agent 的 approval manager。
- 提供 `resolve_tool_approval(agent_id, request_id, decision, remember, reason)`。
- 用户选择 remember 时，更新 `cfg.toolPolicy.approval.allowed` 并写回 `agent_config.json`。
- 更新 Agent 时，如果 `toolPolicy` 改变，同步 approval manager。

建议接口：

```python
async def resolve_tool_approval(
    self,
    agent_id: str,
    request_id: str,
    decision: str,
    remember: bool = False,
    reason: str = "",
) -> bool:
    ...
```

### Chat WebSocket

`backend/api/chat.py` 增加：

```python
elif msg_type == "tool_approval_decision":
    agent = state_manager.agent_factory.agents.get(current_agent_id)
    if agent:
        await state_manager.agent_factory.resolve_tool_approval(
            current_agent_id,
            msg["request_id"],
            msg.get("decision", "deny"),
            bool(msg.get("remember", False)),
            msg.get("reason", ""),
        )
```

### Team WebSocket

Team 模式审批请求可能来自任意成员 Agent。`backend/api/team_ws.py` 的 decision 消息应包含 `agent_name` 或 `agent_id`：

```json
{
  "type": "tool_approval_decision",
  "agent_name": "Coder",
  "request_id": "...",
  "decision": "approve",
  "remember": true
}
```

处理时：

- 用 `team.agents[agent_name]` 找到成员 Agent。
- 再映射回 AgentFactory 的 agent_id，或在 approval request 中直接携带 agent_id。

建议第一阶段在 approval request 中携带 `agentId`，避免 name 重名问题。

## 前端改造

### 类型

`frontend/src/types/index.ts` 增加：

```ts
export type PermissionMode = "readonly" | "ask" | "auto";

export interface ToolApprovalPolicy {
  permissionMode: PermissionMode;
  allowed?: ToolApprovalRule[];
  denied?: ToolApprovalRule[];
  timeoutSeconds?: number;
  decisionOnTimeout?: "deny";
}

export interface ToolPolicy {
  ...
  approval?: ToolApprovalPolicy;
}
```

### Agent 配置 UI

在 `AgentConfigDialog` 的 Tool Policy 弹窗增加权限模式分段控件：

```text
只读
询问
全自动
```

建议默认值：

```json
{
  "permissionMode": "ask",
  "allowed": [],
  "timeoutSeconds": 300,
  "decisionOnTimeout": "deny"
}
```

可以增加 allowed list 管理：

- 展示已记住的命令 label。
- 支持删除单条 allowed rule。
- 支持清空 allowed list。

### ChatWindow 审批卡片

处理 `tool_approval_requested`：

- 插入一条 system runtime message，`chunkType` 可新增 `"tool_approval"`。
- 展示 tool name、风险等级、原因、命令/参数、解析后的 cwd/argv。
- 按钮：
  - Approve
  - Deny
  - Approve and remember

点击按钮后通过 WebSocket 发送 decision。

### TeamChatWindow 审批卡片

Team 当前只展示 team messages，不展示每个成员的 tool stream。审批事件需要至少有一个可见入口。

第一阶段建议：

- 在 TeamChatWindow 的 WebSocket `onmessage` 中处理 `tool_approval_requested`。
- 显示一条 team-level system approval card。
- 卡片标题包含 `agentName`。
- decision 消息携带 `agentId` 或 `agentName`。

后续可把成员 Agent 的完整 runtime stream 纳入 Team workspace 面板。

## SubAgent 策略

`sub_agent` 本身应被视为 capability tool：

- `readonly`：审批。
- `ask`：审批，除非用户将该具体 sub_agent 调用加入 allowed list。
- `auto`：放行。

更细粒度的方案是把父 Agent 的 approval manager 传给 SubAgent，让子 Agent 内部工具也逐个审批。但第一阶段复杂度较高。

建议第一阶段：

- 对 `sub_agent` 工具调用本身审批。
- 子 Agent 内部仍受 `subAgentBlockedTools` 限制。
- 后续再实现 approval manager 透传。

## MCP 策略

MCP 工具默认能力未知：

- `readonly`：审批。
- `ask`：审批，命中 allowed list 放行。
- `auto`：放行。

MCP fingerprint 建议包含：

```json
{
  "toolName": "raw_mcp_tool_name",
  "toolSource": "mcp",
  "mcpServerId": "...",
  "inputHash": "sha256:..."
}
```

第一阶段不要尝试根据 MCP description 自动判断只读。

## 持久化和兼容性

- `toolPolicy.approval` 是新增可选字段。
- 缺失时默认：

```json
{
  "permissionMode": "ask",
  "allowed": [],
  "timeoutSeconds": 300,
  "decisionOnTimeout": "deny"
}
```

- 历史 Agent config 不需要 migration。
- 历史 session 不需要 migration。
- `ToolMessage` 格式不变。
- 前端如果遇到未知 chunk type，应保持忽略或降级展示。

## 分阶段实现计划

### 阶段 1：核心审批门禁

- 新增 `bbagent/core/tool_approval.py`。
- 新增 `bbagent/core/tool_risk.py`。
- `Agent` 增加 approval manager。
- `Agent.tool_execute()` 在工具执行前调用 risk/approval gate。
- 新增 `tool_approval_requested` / `tool_approval_resolved` chunk。
- `interrupt()` / `stop()` 取消 pending approval。
- `readonly` / `ask` / `auto` 三种模式跑通。

### 阶段 2：Shell AST 解析

- 新增 `bbagent/core/shell_parser.py`。
- 使用 `bashlex` 解析；缺失或失败时 fallback 为 `unknown`。
- 输出 `ParsedCommand` dict。
- 支持 simple、pipeline、compound、redirect、command substitution、subshell features。
- 支持 `cd literal && command` 的 `effective_cwd` 推导。
- 生成稳定 fingerprint。

### 阶段 3：后端 API/WS

- AgentFactory 初始化和更新 approval manager。
- AgentFactory 实现 `resolve_tool_approval()`。
- remember 时写入 `toolPolicy.approval.allowed`。
- Chat WS 支持 `tool_approval_decision`。
- Team WS 支持 `tool_approval_decision`。

### 阶段 4：前端 UI

- 扩展 `ToolPolicy` 类型。
- Agent config 增加权限模式设置。
- ChatWindow 增加审批卡片。
- TeamChatWindow 增加审批卡片。
- Allowed list 管理 UI。

### 阶段 5：测试和质量门禁

- 核心单测：
  - `auto` 模式直接执行。
  - `readonly` 模式审批 `bash/write/edit`。
  - `ask` 模式未命中 allowed list 时审批。
  - remember 后相同 fingerprint 自动放行。
  - deny 返回 `ToolMessage`，不执行工具。
  - interrupt 取消 pending approval。
- shell parser 单测：
  - simple argv。
  - pipeline。
  - compound `&&`。
  - redirect。
  - command substitution。
  - `cd frontend && npm run build` 推导 `effective_cwd`。
  - 动态 `cd $DIR && ...` 不推导。
- 后端单测：
  - AgentFactory 写回 allowed rule。
  - WS decision 能 resolve pending request。
- 前端：
  - lint/build。

建议验证命令：

```bash
python -m pytest tests/unit/core
python -m pytest tests/unit/backend
ruff check bbagent backend tests
mypy bbagent backend
cd frontend
npm run lint
npm run build
```

## 风险和注意事项

### 不要让解析器成为绕过审批的入口

AST 解析失败、未知节点、动态特性，都必须进入审批。

### 不要直接 hash 原始命令

原始命令中空格、引号、等价写法会导致 fingerprint 不稳定。应 hash normalized structure。

### 不要把 `cd` 当成跨调用状态

当前 bash tool 每次新开 subprocess。单独 `cd frontend` 不会影响下一次 tool call。只能在同一条命令内静态推导 `effective_cwd`。

### 并行工具调用

模型可能一次产生多个 tool call。第一阶段可以允许多个 pending approvals，但 UI 要能分别 approve/deny。若复杂度过高，可以先在 `stream_tool_loop()` 串行执行 tool call。

### Team 成员身份

Team 中 agent name 可能未来允许重复。approval request 中最好携带 `agentId`，不要只依赖 `agentName`。

### SubAgent 间接风险

第一阶段审批 `sub_agent` 本身。后续如果需要更强安全性，应把父 Agent approval manager 透传给 SubAgent 内部工具执行。

