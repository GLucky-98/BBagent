# BBagent Backend Design Documentation v7

## 1. Overview

BBagent Backend 是基于 FastAPI 的异步 Web 服务，为前端 SPA 提供 REST API 和 WebSocket 接口。

本版本（v7）的核心架构变更：
- **State 协调器**：`State` 单例替代旧的 `StateManager`，按依赖顺序初始化各 Factory 并委托所有 CRUD 操作
- **Factory 分层**：每个资源类型有独立 Factory（Model、Prompt、Skill、Tool、MCP、Agent、Team、Session），Factory 间通过注入引用协作
- **AgentOutputDispatcher**：全局 dispatcher 用于跨 Agent 状态事件广播，每个 Agent 也有自己的 dispatcher
- **SessionManager**：全局 Session 索引、缓存、Fork 操作，LRU 缓存避免重复加载
- **TeamConversationManager**：Team 级别的对话持久化和加载
- **Unified ID 设计**：所有资源（Agent、Team、MCP、Skill、Tool）使用 UUID 作为机器标识，`name` 仅作显示名
- **File Watch WebSocket**：基于 watchdog 的实时文件变化推送
- **错误处理**：结构化 `AppError` 体系，全局异常处理器

> **最后更新**：2026-06-15 — 重构文档对齐当前代码库

---

## 2. Project Structure

```
backend/
├── __init__.py
├── main.py                          # FastAPI app 入口，lifespan，CORS，SPA 静态文件
├── state.py                         # State 协调器单例
├── schemas.py                       # Pydantic 模型（API 请求/响应）
├── errors.py                        # AppError 体系 + 全局异常处理器
├── dispatcher.py                    # AgentOutputDispatcher（fan-out + replay）
├── logging.py                       # 日志配置
├── api/                             # API 路由层
│   ├── __init__.py                  # api_router 注册所有子路由
│   ├── agents.py                    # Agent CRUD + lifecycle
│   ├── chat.py                      # Chat WebSocket
│   ├── file_watch.py                # File Watch WebSocket
│   ├── files.py                     # 文件系统操作
│   ├── hooks.py                     # Hook 描述符列表
│   ├── mcps.py                      # MCP Server CRUD + discover
│   ├── models.py                    # Model CRUD + test
│   ├── prompts.py                   # Prompt CRUD + import
│   ├── sessions.py                  # 全局 Session 管理
│   ├── skills.py                    # Skill import + delete + refresh
│   ├── state.py                     # UI State 持久化
│   ├── team_ws.py                   # Team Chat WebSocket
│   ├── teams.py                     # Team CRUD + lifecycle
│   └── tools.py                     # Tool 列表
├── factories/                       # Factory 层
│   ├── __init__.py                  # _next_id(), _builtin_tool_id() 工具函数
│   ├── agent_factory.py             # Agent CRUD + lifecycle + dispatcher
│   ├── mcp_factory.py               # MCP Server CRUD + discover
│   ├── model_factory.py             # Model CRUD + 缓存 + 热更新
│   ├── prompt_factory.py            # Prompt CRUD + import
│   ├── session_factory.py           # SessionManager（全局索引 + fork + LRU 缓存）
│   ├── skill_factory.py             # Skill import + delete + refresh
│   ├── team_conversation_factory.py # TeamConversationManager
│   ├── team_factory.py              # Team CRUD + lifecycle
│   └── tool_factory.py              # Tool 蓝图管理
```

---

## 3. State Coordinator

### 3.1 State 单例

**文件**：`backend/state.py`

`State` 是全局协调器单例，拥有所有 Factory 实例，提供 API 层使用的公共接口。

```python
class State:
    _instance: Optional["State"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
```

### 3.2 Factory 初始化顺序

按依赖关系分阶段初始化：

```
阶段 1（并行）: ModelFactory, PromptFactory, SkillFactory, ToolFactory
阶段 2（并行）: MCPFactory（依赖 ToolFactory）, AgentFactory（依赖 Model/Tool/Skill/MCP）
阶段 3（并行）: AgentFactory.start_persisted_agents(), TeamFactory.load()
阶段 4:         SessionManager.build_index()
阶段 5:         UI State 加载
```

