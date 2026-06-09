# BBagent 后端完整实现方案

## 1. 设计目标

- 将现有的前端 Mock 数据替换为真实的 Python 后端驱动
- 复用 `BBagent/core` 的全部能力（Agent/Team/Model/Tool/Skill/MCP/Session）
- 用户通过单一命令 `python run.py` 启动完整应用（后端 + 前端）
- 所有用户配置和状态持久化到本地文件系统，下次启动自动恢复

## 2. 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| Web 框架 | FastAPI | 异步、自动生成 OpenAPI 文档、原生支持 WebSocket |
| 进程管理 | uvicorn | ASGI 服务器 |
| 数据序列化 | Pydantic | 请求/响应校验，与前端类型对齐 |
| 状态持久化 | 文件系统 (JSON/YAML) | 直接复用 core 的 `save()`/`load()` 能力 |
| 跨域 | CORS | 开发模式全开，生产模式只允许本地 |
| 静态文件 | FastAPI StaticFiles | 生产模式托管 `frontend/dist` |

## 3. 目录结构

```
BBagent/
├── backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口 + 静态文件托管
│   ├── state.py             # StateManager: 统一状态管理 + 持久化
│   ├── api/
│   │   ├── __init__.py
│   │   ├── models.py        # Model 配置 CRUD
│   │   ├── agents.py        # Agent/Team CRUD + 运行控制
│   │   ├── skills.py        # Skill 扫描与列表
│   │   ├── mcps.py          # MCP Server CRUD + 激活控制
│   │   ├── prompts.py       # System Prompt 模板
│   │   ├── chat.py          # WebSocket 流式聊天
│   │   ├── files.py         # 文件系统操作 (working dir / base dir)
│   │   └── deps.py          # 共享依赖注入 (StateManager)
│   └── schemas.py           # Pydantic 模型定义
├── frontend/                # 现有前端代码
│   └── ...
├── BBagent/core/            # 核心库（已有）
│   └── ...
├── data/                    # 用户数据持久化目录（.gitignore）
│   ├── models/              # 模型配置（每个 .json 文件一个 Model）
│   ├── agents/              # Agent 独立目录
│   ├── teams/               # Team 独立目录
│   ├── skills/              # Skill 目录配置
│   │   └── skills.json      # Skill 目录路径列表
│   ├── mcps/                # MCP 服务器配置（每个 .json 文件一个 MCP）
│   ├── prompts/             # Prompt 模板（每个 .json 文件一个 Prompt）
│   └── store.json           # 前端 UI 状态（当前选中项等）
├── run.py                   # 一键启动脚本
└── pyproject.toml           # 依赖管理
```

## 4. 核心架构

### 4.1 StateManager（状态管理器）

`backend/state.py` 是连接前后端的桥梁。它负责：
1. 加载/保存所有配置资源（models, agents, teams, mcps, prompts）
2. 管理运行时的 Agent/Team 实例
3. 提供线程安全的访问接口

```python
class StateManager:
    """
    单例状态管理器。
    数据目录: PROJECT_ROOT / "data"
    """

    # --- 配置资源（JSON 持久化）---
    models: list[ModelConfig]
    mcp_servers: list[MCPServerConfig]
    prompts: list[PromptConfig]

    # --- 运行时实例（从 YAML 加载）---
    agents: dict[str, Agent]          # agent_id (UUID) -> Agent 实例
    teams: dict[str, AgentTeam]       # team_id (UUID) -> Team 实例

    # --- Agent 生命周期管理 ---
    _agent_dispatchers: dict[str, AgentOutputDispatcher]  # 每个 Agent 一个输出分发器
    _agent_tasks: dict[str, asyncio.Task]                 # 每个 Agent 一个持久事件循环 task

    # --- 前端 UI 状态 ---
    ui_state: UIState                 # 当前选中 tab、选中 agent 等

    # --- 核心方法 ---
    def load_all(self)                 # 启动时从 data/ 加载
    def save_all(self)                 # 退出时保存
    def create_agent(config) -> Agent  # 创建并持久化
    def create_team(config) -> AgentTeam
    def get_or_create_agent(name) -> Agent
    def delete_agent(agent_id)
    def delete_team(team_id)

    # --- Agent 生命周期 ---
    async def start_all_agents()        # 启动时自动启动所有已加载的 Agent
    async def start_agent(agent_id)     # 为 Agent 创建事件循环 task，注册 dispatcher
    async def stop_agent(agent_id)      # 停止 Agent 事件循环，取消 task
    def get_agent_state(agent_id) -> dict   # 返回 state + session_id
    def get_agent_sessions(agent_id) -> list[dict]  # 列出现有 sessions
    async def switch_agent_session(agent_id, session_id)  # 切换后自动更新 lastSessionId 并持久化
    async def new_agent_session(agent_id)                 # 新建后自动更新 lastSessionId 并持久化
    def get_agent_messages(agent_id) -> list[dict]
    def get_agent_dispatcher(agent_id) -> AgentOutputDispatcher | None
```

### 4.2 持久化策略

| 资源 | 格式 | 路径 | 说明 |
|------|------|------|------|
| Models | JSON | `data/models/{id}.json` | 每个 Model 独立一个 JSON 文件，启动时扫描目录加载 |
| MCP Servers | JSON | `data/mcps/{name}.json` | 每个 MCP 独立一个 JSON 文件，启动时扫描目录加载 |
| Prompts | JSON | `data/prompts/{id}.json` | 每个 Prompt 独立一个 JSON 文件，启动时扫描目录加载 |
| Agents | YAML + 目录 | `data/agents/{id}/{name}/` | 复用 `Agent.save()`/`load()` |
| Teams | YAML + 目录 | `data/teams/{id}/` | 复用 `AgentTeam.save()`/`load()` |
| Sessions | JSONL + MD | `data/agents/{id}/{name}/session/` | 复用 `Session.save()`/`load()` |
| UI State | JSON | `data/store.json` | 前端状态，如当前选中 agent |

**关键设计**：Agent/Team 的持久化完全复用 core 的能力，StateManager 只负责管理文件路径和注册表。

### 4.3 数据流

```
前端 (React + Zustand)
    |
    | HTTP / WebSocket
    v
后端 (FastAPI)
    |
    | 调用
    v
StateManager (backend/state.py)
    |
    | 读写
    v
文件系统 (data/)
    |
    | 加载/保存
    v
BBagent/core (Agent/Team/Model/...)
```

## 5. API 设计

### 5.1 REST API

#### Models
```
GET    /api/models                  -> list[ModelConfig]
POST   /api/models                  -> ModelConfig
PUT    /api/models/{model_id}       -> ModelConfig
DELETE /api/models/{model_id}       -> None
POST   /api/models/{model_id}/test  -> {content: str}
```

#### Agents
```
GET    /api/agents                         -> list[AgentConfig]    # 含 state + currentSessionId
GET    /api/agents/{id}                    -> AgentConfig          # 单个详情
POST   /api/agents                         -> AgentConfig          # 创建（id 由后端生成）
PUT    /api/agents/{id}                    -> AgentConfig          # 更新
DELETE /api/agents/{id}?delete_files=true/false  -> None         # delete_files=true 同时删除 basePath
POST   /api/agents/{id}/start              -> {state, session_id}  # 启动 Agent 事件循环
POST   /api/agents/{id}/stop               -> {state, session_id}  # 停止 Agent 事件循环

#### Hooks (descriptor)
```
GET    /api/hooks                          -> HookListResponse     # 内置 hook 描述符（动态驱动前端表单）
GET    /api/agents/{id}/state            -> {state, session_id}  # 查询运行状态
GET    /api/agents/{id}/sessions         -> list[SessionInfo]    # 列出现有会话
POST   /api/agents/{id}/sessions/{id}/switch -> {session_id, status}  # 切换会话
POST   /api/agents/{id}/sessions/new     -> {session_id}         # 新建会话
GET    /api/agents/{id}/messages         -> list[MessageDict]    # 加载历史消息
```

#### Teams
```
GET    /api/teams               -> list[TeamSummary]
GET    /api/teams/{id}          -> TeamConfig
POST   /api/teams               -> CreateTeamRequest -> TeamConfig + members
PUT    /api/teams/{id}          -> TeamConfig
DELETE /api/teams/{id}          -> None
POST   /api/teams/{id}/start    -> {state: str}
POST   /api/teams/{id}/stop     -> {state: str}
```

#### Skills
```
GET    /api/skills              -> list[SkillConfig]
POST   /api/skills/import       -> {imported: int, skills: list[SkillConfig]}
```

#### MCPs
```
GET    /api/mcps                -> list[MCPConfig]
POST   /api/mcps                -> MCPConfig
PUT    /api/mcps/{name}         -> MCPConfig
DELETE /api/mcps/{name}         -> None
POST   /api/mcps/{name}/discover    -> {tools: [...]}  # 一次性连接获取工具元数据
POST   /api/mcps/import         -> {imported: int}      # 扫描 .json 文件导入
```

#### Prompts
```
GET    /api/prompts             -> list[PromptConfig]
POST   /api/prompts             -> PromptConfig
PUT    /api/prompts/{id}        -> PromptConfig
DELETE /api/prompts/{id}        -> None
POST   /api/prompts/import      -> {imported: int}    # 扫描 .md/.txt 文件导入，支持 group 参数
```

PromptConfig 字段：`id`, `name`, `content`, `group`(可选，空字符串表示未分组)

#### Files
```
GET    /api/files/tree?path={dir}   -> FileTreeNode[]
GET    /api/files/read?path={file}  -> {content, type}
GET    /api/files/raw?path={file}   -> Raw file content (for image/PDF preview)
POST   /api/files/write             -> None
GET    /api/files/dirs?path={dir}   -> {current, parent, separator, directories: list[str]}
```
```

#### UI State
```
GET    /api/state               -> UIState
POST   /api/state               -> UIState             # 保存前端状态
```

### 5.2 WebSocket API（流式聊天）

```
WS /api/ws/chat                      # 单 Agent 聊天（持久连接，通过 switch_agent 切换）
WS /api/ws/team/{team_id}            # Team 群聊
```

#### 5.2.1 单 Agent 聊天 (`/ws/chat`)

WebSocket 连接为持久连接，在 Agent 切换时不重建。前端通过 `switch_agent` 消息切换订阅目标，后端在 Dispatcher 层切换输出流。

Agent 以 `start()` 持久事件循环运行。WebSocket 连接不直接驱动 Agent 执行，而是通过 `AgentOutputDispatcher` 订阅 Agent 输出流。

**架构**：
```
Agent.start() 事件循环（后台 asyncio.Task）
   │
   │ output chunks
   ▼
AgentOutputDispatcher (per-agent，fan-out)
   │
   ├──► WebSocket subscriber 1  ──► frontend browser tab A
   ├──► WebSocket subscriber 2  ──► frontend browser tab B
   └──► Team WebSocket subscriber  ──► team group chat
```

**前端 → 后端**：
```json
{"type": "switch_agent", "agent_id": "uuid-xxx", "agent_name": "my-agent"}
{"type": "user_message", "content": "Hello"}
{"type": "human_answer", "content": "8080"}
{"type": "interrupt"}
```

**后端 → 前端（流式）**：
```json
{"type": "switched", "agent_name": "my-agent", "agent_state": "waiting", "context_tokens": 0}
{"type": "agent_state", "state": "running", "context_tokens": 12345}
{"type": "text", "content": "Hello"}
{"type": "thinking", "content": "..."}
{"type": "completed_tool_use", "content": {...}}
{"type": "tool_results", "content": [...]}
{"type": "completed_message", "content": {...}}
{"type": "agent_state", "state": "waiting", "context_tokens": 23456}
{"type": "agent_state", "state": "error", "context_tokens": 0}
{"type": "agent_state", "state": "ready", "context_tokens": 23456}
{"type": "error", "content": "..."}
```

Chat WebSocket handler 的两个并发任务：
1. **receiver**: 读取 WebSocket 消息 → `user_message` 推入 `agent.input.push(content)`，`interrupt` 调用 `agent.interrupt()`，`switch_agent` 切换订阅
2. **forwarder**: 从 dispatcher 订阅队列拉取 chunk → 转发给 WebSocket 客户端

#### 5.2.2 Team 群聊 (`/ws/team/{team_name}`)

Team 的 WebSocket 订阅所有成员 Agent 的 dispatcher，汇总输出。用户通过 `@agent_name` 前缀将消息路由到特定成员。

**前端 → 后端**：
```json
{"type": "user_message", "content": "@coder fix this bug", "mentions": ["coder"]}
```

**后端 → 前端**：
```json
{"type": "text", "content": "I'll fix it", "source_agent": "coder"}
{"type": "thinking", "content": "...", "source_agent": "coder"}
```

**@mention 解析**：后端自动从消息内容提取 `@name` 前缀，将去除了@前缀的消息推送到被 mention 的 Agent 的 input 队列。如无 mention，返回 system 提示。`mentions` 字段由前端解析后显式传入（优先），否则后端自动用正则解析。

后端直接复用 `agent.run(human_msg)` 的异步生成器，将 chunk 转发给 WebSocket。

## 6. Pydantic Schemas（前后端类型对齐）

```python
# backend/schemas.py

class ModelConfig(BaseModel):
    name: str
    provider: Literal["anthropic", "openai"]
    model: str
    api_key: str
    base_url: str
    max_completion_tokens: int
    max_context_tokens: int
    temperature: float
    top_p: float
    thinking: dict | None = None

class AgentConfig(BaseModel):
    """Frontend-facing agent configuration payload. extra="ignore" so old
    fields (basePath/hookEnabled/messages/policy) on request are silently
    dropped for backward compat.

    Per the unified-id design:
    - id: UUID, machine identity. Generated by backend on POST; frontend
      never sets it. All URL paths and storage addresses use id.
    - name: display name, may be duplicated across agents.
    - toolIds: list of ToolConfig.id (UUIDs)
    - skillIds: list of SkillConfig.id (UUIDs)
    """
    model_config = ConfigDict(extra="ignore")

    # Identity
    id: str = ""                     # UUID (backend-generated)
    name: str                        # display name

    # Basic
    type: Literal["single", "team"] = "single"
    modelId: str                # 关联 ModelConfig.id
    systemPrompt: str = ""
    workingDir: str = ""        # 顶层；前端同步到 toolPolicy.cwd
    basePath: str = ""          # 响应字段；后端自动生成后回填

    # Tools
    toolIds: list[str] = []     # ToolConfig.id (UUID) 列表
    skillIds: list[str] = []    # SkillConfig.id (UUID) 列表
    toolPolicy: dict = {}       # 含 cwd（前端提交时同步 workingDir 到 cwd）

    # Hooks
    hookNames: list[str] = []   # 启用的 hook 列表
    hookConfig: dict = {}       # 共享大字典；后端解析 submodelId

    # Team
    teamDescription: str = ""
    contacts: dict[str, dict[str, str]] = {}  # {agentName: {otherName: role}}，不含 self-key
    teamPrompt: str = ""

# === Hook 描述符 schema (GET /api/hooks) ===
HookFieldType = Literal["string", "text", "number", "float", "boolean", "modelId"]

class HookFieldSchema(BaseModel):
    key: str
    type: HookFieldType
    label: str = ""
    default: Any = None
    description: str = ""

class HookSection(BaseModel):
    title: str
    fields: list[HookFieldSchema]

class HookDescriptor(BaseModel):
    name: str
    displayName: str
    description: str = ""
    defaultEnabled: bool = True
    fieldSections: list[HookSection] = []

class HookListResponse(BaseModel):
    hooks: list[HookDescriptor]
    sharedSections: list[HookSection] = []

class TeamSummary(BaseModel):
    id: str                       # team_id (UUID)
    name: str
    agentCount: int
    teamDescription: str = ""
    # state 由 API 层手动注入（运行时状态，非配置）

class TeamConfig(BaseModel):
    id: str = ""                  # team_id (UUID, backend-generated)
    name: str
    teamDescription: str = ""
    workingDir: str = ""
    memberIds: list[str] = []     # member agent IDs (UUID)
    contacts: dict[str, dict[str, str]] = {}  # {agentName: {otherName: role}}，不含 self-key
    # state 由 API 层手动注入（运行时状态，非配置）

class CreateTeamRequest(BaseModel):
    """Frontend-facing team creation payload.

    Separates team-level config from member agent configs, so the frontend
    no longer needs to send a bloated Agent object with empty placeholder
    fields for the team itself.

    workingDir is the shared working directory for all member agents.
    """
    name: str
    teamDescription: str = ""
    workingDir: str = ""
    members: list[AgentConfig] = []
    contacts: dict[str, dict[str, str]] = {}

class SkillConfig(BaseModel):
    id: str                       # skill_id (UUID)
    name: str
    description: str
    path: str

class MCPConfig(BaseModel):
    name: str
    command: str
    args: list[str]
    env: dict[str, str]

class PromptConfig(BaseModel):
    id: str
    name: str
    content: str

class UIState(BaseModel):
    current_tab: Literal["agent", "team"] = "agent"
    current_agent: str | None = None
    current_team: str | None = None
    settings_open: bool = False
    settings_tab: str = "models"
```

## 7. 关键实现细节

### 7.1 Agent 创建流程

```python
# backend/api/agents.py

@router.post("")
async def create_agent(config: AgentConfig):
    # 1. 查找模型
    model_cfg = state_manager.get_model(config.modelId)
    model = Model.from_config_dict(model_cfg.dict())

    # 2. 生成 agent_id
    agent_id = config.id or uuid4().hex

    # 3. 收集工具 (toolIds 存 ToolConfig.id)
    # tools = ToolManager.distribute(agent_id=agent_id, template_ids=config.toolIds)

    # 4. 收集技能 (skillIds 存 SkillConfig.id)
    skills = [state_manager.skills[sid] for sid in config.skillIds if sid in state_manager.skills]

    # 5. 创建 Agent
    agent_config = AgentConfig(
        model=model,
        name=config.name,
        system_prompt=config.system_prompt,
        tools=tools,
        skills=skills,
    )
    agent = Agent(agent_config)

    # 6. 持久化 (路径: data/agents/{agent_id}/{name}/)
    agent.save()
    state_manager.agents[agent_id] = agent
    state_manager.save_ui_state()

    return config
```

### 7.2 WebSocket 聊天实现

Chat WebSocket 使用**持久连接 + switch_agent** 架构。前端在 Agent 切换时不关闭/重连 WS，而是发送 `switch_agent` 消息。后端在 Dispatcher 层切换订阅的 Agent 输出流。