```python
async def load_all(self):
    # 1. No-dependency factories — parallel
    await asyncio.gather(
        loop.run_in_executor(None, self.model_factory.load),
        loop.run_in_executor(None, self.prompt_factory.load),
        loop.run_in_executor(None, self.skill_factory.load),
        loop.run_in_executor(None, self.tool_factory.load),
    )
    # 2. MCPFactory + AgentFactory — parallel
    await asyncio.gather(self.mcp_factory.load(), self.agent_factory.load())
    # 3. Start persisted agents + load teams — parallel
    await asyncio.gather(self.agent_factory.start_persisted_agents(), self.team_factory.load())
    # 4. Build global session index
    self.session_manager = SessionManager(self.agent_factory)
    self.session_manager.build_index()
    # 5. UI state
    self._load_ui_state()
```

### 3.3 跨切面协调

State 处理跨 Factory 的协调逻辑：

- **Model 更新 → Agent 热更新**：`update_model_and_invalidate()` 更新 ModelConfig 后，对使用该 model 的所有 running agent 执行 `change_model()`
- **Model 删除 → Agent 停止**：`delete_model_and_invalidate()` 先停止受影响 agent，再删除 model
- **MCP 删除 → Tool 清理**：MCPFactory 内部处理 tool 清理
- **Agent Session 切换 → Team Conversation 检查**：`_assert_agent_session_mutation_allowed()` 防止在 Team 对话锁定时切换 session

### 3.4 全局实例

```python
# backend/state.py 末尾
state_manager = State()
```

所有 API 路由通过 `from backend.state import state_manager` 访问。

---

## 4. Schemas

**文件**：`backend/schemas.py`

所有 Pydantic 模型用于 API 请求/响应验证。

### 4.1 ModelConfig

```python
class ModelConfig(BaseModel):
    id: str
    name: str
    provider: Literal["anthropic", "openai"]
    modelName: str
    apiKey: str = ""
    baseUrl: str
    maxContextTokens: int
    maxCompletionTokens: int
    temperature: float = 1.0
    topP: float = 1.0
    thinking: bool = True              # bool，非 dict
```

`core_dict` 属性转换为 `Model.from_config_dict()` 所需格式。

### 4.2 ToolConfig

```python
class ToolConfig(BaseModel):
    id: str                            # UUID (template_id)
    name: str                          # 显示名
    source: Literal["built_in", "hook", "mcp", "team"] = "built_in"
    description: str = ""
    mcpServerId: str | None = None     # 仅 MCP 工具
```

### 4.3 AgentConfig

```python
class AgentConfig(BaseModel):
    id: str = ""                       # UUID，后端生成
    name: str                          # 显示名
    modelId: str
    systemPrompt: str = ""
    workingDir: str = ""               # 映射到 toolPolicy.cwd
    baseDir: str = ""                  # 后端自动生成，前端只读
    toolIds: list[str] = []            # ToolConfig.id (UUID) 列表
    skillIds: list[str] = []           # SkillConfig.id (UUID) 列表
    toolPolicy: dict = {}
    hookNames: list[str] = []
    hookConfig: dict = {}
    timers: list[TimerConfig] = []
    lastSessionId: str = ""
```

字段三组分类：
- **Basic**：`name`, `modelId`, `systemPrompt`, `workingDir`
- **Tools**：`toolIds`, `skillIds`, `toolPolicy`
- **Hooks**：`hookNames`, `hookConfig`

### 4.4 TeamConfig

```python
class TeamConfig(BaseModel):
    id: str = ""
    name: str
    teamDescription: str = ""
    workingDir: str = ""
    baseDir: str = ""
    memberIds: list[str] = []
    contacts: dict[str, dict[str, str]] = {}
    started: bool = False
```

### 4.5 CreateTeamRequest

```python
class CreateTeamRequest(BaseModel):
    name: str
    teamDescription: str = ""
    workingDir: str = ""
    members: list[AgentConfig] = []
    contacts: dict[str, dict[str, str]] = {}
```

### 4.6 其他 Schema

| Schema | 用途 |
|--------|------|
| `SkillConfig` | Skill 蓝图（id, name, description, path） |
| `MCPServerConfig` | MCP 服务器配置（id, name, command, args, env, tools） |
| `PromptConfig` | Prompt 配置（id, name, content, group） |
| `TimerConfig` | 定时器配置（name, seconds: float, hint, enabled） |
| `FileNode` | 文件树节点（name, path, type, children, size, extension, modifiedAt） |
| `UIState` | 前端 UI 状态持久化（currentAgentId, currentTeamId, settingsOpen 等） |
| `ChatMessage` | 聊天消息（type: user_message | system_event, content） |
| `ModelTestRequest` | 模型测试请求（prompt） |
| `SessionForkRequest` | Session fork 请求（turnIndex, targetAgentId） |
| `HookDescriptor` / `HookListResponse` | Hook 描述符（用于 GET /api/hooks） |
| `AgentSummary` | Agent 摘要（id, name, type, modelId, state, hookEnabled） |
| `MessageItem` | 消息项（id, role, content, timestamp） |