```python
# backend/api/chat.py

@router.websocket("/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()

    queue: asyncio.Queue | None = None
    current_agent_name: str | None = None
    subscriber_id = f"ws:{uuid4().hex[:8]}"
    switch_lock = asyncio.Lock()

    async def subscribe_to(agent_name: str) -> bool:
        nonlocal queue, current_agent_name
        # Validate new agent first, then unsubscribe old, then subscribe new with replay
        ...

    # forwarder: reads from mutable queue reference, handles sentinel for queue switching
    async def forwarder():
        while not stopped:
            chunk = await asyncio.wait_for(queue.get(), timeout=0.5)
            if chunk is _RESUBSCRIBE_SENTINEL: continue  # queue switched
            ...

    # receiver: handles switch_agent, user_message, interrupt, human_answer
    async for msg in websocket.iter_json():
        if msg["type"] == "switch_agent":
            async with switch_lock:
                await subscribe_to(msg["agent_name"])
        elif msg["type"] == "user_message":
            agent.input.push(msg["content"])
        ...
```

**关键变更**（对比旧版 `agent.run()` 方式）：
- **Agent 持久事件循环**：Agent 通过 `start()` 在后台 `asyncio.Task` 中运行，持续监听 input queue。
- **订阅者模式**：多个 WebSocket 客户端可同时订阅同一个 Agent 的输出。
- **持久 WS 连接**：前端创建一条 WS 连接，切换 Agent 时发送 `switch_agent` 消息，后端通过 sentinel 机制无缝切换 forwarder 的消费队列。
- **replay 机制**：切换到新 Agent 时使用 `subscribe(replay=True)`，Dispatcher 将当前 in-progress round 的缓冲 chunks 回放给新订阅者，避免消息丢失。

#### 7.2.1 ask_human Tool + AskHumanState

The `ask_human` tool is an async built-in tool (`BBagent/built_in_tool/ask_human.py`). When invoked, it:
1. Calls the `on_question` callback (sends `human_question` to frontend via WebSocket)
2. Creates an `asyncio.Future` and awaits it (blocks the agent loop)
3. When the user answers via WebSocket `human_answer`, the Future resolves
4. Returns `"User answer: {answer}"` as the tool result

`AskHumanState` is stored as `tool._ask_human_state` attribute on the Tool object. The backend wires `on_question` to a WebSocket send, and resolves `future` when a `human_answer` message arrives.

#### 7.2.2 Team 群聊 WebSocket (`/ws/team/{team_id}`)

`backend/api/team_ws.py` — Team 群聊 handler。

```python
@router.websocket("/team/{team_id}")
async def team_chat_ws(websocket: WebSocket, team_id: str):
    team = state_manager.teams.get(team_id)

    # 订阅所有成员 Agent 的 dispatcher
    member_queues: dict[str, asyncio.Queue] = {}
    for member_name in team.agents:
        dispatcher = state_manager.get_agent_dispatcher(member_name)
        if dispatcher:
            q = dispatcher.subscribe(subscriber_id)
            member_queues[member_name] = q

    # forwarder: 合并所有成员的输出，标注 source_agent
    async def forwarder():
        await asyncio.gather(*[_forward_member(ws, name, q) for name, q in member_queues.items()])

    # receiver: 解析 @mention，路由到对应 Agent 的 input queue
    async for msg in websocket.iter_json():
        content = msg.get("content", "")
        mentions = msg.get("mentions", [])
        if not mentions:
            mentions = _parse_mentions(content)  # 正则提取 @name
        if mentions:
            stripped = content  # 去除 @name 前缀
            for member_name in mentions:
                member_agent = team.agents.get(member_name)
                if member_agent:
                    member_agent.input.push(stripped, source_id=f"team:{team_name}:user")
```

**@mention 路由机制**：
1. 前端实时解析 `@` 触发 autocomplete 下拉菜单
2. 发送时显式传入 `mentions` 数组（优先使用）
3. 后端也可以自动正则提取 `@name` 作为 fallback
4. 每条消息可 @mention 多个 agent（消息会被分发到所有被 mention 的 agent）
5. 被 mention 的 agent 通过其 `agent.input.push()` 接收消息，在自身事件循环中处理

### 7.3 AgentOutputDispatcher（输出分发器）

`backend/dispatcher.py` — 每个 Agent 绑定一个 `AgentOutputDispatcher`，实现 fan-out 输出模式。

```python
class AgentOutputDispatcher:
    def __init__(self):
        self._subscribers: dict[str, asyncio.Queue] = {}
        self._round_buffer: list[dict] = []      # 当前 round 的 chunk 缓冲（最多 500 条）
        self._buffer_capacity = 500

    async def on_chunk(self, chunk):
        """Agent 输出回调：缓冲 chunk 到 round buffer，广播到所有订阅者"""
        self._round_buffer.append(chunk)
        if len(self._round_buffer) > self._buffer_capacity:
            self._round_buffer.pop(0)
        if chunk.get("type") in ("completed_message", "interrupted"):
            self._round_buffer.clear()
        elif chunk.get("type") == "agent_state" and chunk.get("state") == "error":
            self._round_buffer.clear()
        for q in list(self._subscribers.values()):
            await q.put(chunk)

    def subscribe(self, subscriber_id: str, replay: bool = False) -> asyncio.Queue:
        """创建订阅队列。replay=True 时先回放 round_buffer 中的 chunks"""
        q = asyncio.Queue()
        if replay and self._round_buffer:
            for chunk in self._round_buffer:
                q.put_nowait(chunk)
        self._subscribers[subscriber_id] = q
        return q

    def unsubscribe(self, subscriber_id: str):
        """取消订阅，向队列推送 sentinel 以唤醒 forwarder"""
        q = self._subscribers.pop(subscriber_id, None)
        if q is not None:
            q.put_nowait(_RESUBSCRIBE_SENTINEL)

    async def broadcast_system(self, content: str):
        """发送系统消息广播"""
```

**数据流**：
```
Agent.start() event loop
    │
    │ agent.on_output(dispatcher.on_chunk)  ← 注册回调
    │
    ▼
AgentOutputDispatcher.on_chunk(chunk)
    │
    ├──► asyncio.Queue (WS subscriber A) → WebSocket A → frontend tab A
    ├──► asyncio.Queue (WS subscriber B) → WebSocket B → frontend tab B
    └──► asyncio.Queue (team WS subscriber) → team_ws forwarder → frontend team chat
```

Agent 在 `start()` 启动时注册回调：`agent.on_output(dispatcher.on_chunk)`。Agent 每次产生输出 chunk 时调用 dispatcher，dispatcher 将 chunk 推入所有订阅者的 asyncio.Queue。

### 7.4 Agent 生命周期管理

Agent 以 `start()` / `stop()` 管理持久事件循环的启动与停止。

```python
# backend/state.py

async def start_agent(self, name: str):
    agent = self.agents.get(name)
    dispatcher = self._agent_dispatchers.get(name)
    agent.on_output(dispatcher.on_chunk)      # 注册输出回调
    task = asyncio.create_task(agent.start())  # 启动事件循环
    self._agent_tasks[name] = task

async def stop_agent(self, name: str):
    agent = self.agents.get(name)
    await agent.stop()                        # 停止事件循环
    task = self._agent_tasks.pop(name, None)
    if task: task.cancel()                    # 取消 asyncio.Task
    dispatcher.broadcast_system(...)          # 通知订阅者
```

**auto-start on boot**：FastAPI `lifespan` 事件中调用 `state_manager.start_all_agents()`，遍历已加载的所有 Agent，逐一调用 `start_agent()`。每个 Agent 启动后进入 Waiting 状态，持续监听 input queue。

**Agent 状态机**：
- `Ready` — 已加载但未启动（灰色）
- `Waiting` — 事件循环运行中，等待用户输入（绿色静点）
- `Running` — 正在处理消息/执行工具（绿色脉冲）
- `Error` — 运行出错（红色）

### 7.5 SubAgent Tool

`BBagent/built_in_tool/sub_agent.py` — Delegate tasks to an independent sub-agent with its own model and tools.

```
接口: SubAgent(task, system_prompt, allowed_tools) -> str
```

**创建流程** (`create_sub_agent_tool`):
1. 从 Policy 提取 `sub_agent_model` (完整 ModelConfig dict) 和 `sub_agent_blocked_tools` 列表
2. `sub_agent` 工具本身被永远禁止（防止无限递归）
3. 预创建所有 built-in 工具实例（从 TOOL_CREATOR），缓存到闭包
4. 动态构建 description：列出所有可用工具名及功能，标注 `[BLOCKED]` 标记
5. 返回 `Tool(name="SubAgent", ...)`

**调用流程** (`sub_agent_func`):
1. 校验 `sub_agent_model` 已配置
2. 计算有效工具：`allowed_tools` - `blocked_tools` - `sub_agent`，从缓存查找 Tool 实例
3. `Model.from_config_dict(sub_agent_model)` 构建独立模型
4. 创建 `SubAgent(model, tools, system_prompt)` 并 `run(task)`
5. `task` 字符串自动包装为 `HumanMessage`

**Policy 扩展字段**:
```python
sub_agent_model: Optional[dict] = None      # 完整的 ModelConfig
sub_agent_blocked_tools: Optional[list[str]] = None  # 硬黑名单
```

### 7.6 启动时加载流程