---

## 5. Error Handling

**文件**：`backend/errors.py`

### 5.1 AppError 体系

```python
class ErrorCode(str, Enum):
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    AGENT_ALREADY_EXISTS = "AGENT_ALREADY_EXISTS"
    AGENT_ALREADY_RUNNING = "AGENT_ALREADY_RUNNING"
    AGENT_NOT_RUNNING = "AGENT_NOT_RUNNING"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    TEAM_NOT_FOUND = "TEAM_NOT_FOUND"
    MCP_NOT_FOUND = "MCP_NOT_FOUND"
    SKILL_NOT_FOUND = "SKILL_NOT_FOUND"
    PROMPT_NOT_FOUND = "PROMPT_NOT_FOUND"
    AGENT_CREATE_FAILED = "AGENT_CREATE_FAILED"
    AGENT_START_FAILED = "AGENT_START_FAILED"
    AGENT_STOP_FAILED = "AGENT_STOP_FAILED"
    TEAM_START_FAILED = "TEAM_START_FAILED"
    TEAM_STOP_FAILED = "TEAM_STOP_FAILED"
    TEAM_CONVERSATION_LOCKED = "TEAM_CONVERSATION_LOCKED"
    SESSION_SWITCH_FAILED = "SESSION_SWITCH_FAILED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    TOOLCONFIG_NOT_FOUND = "TOOLCONFIG_NOT_FOUND"
    TOOLCONFIG_INVALID = "TOOLCONFIG_INVALID"

class AppError(Exception):
    code: ErrorCode
    message: str
    status_code: int
    detail: str

class NotFoundError(AppError):    # status_code=404
class ConflictError(AppError):    # status_code=409
```

### 5.2 全局异常处理器

```python
# main.py
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
```

错误响应格式：

```json
{
  "error": {
    "code": "AGENT_NOT_FOUND",
    "message": "Agent 'xxx' not found",
    "detail": "..."  // 可选
  }
}
```

---

## 6. AgentOutputDispatcher

**文件**：`backend/dispatcher.py`

Fan-out 消息分发器，支持 replay buffer。

### 6.1 核心机制

```python
class AgentOutputDispatcher:
    def __init__(self, replay_buffer: bool = True):
        self._subscribers: dict[str, asyncio.Queue] = {}
        self._round_buffer: list[dict] = []       # 当前 turn 的 chunk 缓存
        self._replay_buffer = replay_buffer
```

- **on_chunk(chunk)**：序列化 dataclass → dict，缓存到 round buffer，广播给所有 subscriber
- **subscribe(id, replay)**：创建 asyncio.Queue，可选 replay 当前 buffer
- **unsubscribe(id)**：移除 subscriber

### 6.2 Round Buffer 策略

- 每个 turn 的 chunk 持续累积到 `_round_buffer`
- 仅在 turn 完全结束（`completed_message` + `stop_reason=end_turn`）或中断（`interrupted`、`agent_state=error`）时清空
- 新 subscriber 可通过 `replay=True` 获取当前 turn 的所有已发送 chunk

### 6.3 两种 Dispatcher 实例

| 实例 | 位置 | replay_buffer | 用途 |
|------|------|--------------|------|
| Per-Agent | `AgentFactory._dispatchers[agent_id]` | True | Chat WS 订阅，支持 replay |
| Global | `State.global_dispatcher` | False | 跨 Agent 状态事件广播 |

---

## 7. Factory Details

### 7.1 AgentFactory

**文件**：`backend/factories/agent_factory.py`

**职责**：Agent CRUD、生命周期管理、per-agent runtime state。

**核心数据结构**：
- `agents: dict[str, Agent]` — agent_id → Agent 实例
- `_agent_configs: dict[str, AgentConfig]` — agent_id → 配置
- `_dispatchers: dict[str, AgentOutputDispatcher]` — agent_id → dispatcher
- `_model_ids: dict[str, str]` — agent_id → model_id
- `_tasks: dict[str, asyncio.Task]` — agent_id → 后台任务
- `_mcp_clients: dict[str, dict[str, MCPClient]]` — agent_id → {mcp_id → client}
- `_tool_instances: dict[str, list[Tool]]` — agent_id → tool 实例列表
- `_hook_states: dict[str, dict]` — agent_id → hook 状态

**Policy 字段映射**：前端 camelCase → 后端 snake_case