```python
# backend/state.py

def load_all(self):
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # 1-4. 加载 Models/MCPs/Prompts/Skills（同上）
    # ...

    # 5. 加载 Agents（从各自目录），同时创建 AgentOutputDispatcher
    agents_dir = data_dir / "agents"
    if agents_dir.exists():
        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir() and (agent_dir / "agent_config.yaml").exists():
                try:
                    agent = Agent.load(agent_dir)
                    self.agents[agent.name] = agent
                    self._agent_dispatchers[agent.name] = AgentOutputDispatcher()
                except Exception as e:
                    logger.warning(f"Failed to load agent from {agent_dir}: {e}")

    # 6. 加载 Teams
    teams_dir = data_dir / "teams"
    if teams_dir.exists():
        for team_dir in teams_dir.iterdir():
            if team_dir.is_dir() and (team_dir / "team_config.yaml").exists():
                try:
                    team = AgentTeam.load(team_dir)
                    self.teams[team.name] = team
                except Exception as e:
                    logger.warning(f"Failed to load team from {team_dir}: {e}")

    # 7. 加载 UI 状态
    store_path = data_dir / "store.json"
    if store_path.exists():
        self.ui_state = UIState(**json.loads(store_path.read_text()))
```

## 8. 启动方式

### 8.1 开发模式（前后端分离）

终端 1：启动后端
```bash
cd /Users/gonglin/Desktop/note/BBagent
python -m backend.main
# 默认端口 8000
```

终端 2：启动前端
```bash
cd /Users/gonglin/Desktop/note/BBagent/frontend
npm run dev
# 默认端口 5173，代理到 8000
```

### 8.2 生产模式（单一进程）

```bash
cd /Users/gonglin/Desktop/note/BBagent
python run.py
```

`run.py` 逻辑：
1. 先执行 `npm run build`（如果 dist 不存在或源码更新）
2. 启动 FastAPI，通过 `StaticFiles` 托管 `frontend/dist`
3. FastAPI `lifespan` 事件中调用 `state_manager.start_all_agents()` 自动启动所有已加载的 Agent 事件循环
4. 用户访问 `http://localhost:8000` 即可

```python
# run.py
import os
import signal
import subprocess
import uvicorn


def kill_old_server(port: int = 8000):
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
        pids = [int(pid) for pid in result.stdout.strip().split() if pid]
        for pid in pids:
            os.kill(pid, signal.SIGKILL)
            print(f"Killed old process PID={pid} on port {port}")
    except Exception:
        pass


def main():
    kill_old_server(8000)
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["backend"],
    )


if __name__ == "__main__":
    main()
```

```python
# backend/main.py（生产模式）
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    await state_manager.start_all_agents()  # auto-start all agents on boot
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(api_router, prefix="/api")

# 生产模式：托管前端构建产物
dist_path = Path(__file__).parent.parent / "frontend" / "dist"
if dist_path.exists():
    app.mount("/assets", StaticFiles(directory=dist_path / "assets"), name="assets")
    app.mount("/icons", StaticFiles(directory=dist_path / "icons"), name="icons")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index_file = dist_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"error": "Frontend not built"}
```

## 9. 状态持久化方案

### 9.1 持久化时机

| 操作 | 持久化内容 | 时机 |
|------|-----------|------|
| 创建/更新 Model | `data/models/{id}.json` | API 调用后立即 |
| 创建/更新 MCP | `data/mcps/{name}.json` | API 调用后立即 |
| 创建/更新 Prompt | `data/prompts/{id}.json` | API 调用后立即 |
| 创建/更新 Agent | `data/agents/{name}/agent_config.yaml` | API 调用后立即 + `agent.save()` |
| 创建/更新 Team | `data/teams/{name}/team_config.yaml` | API 调用后立即 + `team.save()` |
| 聊天过程中 | Session JSONL + MD | `session.save()` 自动触发（Agent.run / _handle_event 的 finally） |
| Agent stop | Session MD | `session.save()` 在 `agent.stop()` 之前落盘 |
| Agent delete | Session MD | stop 失败时兜底 `session.save()` |
| 应用关闭 | 所有 active Session MD | lifespan 关闭时遍历所有 agent 调用 `session.save()` |
| UI 状态 | `data/store.json` | 前端主动调用 `/api/state` 或后端定期保存 |

### 9.2 Session Metadata 持久化时机

Session 的 `.md` 文件（包含 turn_count、last_updated 等元数据）在以下四个位置触发持久化，消除与 `.jsonl` 之间的一致性窗口：

| 触发位置 | 代码路径 | 说明 |
|---------|---------|------|
| 正常 turn 结束 | `core/agent.py` — `run()` 的 `finally` 块 | 每次 Agent 回复完成后自动保存，与 `.jsonl` 同步 |
| 事件处理结束 | `core/agent.py` — `_handle_event()` 的 `finally` 块 | timer / team 事件入口的兜底保存 |
| Agent stop | `backend/factories/agent_factory.py` — `stop()` | 在 `agent.stop()` 之前落盘，防止用户 Stop 后立即关闭应用丢数据 |
| Agent delete | `backend/factories/agent_factory.py` — `delete()` | stop 失败时的兜底保存，防止 `shutil.rmtree` 前丢数据 |
| 应用关闭 | `backend/main.py` — `lifespan` 关闭路径 | 遍历所有 active agent 调用 `session.save()`，覆盖 Ctrl+C / SIGTERM / reload 场景 |

此外，Session 的创建（`Session.create`）和切换（`Session.fork`）也会触发 `session.save()`。

### 9.3 首次启动（Onboarding）

如果 `data/` 目录不存在或为空：
1. 后端返回空列表给前端
2. 前端展示 Onboarding 引导页
3. 用户配置第一个 Model → 保存到 `data/models/{id}.json`
4. 用户创建第一个 Agent → 保存到 `data/agents/{name}/`

## 10. 与前端对接要点

### 10.1 前端修改清单

1. **移除 Mock 数据**：`store/index.ts` 中的 `mockModels` / `mockAgents` 等改为从 API 获取
2. **API 客户端**：新增 `lib/api.ts`，封装 `fetch` 调用后端 REST API
3. **WebSocket 客户端**：新增 `lib/ws.ts`，封装 WebSocket 连接管理
4. **Zustand Store 改造**：
   - `loadState()` 改为调用 `GET /api/state`
   - `addModel()` 改为调用 `POST /api/models`
   - `sendMessage()` 改为通过 WebSocket 发送
5. **环境变量**：`.env.development` 中 `VITE_API_BASE=http://localhost:8000/api`

### 10.2 类型映射

前端 `types/index.ts` 与后端 `schemas.py` 保持字段一致：
- `Model` ↔ `ModelConfig`
- `Agent` ↔ `AgentConfig`
- `AgentTeam` ↔ `TeamConfig`
- `Skill` ↔ `SkillConfig`
- `MCPServer` ↔ `MCPConfig`
- `Prompt` ↔ `PromptConfig`

## 11. 实施阶段

### Phase 1: 骨架搭建
- [ ] 创建 `backend/` 目录结构
- [ ] 写 `backend/schemas.py`（Pydantic 模型）
- [ ] 写 `backend/state.py`（StateManager 骨架）
- [ ] 写 `backend/main.py`（FastAPI 骨架 + CORS）
- [ ] 写 `run.py`

### Phase 2: 配置资源 API
- [ ] 实现 `/api/models` CRUD
- [ ] 实现 `/api/mcps` CRUD
- [ ] 实现 `/api/prompts` CRUD
- [ ] 实现 `/api/skills` 扫描
- [ ] 前端对接：Settings 四个 Tab 走真实 API

### Phase 3: Agent/Team API
- [ ] 实现 `/api/agents` CRUD
- [ ] 实现 `/api/teams` CRUD
- [ ] 前端对接：AgentTabs、TeamDropdown 走真实 API

### Phase 4: 文件系统 API
- [ ] 实现 `/api/files/tree`
- [ ] 实现 `/api/files/read`
- [ ] 前端对接：WorkingDir / BaseDir 面板

### Phase 5: WebSocket 聊天
- [x] 实现 `/api/ws/chat`（持久连接，switch_agent 切换订阅）
- [x] 前端对接：ChatWindow 从 WebSocket 接收流式消息

### Phase 6: 生产模式
- [ ] 配置 `StaticFiles` 托管前端 dist
- [ ] 验证 `python run.py` 一键启动
- [ ] 首次启动 Onboarding 流程端到端测试


---

## 12. Recent Updates (2026-05-28)

### 12.1 New API: Directory Listing

`GET /api/files/dirs?path=~`

Returns flat list of immediate subdirectories for folder browser UI (used by FolderPicker component for Base Path, Policy Working Directory, and Import from Folder in Skills/MCPs/Prompts):

```json
{"current": "/Users/gonglin", "parent": "/Users", "separator": "/", "directories": ["Desktop", "Documents"]}
```

### 12.2 New API: Model Test

`POST /api/models/{model_id}/test`

Body: `{"prompt": "Hello"}`. Returns: `{"content": "Hello! ..."}`

Backend builds Model from ModelConfig, creates Model_Input with HumanMessage, calls async_invoke, extracts text from response.

### 12.3 AgentConfig Schema Changes