```python
_POLICY_FIELD_MAP = {
    "maxReadSize": "max_read_size",
    "bashMaxOutputSize": "bash_max_output_size",
    "bashDefaultTimeout": "bash_default_timeout",
    "webTimeout": "web_timeout",
    "webMaxResponseSize": "web_max_response_size",
    "webMaxOutputSize": "web_max_output_size",
    "webSearchMaxResults": "web_search_max_results",
    "webAllowedDomains": "web_allowed_domains",
    "webUserAgent": "web_user_agent",
    "subAgentModel": "sub_agent_model",
    "subAgentBlockedTools": "sub_agent_blocked_tools",
}
```

**生命周期**：
- `create(config)` → 创建 Agent + 保存配置 + 启动
- `start(agent_id)` → 启动 Agent 事件循环（后台 asyncio.Task）
- `stop(agent_id)` → 停止事件循环 + 保存 session
- `delete(agent_id)` → 停止 + 清理文件 + 移除内存
- `start_persisted_agents()` → 启动时恢复所有持久化的 auto-start agent

**Session 管理**：
- `switch_session(agent_id, session_id)` — 切换 session（受 Team Conversation 锁定检查）
- `new_session(agent_id)` — 创建新 session
- `get_sessions(agent_id)` — 获取 session 列表
- `get_messages(agent_id)` — 获取当前 session 消息

### 7.2 ModelFactory

**文件**：`backend/factories/model_factory.py`

**职责**：Model CRUD + 缓存 + 热更新。

- `load()` — 从 `data/models/` 加载所有 ModelConfig
- `acquire(model_id)` — 获取 Model 实例（带缓存）
- `invalidate(model_id)` — 清除缓存，下次 acquire 重新构建
- `add(config)` / `update(model_id, updates)` / `delete(model_id)` — CRUD

### 7.3 MCPFactory

**文件**：`backend/factories/mcp_factory.py`

**职责**：MCP Server CRUD + tool discover。

- `load()` — 从 `data/mcps/` 加载所有 MCPServerConfig
- `add(config)` — 创建 MCP 服务器 + 自动 discover tools
- `discover_tools_by_id(mcp_id)` — 重新 discover tools
- `delete(mcp_id)` — 删除 MCP + 清理关联 tools

### 7.4 TeamFactory

**文件**：`backend/factories/team_factory.py`

**职责**：Team CRUD + lifecycle。

- `load()` — 从 `data/teams/` 加载所有 Team
- `create(config, member_configs)` — 创建 Team + 成员 Agent
- `update(team_id, updates)` — 更新 Team 配置（含成员增删）
- `start(team_id)` / `stop(team_id)` — 启动/停止 Team
- `is_started(team_id)` / `get_state(team_id)` — 状态查询

**Team 数据目录结构**：
```
data/teams/{team_id}/{team_name}/
├── team_config.json
└── conversations/
    ├── index.json
    └── {conversation_id}/
        ├── meta.json
        └── messages.jsonl
```

### 7.5 SessionManager

**文件**：`backend/factories/session_factory.py`

**职责**：全局 Session 索引、缓存、Fork 操作。

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

**核心方法**：
- `build_index()` — 扫描所有 agent 的 session 目录构建索引
- `list_sessions(agent_id)` — 全局 session 列表，支持按 agent 过滤
- `get_session_detail(session_id)` — session 详情 + turn 摘要
- `fork_at_turn(session_id, turn_index, target_agent_id)` — 从指定 turn fork session
- `delete_session(session_id)` — 删除 session（含文件清理）
- LRU 缓存（capacity=20）避免重复加载 Session 对象

### 7.6 TeamConversationManager

**文件**：`backend/factories/team_conversation_factory.py`

**职责**：Team 级别对话的持久化和加载。

**核心方法**：
- `ensure_loaded(team_id, team)` — 确保至少一个 conversation 存在并加载
- `list_conversations(team)` — 列出 Team 的所有对话
- `create_conversation(team, name)` — 创建新对话（为每个成员创建新 session）
- `load_conversation(team, conversation_id)` — 加载指定对话
- `delete_conversation(team, conversation_id)` — 删除对话
- `assert_member_session_switch_allowed(team, agent_id)` — 检查成员是否允许切换 session

### 7.7 其他 Factory

| Factory | 文件 | 职责 |
|---------|------|------|
| `PromptFactory` | `prompt_factory.py` | Prompt CRUD + 文件夹导入 |
| `SkillFactory` | `skill_factory.py` | Skill 导入 + 删除 + 刷新 |
| `ToolFactory` | `tool_factory.py` | Tool 蓝图管理（builtin + MCP tools） |

---

## 8. API Router Registration

**文件**：`backend/api/__init__.py`

```python
api_router = APIRouter()
api_router.include_router(models.router,    prefix="/models",    tags=["models"])
api_router.include_router(mcps.router,      prefix="/mcps",      tags=["mcps"])
api_router.include_router(prompts.router,   prefix="/prompts",   tags=["prompts"])
api_router.include_router(skills.router,    prefix="/skills",    tags=["skills"])
api_router.include_router(agents.router,    prefix="/agents",    tags=["agents"])
api_router.include_router(teams.router,     prefix="/teams",     tags=["teams"])
api_router.include_router(chat.router,      prefix="/ws",        tags=["chat"])
api_router.include_router(file_watch.router, prefix="/ws",       tags=["file_watch"])
api_router.include_router(team_ws.router,   prefix="/ws",        tags=["team_chat"])
api_router.include_router(files.router,     prefix="/files",     tags=["files"])
api_router.include_router(state.router,     prefix="/state",     tags=["state"])
api_router.include_router(tools.router,     prefix="/tools",     tags=["tools"])
api_router.include_router(hooks.router,     prefix="/hooks",     tags=["hooks"])
api_router.include_router(sessions.router,  prefix="/sessions",  tags=["sessions"])
```

---

## 9. WebSocket Handlers

### 9.1 Chat WebSocket

**文件**：`backend/api/chat.py`

**路径**：`WS /api/ws/chat`

**协议**：
- 前端 → 后端：`switch_agent`, `user_message`, `human_answer`, `interrupt`
- 后端 → 前端：`switched`, `agent_state`, `text`, `thinking`, `completed_tool_use`, `tool_results`, `completed_message`, `human_question`, `error`

**连接管理**：
- 单一持久连接，通过 `switch_agent` 切换订阅的 agent
- 切换时先 unsubscribe 旧 agent dispatcher，再 subscribe 新 agent（带 replay）
- Agent 状态变化通过 `global_dispatcher` 广播

### 9.2 Team Chat WebSocket

**文件**：`backend/api/team_ws.py`

**路径**：`WS /api/ws/team/{team_id}`

**协议**：
- 前端 → 后端：`team_message`（含 @mention 信息）
- 后端 → 前端：`team_message`（路由后的消息）、`agent_state`

### 9.3 File Watch WebSocket

**文件**：`backend/api/file_watch.py`

**路径**：`WS /api/ws/files`

**依赖**：`watchdog`（可选，缺失时静默降级）

**机制**：
- 连接时根据前端发送的路径启动 watchdog Observer
- 文件变化事件经 debounce（0.5s）后推送
- 忽略 `.git`、`__pycache__`、`node_modules` 等目录和 `.pyc`、`.tmp` 等后缀
- 忽略 `opened`、`closed` 等无意义事件类型

---

## 10. Application Lifecycle

**文件**：`backend/main.py`

### 10.1 Lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await state_manager.load_all()
    yield
    # Shutdown — 保存所有 active session
    for agent_id, agent in agent_factory.agents.items():
        if agent.session:
            agent.session.save()
```

### 10.2 SPA 静态文件服务

当 `frontend/dist/` 存在时，自动挂载静态资源并提供 SPA fallback：

```python
# 挂载 /assets, /icons, /public
# 所有非 /api/ 和 /health 路径返回 index.html
```

### 10.3 Health Check

```python
@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## 11. Data Persistence

### 11.1 目录结构

```
data/
├── agents/
│   └── {agent_id}/
│       └── agent_config.json
├── teams/
│   └── {team_id}/
│       └── {team_name}/
│           ├── team_config.json
│           └── conversations/
│               ├── index.json
│               └── {conversation_id}/
│                   ├── meta.json
│                   └── messages.jsonl
├── models/
│   └── {model_id}.json
├── mcps/
│   └── {mcp_id}.json
├── prompts/
│   └── {prompt_id}.json
├── skills/
│   └── {skill_id}/
├── tools/
└── store.json              # UI State 持久化
```

### 11.2 Session 文件

每个 Agent 的 session 存储在 `agent.session_dir/{session_id}/` 下：
- `{session_id}.jsonl` — 消息日志
- `{session_id}.md` — 元数据（timestamp, turn_count, parent_session_id, fork_turn_index）

### 11.3 兼容性注意事项

- Session 文件（`.jsonl` + `.md`）是兼容性表面，修改格式需考虑迁移
- Team 消息持久化为 JSONL，消息结构需保持稳定
- `templates/` 目录下的模板是公开示例和兼容性 fixture