AgentConfig 字段按三组分类（与 [api-mapping.md#7.1](file:///Users/gonglin/Desktop/note/BBagent/doc/api-mapping.md) 对齐）：

- **Basic（基本信息）**：
  - `name: str`（必填）
  - `type: Literal["single", "team"] = "single"`
  - `modelId: str`（必填）
  - `systemPrompt: str = ""`
  - `workingDir: str = ""`（**顶层字段**，后端映射到 `policy.cwd`）
  - `basePath: str = ""`（**响应字段**，前端不发送，后端自动生成后回填）
- **Tools（工具配置）**：
  - `toolIds: list[str] = []`
  - `skillIds: list[str] = []`
  - `toolPolicy: dict = {}`（**含 cwd**；前端提交时同步 workingDir 到 cwd；各 tool creator 取所需字段）
- **Hooks（Hook 配置）**：
  - `hookNames: list[str] = []`（启用的 hook 列表）
  - `hookConfig: dict = {}`（**共享大字典**；snake_case；后端解析 `submodelId` 为 Model 实例）
- **Team 字段**：`teamDescription`、`contacts`、`teamPrompt`（team 流程使用）

**删除字段**：`messages`（不再在请求中传递）、`hookEnabled`（拆为 `hookNames` + `hookConfig`）。

**额外配置**：`model_config = ConfigDict(extra="ignore")`，旧请求体中的 `basePath`/`hookEnabled`/`messages`/`policy` 会被静默忽略，向后兼容。

### 12.4 list_agents Returns Full Configs

`GET /api/agents` 返回完整 `AgentConfig` 对象（通过 `get_agent_config`），包含 `basePath`（自动生成）、`workingDir`（来自 `policy.cwd`）、`toolPolicy`（不含 cwd）、`hookNames`（启用列表）、`hookConfig`（共享字典）。

### 12.5 get_agent_config Updated

`StateManager.get_agent_config()` 现在填充：
- `workingDir` ← `agent.policy.cwd`
- `basePath` ← `str(agent.base_dir)`
- `toolPolicy` ← `agent.policy` 去掉 `cwd` 后的部分（camelCase 转换）
- `hookNames` ← `_agent_hook_metas` 里的 source 列表
- `hookConfig` ← 合并 `_agent_hook_metas` 各 entry 的 config 字典（共享）

### 12.5.1 create_agent 处理流程

```python
async def create_agent(self, config: AgentConfig) -> Agent:
    with log_operation(logger, "create_agent", agent_name=config.name):
        # 1. 解析共享 Model 实例（refcount++）
        #    - 缓存命中：直接返回并 refcount++
        #    - 缓存未命中：从 ModelConfig 构建新实例，注册到 _model_instances
        model = self._resolve_model(config.modelId)
        
        agent = None
        agent_dir_to_cleanup = None
        try:
            # 2. 构造 metas（轻量，分类 toolIds / skillIds / hookConfig）
            tool_metas, mcp_metas = self._build_tool_metas(config.toolIds)
            skill_metas = self._build_skill_metas(config.skillIds)
            shared_hook_config = self._build_shared_hook_config(config.hookConfig)
            
            # 3. 构造 core Agent + save
            core_kwargs = {"model": model, "base_dir": DATA_DIR / "agents",
                           "system_prompt": config.systemPrompt}
            if config.name.strip():
                core_kwargs["name"] = config.name.strip()
            core_config = CoreAgentConfig(**core_kwargs)
            agent = Agent(core_config)
            agent_dir_to_cleanup = agent.base_dir
            agent.save()
            
            actual_name = agent.name
            
            # 4. 合并 toolPolicy（含 cwd）和 workingDir
            policy_snake = _policy_to_snake(config.toolPolicy or {})
            cwd = (config.workingDir or "").strip() or str(agent.base_dir)
            policy_snake["cwd"] = cwd
            agent.policy = policy_snake
            
            # 5. 缓存 metas 到 _agent_* 字典
            self._agent_tool_metas[actual_name] = tool_metas
            self._agent_mcp_metas[actual_name] = mcp_metas
            self._agent_skill_metas[actual_name] = skill_metas
            self._agent_hook_metas[actual_name] = self._api_to_hook_metas(
                config.hookNames, config.hookConfig or {}
            )
            self._agent_model_ids[actual_name] = config.modelId
            self._agent_shared_hook_config[actual_name] = shared_hook_config
            
            self.agents[actual_name] = agent
            agent.logger.set_console_level(logging.CRITICAL + 1)
            self._agent_dispatchers[actual_name] = AgentOutputDispatcher()
            
            # 6. 持久化 started=false 等附加字段到 yaml
            self._save_agent_yaml_extras(actual_name, started=False)
            
            # 7. 不再自动 start_agent；调用方（前端 / 业务流）显式启动
            return agent
        
        except Exception:
            # 完整回滚：清理 metas、self.agents、yaml 目录、释放 model
            if agent is not None:
                name = agent.name
                self.agents.pop(name, None)
                for cache in (self._agent_tool_metas, self._agent_mcp_metas,
                              self._agent_skill_metas, self._agent_hook_metas,
                              self._agent_timer_metas, self._agent_shared_hook_config):
                    cache.pop(name, None)
                self._agent_model_ids.pop(name, None)
                self._agent_dispatchers.pop(name, None)
            if agent_dir_to_cleanup and agent_dir_to_cleanup.exists():
                shutil.rmtree(agent_dir_to_cleanup, ignore_errors=True)
            await self._release_model(config.modelId)
            raise
```

**关键设计**：
- **共享 Model 实例**：多个 agent 用同一 modelId 时共享一个 `Model` 对象（包括共享 `httpx.AsyncClient` 连接池）
- **create 不自动 start**：API 层解耦创建和启动；前端在拿到响应后立即调 `start_agent`
- **完整回滚**：任意步骤失败都会清理 metas、self.agents、yaml 目录、释放 model 引用

### 12.5.2 update_agent 增量更新

支持部分更新（`updates: dict`）。`toolPolicy` 和 `workingDir` 任一变化时重算 `policy.cwd` 并重建所有内置 tool。`hookNames` 或 `hookConfig` 变化时清空所有 hook 后按新配置重建（option A）。`modelId` 变化时调用 `_resolve_model(new)` + `_release_model(old)`。

### 12.5.3 Hook 描述符接口

`GET /api/hooks` 返回 `HookListResponse`，包含每个 hook 的 displayName/description/fieldSections，以及全局 `sharedSections`（如 `submodelId`、`merge_ratio`、`small_turn_cap`）。字段类型从 `BuiltinHookConfig` dataclass 自动读取默认值；新增 hook 时只需要扩展 [`_HOOK_DEFINITIONS`](file:///Users/gonglin/Desktop/note/BBagent/backend/api/hooks.py)。

### 12.5.4 Model 实例共享与 refcount

**目标**：多个 agent 引用同一 `ModelConfig.id` 时共享一个 `Model` 实例，节省内存 + 共享 HTTP 连接池。

**核心数据结构**：
```python
self._model_instances: dict[str, Model]    # key = ModelConfig.id
self._model_refcount: dict[str, int]       # 每个 id 的引用计数
```

**辅助方法**：
- `_resolve_model(model_id) -> Model`：缓存命中则 refcount++，未命中则 `Model.from_config_dict` 新建并 refcount=1
- `_release_model(model_id)`：refcount--；降到 0 时 `await model.aclose()` 并从 cache 移除
- `invalidate_model(model_id) -> list[str]`：强制 aclose + 移除缓存实例；然后为受影响的 agent 自动 acquire 新 Model 实例并调用 `agent.change_model()` 热替换；返回受影响的 agent_id 列表
- `update_model_and_invalidate(...)`：更新配置 + invalidate（agent 自动热替换新模型，无需重启）
- `delete_model_and_invalidate(...)`：先收集受影响 agent → 停止这些 agent → 删除配置 + invalidate；返回受影响的 agent_id 列表（前端提示用户重新选择模型）

**生命周期**：
- 应用启动时 `_load_agents` 会为每个 agent 调一次 `_resolve_model`（refcount 递增）
- `delete_agent` 调 `_release_model` 减计数
- 计数降到 0 才真正 `aclose`，避免反复开关连接

**失效场景**：
- 用户更新 model config（API key 等）→ 失效缓存 → 自动为受影响 agent 热替换新 Model 实例 → 返回 affected_agents（前端提示"已自动生效"）
- 用户删除 model config → 先停止受影响 agent → 删除配置 + 失效缓存 → 返回 affected_agents（前端提示"需要重新选择模型"）

### 12.5.5 启动状态持久化与启动恢复

**yaml 新增 `started: bool` 字段**：
- `create_agent` 完成后写入 `started: false`
- `start_agent` 完成后写入 `started: true`
- `stop_agent` 完成后写入 `started: false`

**应用启动恢复**：
- `load_all` 调用流程：
  1. `_load_agents`：从 yaml 加载所有 agent 元数据 + Model 实例
  2. **`_load_one` 中恢复 lastSessionId**：若 `agent_config.json` 中存在 `lastSessionId` 且对应 session 文件存在，则通过 `Session.load` 恢复该会话，否则保留默认的新建空 session
  3. **`start_persisted_agents`**：扫描 `self._agent_persisted_started`（在 `_load_one_agent` 中从 yaml 的 `started` 字段填入），对值为 `true` 的 agent 调 `start_agent`
  4. `_load_teams`、`_load_ui_state`

**lastSessionId 更新机制**：
- `switch_session` / `new_session` 后，调用 `_update_last_session_id` 将当前 session.id 写入内存 config 并持久化到 `agent_config.json`
- `get_agent_config` 返回时仍会从运行时 agent.session 补充 lastSessionId（确保实时性）
- 后端重启时 `_load_one` 读取 `lastSessionId` 自动恢复上次会话
- 启动恢复使用 `asyncio.gather(..., return_exceptions=True)`：**单个 agent 启动失败不阻塞其他 agent**，仅记录 warning

**前端调用约定**：
- 创建 agent 后调 `start_agent`（默认行为，前端立即调）
- 用户主动 stop/start 时通过 `POST /agents/{name}/stop|start` 触发
- 应用重启后，前端可在加载时通过 `GET /agents` 看到哪些 agent 是 `started` 状态（运行时 `state` 字段反映当前是否在事件循环里）

### 12.6 Import APIs

`POST /api/skills/import`
- Body: `{"path": "/path/to/skills/folder"}`
- Scans subdirectories for `SKILL.md` files, imports via scan_skills
- Persists imported directory path for reload on restart
- Returns: `{"imported": N, "skills": [...]}`

`POST /api/mcps/import`
- Body: `{"path": "/path/to/mcp/configs/folder"}`
- Scans for `.json` files, parses as MCPServerConfig (supports single config, array, and `{"mcpServers": ...}` formats)
- Adds to `data/mcps/{name}.json` (individual file per MCP)
- Returns: `{"imported": N}`

`POST /api/prompts/import`
- Body: `{"path": "/path/to/prompts/folder"}`
- Scans for `.md` and `.txt` files, creates PromptConfig (name=filename, content=file content)
- Adds to `data/prompts/{id}.json` (individual file per prompt)
- Returns: `{"imported": N}`

### 12.7 Delete Agent with File Cleanup

`DELETE /api/agents/{name}?delete_files=true`

- `delete_files=false` (default): only removes agent from registry, keeps source files
- `delete_files=true`: also removes agent's `basePath` directory with `shutil.rmtree`

### 12.8 Name-Based Identity

AgentConfig/TeamConfig schemas: removed redundant `id` field. `name` is the sole identifier for agents and teams (`state_manager.agents` is `Dict[name, Agent]`, files stored at `data/agents/{name}/`).

### 12.9 Agent Storage Path Fix

`create_agent` now sets `base_dir=DATA_DIR / "agents"`, ensuring agent configs are saved to `data/agents/{name}/agent_config.yaml` instead of the project root.

### 12.10 Auto-Generated Agent Names

When `name` is empty in `POST /api/agents`, `CoreAgentConfig` is constructed without passing `name`, triggering the built-in dataclass default (`Agent_YYYY-MM-DD_HH-MM-SS_random8`). The response includes the generated name.

---

## 13. Recent Updates (2026-05-30)

### 13.1 Agent Lifecycle: `start()` Event-Loop Architecture

Refactored from `agent.run()` (one-shot per message) to `agent.start()` (persistent event loop):

- **StateManager** now manages agent lifecycle: `start_agent()` / `stop_agent()` / `start_all_agents()`
- Each agent runs as a long-lived `asyncio.Task`, consuming from an input queue
- FastAPI `lifespan` event auto-starts all loaded agents on boot
- Agent states: `Ready` / `Waiting` / `Running` / `Error`

### 13.2 AgentOutputDispatcher

`backend/dispatcher.py` — Per-agent fan-out output dispatcher:

- `agent.on_output(dispatcher.on_chunk)` registered at agent start
- Multiple WebSocket subscribers can subscribe to a single agent's output
- Chunks are broadcast to all subscriber `asyncio.Queue`s simultaneously

### 13.3 chat.py Rewrite

No longer uses `agent.run()` with `asyncio.Queue` for message passing:

- `receiver`: reads WebSocket messages, pushes `user_message` to `agent.input.push(content)`
- `forwarder`: subscribes to `AgentOutputDispatcher`, forwards chunks to WebSocket client
- Agent event loop autonomously processes messages from its input queue

### 13.4 New REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/agents/{name}/start` | Start agent event loop |
| POST | `/agents/{name}/stop` | Stop agent event loop |
| GET | `/agents/{name}/state` | Get agent state + session ID |
| GET | `/agents/{name}/sessions` | List all sessions |
| POST | `/agents/{name}/sessions/{id}/switch` | Switch to existing session |
| POST | `/agents/{name}/sessions/new` | Create new session |
| GET | `/agents/{name}/messages` | Load history messages |

### 13.5 Team Group Chat WebSocket

`backend/api/team_ws.py` — `WS /ws/team/{team_name}`:

- Subscribes to all member agents' dispatchers, merges output into single stream
- `source_agent` field added to identify which agent produced each chunk
- `@agent_name` mention routing with regex + explicit `mentions` array
- Frontend autocompletes mentions from team member list

### 13.6 Agent List Responses Include State

`GET /api/agents` and `GET /api/agents/{name}` now include runtime state fields:
- `state`: current agent state (`ready`/`waiting`/`running`/`error`)
- `currentSessionId`: active session UUID

---

## 14. Recent Updates (2026-06-01) — Startup Optimization

### 14.1 Lazy Tool Loading Architecture

Agent loading is now split into two phases:

**Phase 1 — Load (fast, parallel)**:
- YAML is parsed once (not twice), metadata extracted
- Only `Model` + `Session` are built
- Tools, skills, hooks, and timers are NOT built during load
- Multiple agents are loaded in parallel via `asyncio.to_thread()`
- Agents return in `Ready` state (gray dot in frontend)

**Phase 2 — Start (on-demand)**:
- When user clicks ▶, `start_agent()` triggers `_lazy_init_agent()` (one-shot)
- Built-in tools are built in parallel via `asyncio.to_thread()`
- MCP tools connect in parallel with 15s timeout per server
- Skills are loaded, hooks set up, timers registered
- Agent event loop starts after initialization

### 14.2 Parallel Loading

| Method | Before | After |
|--------|--------|-------|
| `_load_agents()` | Sequential `for` loop | `asyncio.gather(asyncio.to_thread(...))` for each agent |
| `_load_teams()` | Sequential `for` loop | `asyncio.gather(...)` for each team |
| `_lazy_init_agent()` tools | N/A (was in load) | `asyncio.gather(to_thread(builtin) + async(mcp))` |

### 14.3 Metadata Caches

New `StateManager` fields store metadata separate from Agent instances:

| Field | Purpose |
|-------|---------|
| `_agent_started: set[str]` | Tracks which agents have been lazy-initialized |
| `_agent_tool_metas: dict[str, list[dict]]` | Built-in tool configs (source + config) |
| `_agent_mcp_metas: dict[str, list[dict]]` | MCP tool configs (server + tool name) |
| `_agent_skill_metas: dict[str, list[dict]]` | Skill configs |
| `_agent_hook_metas: dict[str, list[dict]]` | Hook configs |
| `_agent_timer_metas: dict[str, list[dict]]` | Timer configs |

### 14.4 No Auto-Start on Boot

`start_all_agents()` is removed from `lifespan`. Agents load in `Ready` state and the user controls when to start each agent via the ▶ button.

### 14.5 `get_agent_config()` Reads from Cache

When an agent is not yet started (`agent.tools` is empty), `toolIds` and `skillIds` are read from the cached `_agent_configs`. This ensures the frontend always sees the correct tool/skill lists even before the agent is started.

- **Create**: Config is set from `config.toolIds` / `config.skillIds`
- **Update**: When `toolIds` or `skillIds` change, config is refreshed and `_started` is discarded (triggers rebuild on next start)
- **Delete**: All caches cleaned up for the deleted agent

---

## 15. Recent Updates (2026-06-01)

### 15.1 Persistent WebSocket Connection

Chat WebSocket endpoint changed from `/ws/chat/{agent_name}` to `/ws/chat`. The connection is established once and persists across agent tab switches. Frontend sends `{"type": "switch_agent", "agent_name": "..."}` to change which agent's output stream is subscribed to. This eliminates TCP reconnection overhead (~50-200ms) and prevents race conditions during rapid agent switching.

### 15.2 AgentOutputDispatcher Round Buffer

`AgentOutputDispatcher` maintains a round-level buffer (`_round_buffer`, capacity 500 entries / 500 KB). All chunks from the current agent turn are cached until a `completed_message`, `interrupted`, or `agent_state=error` chunk clears the buffer. `agent_state` chunks for `running`/`waiting`/`ready` do NOT clear the buffer — they are normal in-turn notifications. New subscribers using `subscribe(replay=True)` receive all buffered chunks before live chunks, ensuring that switching back to a streaming agent replays the in-progress round with full visual continuity.

### 15.3 Queue Switching via Sentinel

When `unsubscribe()` is called, a sentinel object (`_RESUBSCRIBE_SENTINEL`) is pushed to the subscriber's queue. The chat handler's forwarder detects this sentinel, continues its loop, and picks up the new queue reference (set by `subscribe_to` under `switch_lock`). This enables zero-delay queue switching without polling overhead.

### 15.4 Frontend Auto-Reconnect

`ChatWindow` now creates a single WebSocket on mount. On disconnect, it auto-reconnects with exponential backoff (1s → 2s → 4s → ... → 30s max) and re-sends `switch_agent` for the currently selected agent. `streamBufferRef` is reset on each agent switch and session switch to prevent cross-agent text contamination. Agent switch loads HTTP history first, then sends `switch_agent` to prevent replay chunks from being overwritten.

### 15.5 `get_agent_messages()` Field Alignment

Historical message loading now emits thinking as a separate `chunkType: "thinking"` entry and populates `tool_use` entries with serialized JSON `content`, matching the format used by WebSocket streaming chunks. This ensures `MessageBubble` renders history identically to live streaming messages.

---

## 16. Recent Updates (2026-06-02)

### 16.1 `Session.fork(at=N)` 支持按 turn 切片复制

`Session.fork` 新增 `at: int` 参数，允许从指定 turn 索引处复制（含该 turn）。这是 core 库对会话分支能力的扩展，源于"从一个不确定的中间状态分叉探索"的需求（如回退实验、A/B 对比）。

**签名变化**：
```python
def fork(self, session_root: str | Path = None, at: int = None) -> 'Session'
```

**行为约定**：
- `at=None`（默认）→ 复制所有 turn，向后兼容旧调用
- `at=N`（N ≥ 0）→ 复制 `turns[0..N]`（共 N+1 个 turn）
- `at=-1` → 等价于全复制；负数索引沿用 `get_turn` 的归一化风格
- `at` 越界（正/负）→ 抛 `IndexError`
- 空 session 调 `at` → 抛 `IndexError`
- 纯内存 session（`dir=None`）→ 抛 `ValueError`（与原 fork 一致）

**元数据延续策略**（与原 fork 的"原样继承"不同，**全部按复制范围重算**）：

| 字段 | 策略 | 原因 |
|---|---|---|
| `window_start` | 置 0 | fork 是一个新起点；后续压缩流程会根据可见 turns 重新计算 |
| `compress_turn_count` | 按 `turn.is_summarized` 重新计数 | 复制范围变了，统计口径必须跟着变 |
| `total_input_cost_tokens` | 从复制范围内 `ModelMessage.input_tokens` 重新累加 | 同上，避免继承原 session 的全部费用 |
| `total_output_cost_tokens` | 从复制范围内 `ModelMessage.output_tokens` 重新累加 | 同上 |

**ID 命名约定**：
- 旧：`{原ID}_fork_{timestamp}_{uuid8}`
- 新：`{原ID}_fork_at{N}_{timestamp}_{uuid8}`（指定 `at` 时）
- 目的：路径名一眼可见 fork 血缘 + 复制位置

**落盘策略**（不变）：仅 flush `is_complete` 的 turn，未完成 turn 在内存中保留以便继续对话；最后调用 `_write_metadata()` 写 `<id>.md`。

**典型用法**：
```python
branch = session.fork(at=2)            # 复制前 3 个 turn
branch = session.fork(at=-1)           # 复制全部
branch = session.fork(at=2, session_root="./experiments")
```

---

## 17. Recent Updates (2026-06-03) — MCP Tool 字段重构

### 17.1 背景

`ToolConfig` 旧字段 `id` + `name`(raw) + `isMcp` + `mcpServerName` 与 core `MCPTool`（`mcp_server_name` + `raw_name` + 拼接的 `func_name`）字段语义错位，且 backend 旧代码用 `getattr(t, '_mcp_tool_name', '')` 引用了不存在的属性，导致 per-Agent 工具匹配恒为假。同步收敛三个层（core / backend / frontend）的字段命名。

### 17.2 ToolConfig 新字段

```python
class ToolConfig(BaseModel):
    name: str                  # 复合名 'mcp:{server}::{raw}'，与 core MCPTool.func_name 对齐
    rawName: str               # 工具在 MCP server 上的原始名（前端展示/回传 server）
    description: str
    inputSchema: dict
    mcpServerName: str | None  # 非空即为 MCP 工具（替代旧的 isMcp bool）
```

- 删：`id`（与 `name` 重复，React key 可用 `name`）、`isMcp`（可由 `mcpServerName != null` 派生）
- 增：`rawName`

### 17.3 Agent `toolIds` 格式

旧：`mcp:{server}:{raw}`（`:` 同时做前缀和分隔，扩展性差）
新：`mcp:{server}::{raw}`（`::` 作为 server 与 raw 之间的分隔符）

为什么是 `::` 而不是 `_`：
- server/raw 名都可能含 `_`，用 `_` 切分会歧义
- `::` 在标识符中几乎不出现，parse 用 `split("::", 1)` 即可，O(1) 无歧义

### 17.4 `_parse_mcp_tool_ref` 改造

```python
@staticmethod
def _parse_mcp_tool_ref(name: str) -> tuple[str, str | None]:
    if not name.startswith("mcp:"):
        return ("", None)
    body = name[len("mcp:"):]
    if "::" in body:
        server, tool = body.split("::", 1)
        return (server, tool or None)
    # Legacy: 'mcp:{serverName}' 加载该 server 全部工具
    return (body, None)
```

### 17.5 副作用修复

- 修复 backend `getattr(t, '_mcp_tool_name', '')` 恒为空的 bug → 改为 `t.raw_name`
- 修复 `MCPTool.func_name` 从 `{server}_{raw}` 改为 `mcp:{server}::{raw}`，与 LLM schema 对齐
- `data/mcps/*.json` 旧格式不迁移，下次 discover 自动重写

### 17.6 前端 UI 变化

- `MCPsModule` env 输入：textarea → 默认 3 行 KEY+VALUE 输入 + "Add" 按钮
- args 输入：保持空格分隔不变
- 工具展示：用 `tool.rawName` 替代 `tool.name`，用 `tool.name` 作 React key
- `AgentConfigDialog` 筛选：`!t.isMcp` / `t.isMcp` → `!t.mcpServerName` / `!!t.mcpServerName`

---

## 18. Unified ID & Entity Lifecycle（v2，2026-06）

> 配套设计文档：[`issue/unified-id-design.md`](../issue/unified-id-design.md)

### 18.1 目标与原则

- 所有持久化配置项分配一个全局唯一 UUID 作为机器身份
- `name` 退化为展示名，可重名，仅用于 UI
- 磁盘路径以 ID 为目录，name 仅作文件名后缀
- `ToolConfig` 是蓝图（持久化），`Tool` 实例是 per-agent 瞬态对象
- MCP 客户端 per-agent 隔离，不跨 agent 共享
- `toolIds` 允许自由增删；不向后兼容旧数据

### 18.2 Schema 变化（`backend/schemas.py`）

```python
class ToolConfig(BaseModel):
    id: str                              # template_id (UUID)
    name: str                            # builtin shortName / mcp rawName
    source: Literal["built_in", "hook", "mcp", "team"]
    description: str
    inputSchema: dict
    mcpServerId: str | None = None       # only for mcp source

class SkillConfig(BaseModel):
    id: str
    name: str
    ...

class MCPServerConfig(BaseModel):
    id: str
    name: str
    ...
    tools: list[ToolConfig]

class AgentConfig(BaseModel):
    id: str = ""                         # backend-generated UUID
    name: str                            # display name
    ...
    toolIds: list[str] = Field(...)    # stores ToolConfig.id list
    skillIds: list[str] = Field(...)   # stores SkillConfig.id list

class TeamConfig(BaseModel):
    id: str = ""
    name: str
    teamDescription: str = ""
    workingDir: str = ""
    memberIds: list[str] = []
    contacts: dict[str, dict[str, str]] = {}
    # state 由 API 层手动注入（运行时状态，非配置）

class CreateTeamRequest(BaseModel):
    """Frontend-facing team creation payload (team config + member configs)."""
    name: str
    teamDescription: str = ""
    workingDir: str = ""
    members: list[AgentConfig] = []
    contacts: dict[str, dict[str, str]] = {}  # {agentName: {otherName: role}}，不含 self-key

class UIState(BaseModel):
    currentTab: Literal["agent", "team"] = "agent"
    currentAgentId: str | None = None    # was currentAgentName
    currentTeamId: str | None = None     # was currentTeamName
```

### 18.3 持久化布局

```
data/
├── agents/
│   └── {agent_id}/                     # 目录走 ID
│       └── {name}/                     # 兼容 core Agent 的 base_dir
│           ├── agent_config.yaml       # 含 id 字段
│           └── session/...
├── teams/{team_id}/{name}/team_config.yaml
├── models/{id}.json
├── prompts/{id}.json
├── skills/skills.json                  # 仍在 skills 下
└── mcps/{id}.json                      # 文件名走 id
```

### 18.4 StateManager 字段（`backend/state.py`）

```python
# 主索引
self.mcp_servers: Dict[str, MCPServerConfig]      # key = id
self.prompts: Dict[str, PromptConfig]              # key = id
self.agents: Dict[str, Agent]                      # key = name (legacy)
self.teams: Dict[str, AgentTeam]                   # key = name (legacy)
self._mcp_servers_by_name: Dict[str, str]          # name -> id

# 稳定 id 索引
self._agent_ids: Dict[str, str]                    # name -> id

# Template registry
self._tool_configs: Dict[str, SchemaToolConfig]    # template_id -> config

# Per-agent runtime pools (lazy, not persisted)
self._agent_tool_instances: Dict[str, Dict[str, Tool]]
self._agent_mcp_clients: Dict[str, Dict[str, MCPClient]]
```

### 18.5 关键方法（`backend/state.py`）

- `_next_id()`：生成 UUID4 字符串
- `_mcp_tool_id(mcp_server_id, raw_name)`：`uuid5` 派生稳定的 MCP tool id
- `_load_builtin_tool_templates()`：启动时填充 builtin tool 的 `_tool_configs`
- `_register_mcp_tool_templates(mcp_cfg)`：MCP server 添加/更新时把其 tools 同步到 `_tool_configs`
- `get_agent_id(name)` / `get_agent_by_id(agent_id)` / `get_agent_name_by_id(agent_id)`：id ↔ name 互查
- `get_team_id(name)` / `get_team_by_id(team_id)`
- `get_mcp_id(name)` / `get_mcp_by_name(name)`
- `_build_tool_metas(tool_names)`：把 template_id 列表分类为 builtin/mcp metas（fallback 兼容 legacy composite）
- `_discover_mcp_tools(name)`：写入新格式（id, source, mcpServerId）并注册到 `_tool_configs`

### 18.5.1 ToolFactory 与 MCPFactory 初始化解耦

`ToolFactory.load()` 从磁盘加载 ToolConfig 时跳过 `source="mcp"` 的条目，MCP 工具统一由 `MCPFactory.load()` 通过 `ToolFactory.on_mcp_added()` 注册，避免双重注册和数据不一致。

`ToolFactory.on_mcp_added()` 使用传入 ToolConfig 的 `t.id` 而非重新计算，并通过 `assert t.id == _mcp_tool_id(mcp_id, t.name)` 校验 id 一致性，防止静默覆盖。

### 18.6 builtin tool UUID

`BBagent/built_in_tool/__init__.py` 中 hardcode：

```python
BUILTIN_TOOL_IDS = {
    "read":      "4c48a29c-a52a-4ec7-b7d7-d265316091c7",
    "write":     "20c41591-9b4e-4ff0-9182-f11db46fef41",
    "edit":      "2d35e797-d8f7-41cf-aa12-e439ec74230b",
    "bash":      "5a40e5e1-6931-4126-b142-581379f4f2eb",
    "find":      "023a166d-246b-4aeb-be56-3119210b9bba",
    "grep":      "4dc7319f-7ff7-484b-aa19-c39fa5efa772",
    "ls":        "20ae9084-3a2c-413b-bdbb-86f04fb9fdd3",
    "sub_agent": "5596651c-ee17-4ad4-ae79-7ed73e6dad29",
}
```

新加的 `get_builtin_tool_configs()` 在启动时填充 builtin template 列表；`build_builtin_tool(template_id, policy)` 给出 per-agent 实例的构造函数（policy 仅影响 builtin tool）。

### 18.7 MCP tool ID 派生

MCP tool id = `uuid5(_MCP_TOOL_NS, f"{mcp_server_id}::{raw_name}")`，namespace 固定为 `5b3a6e29-2c47-4b71-8c5b-3b0c8f7d2e91`。同一对 `(server_id, raw_name)` 跨进程稳定。

### 18.8 API 变化

所有 agent / team / mcp URL 改用 id；后端 `_resolve_agent` / `_resolve_team` / `_resolve_mcp` 接受 id 或 name（name 作为 fallback，简化过渡）：

| 旧 | 新 |
|---|---|
| `GET /api/agents/{name}` | `GET /api/agents/{id}` |
| `PUT /api/agents/{name}` | `PUT /api/agents/{id}` |
| `POST /api/agents/{name}/start` | `POST /api/agents/{id}/start` |
| `GET /api/teams/{name}` | `GET /api/teams/{id}` |
| `PUT /api/mcps/{name}` | `PUT /api/mcps/{id}` |

### 18.9 与 v1 ToolConfig 的兼容

旧 `ToolConfig`（name=composite + rawName + mcpServerName）已被弃用。`get_agent_config()` 现在把 core Tool 映射回 `template_id`：

- builtin `bash` → `5a40e5e1-...`
- MCP `t.raw_name` 在 `mcp_server_id` 下 → `uuid5(...)`

### 18.10 已知未完成项

> v1 留下的待办项目已在 v2 实施中收尾。下列条目全部完成：

- ✅ `update_agent` 收到 `toolIds` 时不仅更新 config，还 diff 出 added/removed 并通过 `_build_tool` / `agent.remove_tools` 重建实例池
- ✅ `start_agent` 调用 `_collect_missing_tool_template_ids`，对失效 id 抛 `TOOLCONFIG_NOT_FOUND`（status 400，detail.missingTemplateIds）
- ✅ `_build_tool_for_agent(name, template_id, policy)` / `_get_mcp_client(name, mcp_server_id)` / `_close_agent_runtime(name)` 在 `_lazy_init_agent` / `stop_agent` / `delete_agent` 中均已调用
- ✅ `MCPClient` 池（per-agent 隔离）已通过 `_agent_mcp_clients` + `_get_mcp_client` 在 `_lazy_init_agent` 中接入；`delete_agent` / `stop_agent` 通过 `_close_agent_runtime` 关掉所有 client
- ✅ WebSocket 路由 `/ws/team/{ref}` 和 `/ws/chat` 都接受 id 或 name；chat 的 `switch_agent` 消息携带 `agent_id` 优先 + `agent_name` 兜底
- ✅ 测试 fixture 迁移：`test/integration/test_agent_creation_api.py` 中 `toolIds` 改为 `BUILTIN_TOOL_IDS[...]` 列表
- ✅ 前端 React key 统一：`SkillsModule` / `MCPsModule` / `AgentTabs` 的列表 key 改为 `id || name`；`MCPsModule` 的 `tool.rawName` 兜底已去除（统一用 `tool.name`）；`ChatWindow` 的 `switch_agent` 消息加 `agent_id` 字段；`TeamChatWindow` 把 `team.id` 传给 WS 路径

---

## 19. Recent Updates (2026-06-05) — Skill 增删补全

### 19.1 问题

`AgentFactory.update()` 处理 `skillIds` 变更时只实现了**新增** skill 的逻辑，缺少**移除** skill 的处理。当用户在前端减少 agent 的 skill 时，`_agent_configs` 中的 `skillIds` 会更新，但运行时 `agent.skills` 字典和 `skill_prompt` 不会同步移除，导致 agent 仍然能访问已被移除的 skill。

### 19.2 修复

1. **`Agent.remove_skills(skill_names: List[str])`**：在 `BBagent/core/agent.py` 的 `Agent` 类和 `SubAgent` 类中新增方法，从 `self.skills` 字典中移除指定名称的 skill，并刷新 `skill_prompt`。当所有 skill 被移除时，`skill_prompt` 置空。

2. **`AgentFactory.update()` skillIds diff 逻辑**：参照 `toolIds` 的 added/removed diff 模式，补全 skill 的移除逻辑：
   - 计算新增 skill 列表 → `agent.add_skills()`
   - 计算移除 skill 名称列表 → `agent.remove_skills()`

## 8. 全局 Session 管理

### 8.1 架构

```
Frontend (Session Manager UI)
    │ REST API
    ▼
backend/api/sessions.py
    │
    ▼
backend/state.py (代理方法)
    │
    ▼
backend/factories/session_factory.py
    SessionManager（全局管理类）
    - 索引构建、LRU 缓存、fork 操作
    │
    ▼
BBagent/core/message.py
    Session / Turn（扩展：parent_session_id / fork_turn_index）
```

### 8.2 SessionIndex

轻量索引数据结构，不包含完整消息数据，仅用于列表展示和路由：

```python
@dataclass
class SessionIndex:
    session_id: str
    agent_id: str
    agent_name: str
    timestamp: str
    turn_count: int
    is_active: bool
    parent_session_id: str
    fork_turn_index: int
    session_dir: str
```

### 8.3 SessionManager 核心方法

| 方法 | 说明 |
|------|------|
| `build_index()` | 启动时全量扫描所有 agent 的 session 目录构建索引 |
| `list_sessions(agent_id?)` | 全局或按 agent 过滤的 session 列表 |
| `get_session_detail(session_id)` | session 详情 + turn 摘要列表 |
| `fork_at_turn(session_id, turn_index, target_agent_id?)` | 从指定 turn 位置 fork |
| `delete_session(session_id)` | 删除 session（含文件清理） |
| `refresh_agent_index(agent_id)` | agent session 变化后增量刷新索引 |
| `_load_session(session_id)` | 带 LRU 缓存的异步加载（run_in_executor） |

### 8.4 Session 类扩展

在 `BBagent/core/message.py` 的 Session 类中新增：

- `parent_session_id: str` — fork 来源 session 的 ID
- `fork_turn_index: int` — fork 发生在源 session 的哪个 turn 位置

元数据文件 `.md` 中追加写入这两个字段，`load()` 时读取恢复。

### 8.5 Session ID 生成

Session ID 格式：`{timestamp}_{uuid4().hex[:16]}`，16 位十六进制随机数（64 bit），全局碰撞概率可忽略。

### 8.6 性能策略

| 场景 | 策略 |
|------|------|
| 全局 session 列表 | 只读 SessionIndex，不加载 Session 对象 |
| 展开 session turns | 按需加载 Session，LRU 缓存（容量 20） |
| fork 操作 | 加载源 session → fork → 写入 → 缓存新 session |
| 索引构建 | 启动时扫描所有 `.md` 元数据文件 |
| 索引更新 | agent session 变化时增量刷新该 agent 的索引 |
| Session 加载 | `run_in_executor` 避免阻塞事件循环 |

### 8.7 AgentFactory 联动

| AgentFactory 操作 | SessionManager 联动 |
|---|---|
| `create()` | `_refresh_session_index(agent_id)` |
| `new_session()` | `_refresh_session_index(agent_id)` |
| `switch_session()` | `_refresh_session_index(agent_id)` |
| `delete()` | `_remove_session_index(agent_id)` |

