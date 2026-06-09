

# 前端动作与后端功能映射文档

本文档详细描述 BBagent 前端所有用户动作与后端 API 的对应关系，覆盖数据流、请求格式、响应格式及状态更新逻辑。

---

## 一、开发环境代理配置

前端开发服务器（Vite）监听端口 `5173`，后端 FastAPI 监听端口 `8000`。通过 Vite 代理实现跨域请求转发：

| 代理规则 | 目标地址 | 说明 |
|---------|---------|------|
| `/api` | `http://localhost:8000` | REST API 请求转发 |
| `/api/ws` | `ws://localhost:8000` | WebSocket 连接转发 |

前端 API 基础路径：`http://localhost:8000/api`（生产环境可通过 `VITE_API_BASE` 覆盖）

---

## 二、全局状态初始化

### 2.1 应用启动加载（App.tsx）

**前端动作**：`useEffect(() => { loadAll(); }, [])`

**后端调用**：并发请求以下 7 个接口

| 接口 | 方法 | 路径 | 用途 |
|-----|------|------|------|
| listModels | GET | `/api/models` | 加载已配置模型列表 |
| listMcps | GET | `/api/mcps` | 加载 MCP 服务器列表 |
| listPrompts | GET | `/api/prompts` | 加载 Prompt 模板列表 |
| listSkills | GET | `/api/skills` | 加载 Skill 技能列表 |
| listAgents | GET | `/api/agents` | 加载单 Agent 列表 |
| listTeams | GET | `/api/teams` | 加载 Team 列表 |
| getState | GET | `/api/state` | 加载 UI 状态（工作目录等） |

**状态更新**：将 agents 与 teams 合并为一个列表存入 `agents`，同时更新 `models`、`mcpServers`、`prompts`、`skills`、`workingDirPath`。

---

## 三、模型管理（ModelsModule）

### 3.1 创建模型

**前端动作**：点击 "New Model" → 填写表单 → 点击 Save

**后端调用**：`POST /api/models`

**请求体**（ModelConfig）：
```json
{
  "id": "uuid",
  "name": "Claude Sonnet 4",
  "provider": "anthropic",
  "modelName": "claude-sonnet-4-20250514",
  "apiKey": "sk-xxx",
  "baseUrl": "https://api.anthropic.com",
  "maxContextTokens": 200000,
  "maxCompletionTokens": 100000,
  "temperature": 1.0,
  "topP": 0.95,
  "thinking": { "type": "adaptive", "budgetTokens": 12000 }
}
```

**状态更新**：`addModel` → `api.createModel(model)` → `set({ models: [...state.models, model] })`

### 3.2 更新模型

**前端动作**：选中模型 → 点击编辑 → 修改字段 → Save

**后端调用**：`PUT /api/models/{model_id}`

**请求体**：部分或完整 ModelConfig 字段

**状态更新**：`updateModel` → `api.updateModel(id, updates)` → 本地 state 同步更新对应模型

### 3.3 删除模型

**前端动作**：选中模型 → 点击删除

**后端调用**：`DELETE /api/models/{model_id}`

**响应**：
```json
{
  "success": true,
  "affectedAgents": ["agent-a", "agent-b"]
}
```

**`affectedAgents` 说明**：后端在删除 model 时会自动停止使用该 model 的 agent，并返回受影响的 agent 列表。前端应提示用户为这些 agent 重新选择模型后再启动。

### 3.3.1 更新模型（带 affectedAgents）

**响应**（`PUT /api/models/{model_id}`）：
```json
{
  ...原 ModelConfig 字段,
  "affectedAgents": ["agent-a", "agent-b"]
}
```

**含义**：用户改了 model config（API key / base URL 等），后端失效共享 `Model` 实例缓存，并自动为受影响的 agent 热替换新的 Model 实例（`agent.change_model(new_model)`），agent 无需重启即可使用新配置。

**前端约定**：
- 把 `affectedAgents` 显示在 toast/dialog 里（如 "模型配置已更新，已自动生效到 N 个 Agent"）
- agent 已自动切换到新模型，无需手动重启

### 3.4 测试模型 (Run Test)

**前端动作**：选中模型 → 在 Test 区域输入 Prompt → 点击 "Run Test"

**后端调用**：`POST /api/models/{model_id}/test`

**请求体**（ModelTestRequest）：
```json
{
  "prompt": "Hello, respond with a short greeting."
}
```

**后端行为**：
1. 根据 `ModelConfig` 构建核心 Model 配置字典（字段映射见下方）
2. 调用 `Model.from_config_dict(config_dict)` 实例化模型
3. 构造 `Model_Input(prompt=test_prompt)` 传入 `model.async_invoke()`
4. 从 `ModelMessage.content` 中提取纯文本内容返回

**字段映射**（前端 ModelConfig → 核心 Model 配置 dict）：

| ModelConfig 字段 | 核心配置字段 | 说明 |
|-----------------|-------------|------|
| `provider` | `provider` | 直接传递 |
| `modelName` | `model` | LLM 模型标识名 |
| `apiKey` | `api_key` | 支持 `${ENV_VAR}` 语法引用环境变量 |
| `baseUrl` | `base_url` | API 基础地址 |
| `maxContextTokens` | `max_context_tokens` | 上下文窗口大小 |
| `maxCompletionTokens` | `max_tokens` (anthropic) / `max_completion_tokens` (openai) | 按 provider 分配对应参数名 |
| `temperature` | `temperature` | 采样随机性 |
| `topP` | `top_p` | 核采样阈值 |
| `thinking` | `thinking` | 扩展思考模式配置 |

**响应**：
```json
{
  "content": "Hello! I'm doing great, how can I help you today?"
}
```

**前端状态更新**：`handleTest` → `api.testModel(id, prompt)` → `setResult(res.content)`，无全局 state 变更

**错误处理**：
- 400：模型初始化失败（provider 不识别、参数错误）
- 404：模型 ID 不存在
- 500：LLM API 调用失败（网络错误、认证失败、限流等），前端红色错误提示框展示

---

## 四、MCP 服务器管理（MCPsModule）

### 4.1 创建 MCP 服务器

**前端动作**：点击 "New MCP Server" → 填写 name/command/args/env（env 用 KEY+VALUE 单独输入行）→ Save

**后端调用**：`POST /api/mcps`

**请求体**（MCPServerConfig）：
```json
{
  "name": "firecrawl",
  "command": "npx",
  "args": ["-y", "@firecrawl/mcp"],
  "env": { "FIRECRAWL_API_KEY": "xxx" },
  "tools": []
}
```

**状态更新**：`addMcpServer` → `api.createMcp(server)` → `set({ mcpServers: [...state.mcpServers, server] })`

### 4.2 更新 MCP 服务器

**前端动作**：编辑 MCP 配置

**后端调用**：`PUT /api/mcps/{name}`

**响应**：
```json
{
  ...原 MCPServerConfig 字段,
  "hint": "MCP server config updated. Agents using tools from this MCP server may need to restart to take effect"
}
```

**前端约定**：检查响应中的 `hint` 字段，非空时弹窗提示用户。

### 4.3 删除 MCP 服务器

**前端动作**：点击删除

**后端调用**：`DELETE /api/mcps/{name}`

**响应**：
```json
{
  "success": true,
  "hint": "MCP server deleted. Agents using tools from this MCP server need to reconfigure their tools"
}
```

**前端约定**：检查响应中的 `hint` 字段，非空时弹窗提示用户。

### 4.4 发现 MCP 工具

**前端动作**：在 MCP 详情页点击 "Discover Tools" 按钮（位于 header 右侧，带 RefreshCw 图标，点击时图标旋转表示 loading）

**后端调用**：`POST /api/mcps/{id}/discover`

**后端行为**：`state_manager.discover_mcp_tools(mcp_id)` → `MCPFactory._discover_tools()` 创建临时 MCPClient → 建立 STDIO 连接 → 握手 → 获取 tools 列表 → 更新 MCPServerConfig.tools + ToolFactory 注册 → 断开连接

**ToolConfig 字段（discover 缓存）**：
```json
{
  "id": "uuid5-derived-id",
  "name": "crawl",
  "source": "mcp",
  "description": "...",
  "mcpServerId": "mcp-server-uuid"
}
```

- `id`：由 `_mcp_tool_id(mcp_server_id, raw_name)` 生成的确定性 UUID5
- `name`：工具在 MCP server 上的原始名
- `source`：固定为 `"mcp"`
- `mcpServerId`：所属 MCP 服务器的 id

**响应**：`{ "success": true, "tools": [...] }`

**状态更新**：`discoverMcpTools` → 调用 `api.discoverMcp(id)` → 刷新 `mcpServers` 和 `tools` 列表 → toast 提示发现的工具数量

### 4.5 Agent 使用 MCP 工具时建立连接

**行为**：Agent 创建或更新时 `toolIds` 包含 MCP 工具的 ToolConfig.id，`AgentFactory` 通过 `ToolFactory.build_tool` 解析出 MCP server，为该 Agent 创建独立的 MCPClient 连接。每个 Agent 拥有各自的 MCP 子进程实例，互不共享。

---

## 五、Prompt 管理（PromptsModule）

Prompt 支持 `group` 字段进行分组管理，类似浏览器收藏夹分组。`group` 为空字符串表示未分组（显示在顶层）。

### 5.1 创建 Prompt

**前端动作**：新建 Prompt → 填写 name/content/group → Save

**后端调用**：`POST /api/prompts`

**请求体**（PromptConfig）：
```json
{
  "id": "uuid",
  "name": "Code Reviewer",
  "content": "You are a code reviewer...",
  "group": "代码审查"
}
```

### 5.2 更新 Prompt

**后端调用**：`PUT /api/prompts/{prompt_id}`

可更新 `group` 字段实现移入/移出分组操作。

### 5.3 删除 Prompt

**后端调用**：`DELETE /api/prompts/{prompt_id}`

### 5.4 分组操作

分组操作均通过更新 prompt 的 `group` 字段实现，无需独立 API：

| 操作 | 实现方式 |
|------|---------|
| 创建组 | 创建 prompt 时设置 `group`，或拖拽 prompt 到 "New Group" |
| 移入组 | `PUT /api/prompts/{id}` 更新 `group` 为目标组名 |
| 移出组 | `PUT /api/prompts/{id}` 更新 `group` 为 `""` |
| 删除组 | 批量更新该组所有 prompt 的 `group` 为 `""`（仅删组）或批量删除 |
| 重命名组 | 批量更新该组所有 prompt 的 `group` 为新名称 |

### 5.5 导入 Prompt

**后端调用**：`POST /api/prompts/import`

**请求体**：
```json
{
  "path": "/path/to/folder",
  "group": "导入的组名"
}
```

`group` 可选，指定后导入的 prompt 自动归入该组。

---

## 六、Skill 管理（SkillsModule）

### 6.1 加载 Skill 列表

**前端动作**：应用启动时自动加载

**后端调用**：`GET /api/skills`

**响应**：SkillConfig 列表

**注意**：Skill 为只读列表，后端通过 `state_manager.list_skills()` 从文件系统扫描加载，前端仅展示，不提供增删改 API。

---

## 七、Agent 管理

### 7.1 创建单 Agent

**前端动作**：Onboarding 或顶部栏 → "Create Agent" → 选择 "Single Agent" → 填写表单 → Save

**后端调用**：`POST /api/agents`

**请求体**（AgentConfig，按三组分类）：
```json
{
  "name": "my-agent",
  "type": "single",
  "modelId": "model-uuid",
  "systemPrompt": "You are a helpful assistant",
  "workingDir": "/Users/me/projects/my-agent",
  "toolIds": ["bash", "read", "write"],
  "skillIds": ["web-search"],
  "toolPolicy": {
    "maxReadSize": 200000,
    "maxReadLines": 3000,
    "maxWriteSize": 5242880,
    "writeCreateDirectories": true,
    "bashMaxOutputLines": 1000,
    "bashDefaultTimeout": 60
  },
  "hookNames": ["built_in.memory", "built_in.compress"],
  "hookConfig": {
    "submodelId": "model-uuid-sub",
    "merge_ratio": 0.2,
    "small_turn_cap": 5000,
    "memory_system_prompt": "..."
  }
}
```

**字段说明（三组分类）**：
- **Basic（基本信息）**：`name`、`modelId`、`systemPrompt`、`workingDir`
  - `workingDir` 映射到后端 `toolPolicy.cwd`，留空回退到 `agent.base_dir`
- **Tools（工具配置）**：`toolIds`、`skillIds`、`toolPolicy`
  - `toolPolicy` 是所有内置工具共享的配置（含 cwd，前端提交时同步 workingDir 到 cwd），各 tool creator 自己取需要的字段
- **Hooks（Hook 配置）**：`hookNames`、`hookConfig`
  - `hookNames` 是启用的 hook 列表（默认 `["built_in.memory", "built_in.compress"]`）
  - `hookConfig` 是一个共享的大字典，所有 hook creator 取自己关心的字段

> **name 自动生成**：如果 name 为空字符串，后端不传 name 参数给 CoreAgentConfig，dataclass 默认值自动生成类似 `Agent_2026-05-29_a1b2c3d4` 的名称。响应中返回生成的 name，前端 `createAgentApi` 以后端响应为准更新 Store。
>
> **basePath 由后端自动生成**：前端不需要也不应该发送。响应中会回填，供 BasedirTree 渲染文件树。

**后端行为**：`state_manager.create_agent(config)` 实例化 Agent 对象，保存到 `data/agents/{id}/{name}/`，加入运行时字典（key = agent_id）。Hook 配置会解析 `submodelId` 为 `Model` 实例后传给 `BuiltinHookConfig`。

**状态更新**：`createAgentApi` → 成功后 `set({ agents: [...state.agents, created], activeAgentId: created.id })`

### 7.1.1 获取 Hook 描述符（前端动态生成 Hook 配置页）

**前端动作**：应用启动时 `loadAll` 并行拉取

**后端调用**：`GET /api/hooks`

**响应**（HookListResponse）：
```json
{
  "hooks": [
    {
      "name": "built_in.memory",
      "displayName": "Memory",
      "description": "Long-term memory system ...",
      "defaultEnabled": true,
      "fieldSections": [
        {
          "title": "Memory",
          "fields": [
            {"key": "memory_system_prompt", "type": "text", "label": "Memory System Prompt", "default": "..."},
            {"key": "clean_mutation_threshold", "type": "number", "label": "Clean Mutation Threshold", "default": 50}
          ]
        }
      ]
    },
    {
      "name": "built_in.compress",
      "displayName": "Context Compression",
      "description": "...",
      "defaultEnabled": true,
      "fieldSections": [...]
    }
  ],
  "sharedSections": [
    {
      "title": "Shared",
      "fields": [
        {"key": "submodelId", "type": "modelId", "label": "Sub-model", "default": "", "description": "..."},
        {"key": "merge_ratio", "type": "float", "label": "Merge Ratio", "default": 0.2},
        {"key": "small_turn_cap", "type": "number", "label": "Small Turn Cap", "default": 5000}
      ]
    }
  ]
}
```

**字段类型**：`string` / `text` / `number` / `float` / `boolean` / `modelId`（`modelId` 渲染为模型下拉框）

**默认实现**：[backend/api/hooks.py](file:///Users/gonglin/Desktop/note/BBagent/backend/api/hooks.py) 从 `BuiltinHookConfig` dataclass 读取字段默认值，新增 hook 时只需要扩展 `_HOOK_DEFINITIONS` 即可。

### 7.2 获取 Agent 详情

**前端动作**：选中某个 Agent Tab

**后端调用**：`GET /api/agents/{id}`

**响应**：完整 AgentConfig（包含 `id`、`basePath`、`workingDir`、`toolPolicy`、`hookNames`、`hookConfig` 等新字段，不含 `messages` 历史）

### 7.3 更新 Agent

**前端动作**：编辑 Agent 配置

**后端调用**：`PUT /api/agents/{id}`

**后端行为**：`state_manager.update_agent(agent_id, updates)` 支持部分更新。新增对 `toolPolicy` / `workingDir`（映射到 `policy.cwd`）和 `hookNames` / `hookConfig`（清空所有 hook 后按新配置重建，option A）的支持。`modelId` 变化时通过 `_resolve_model` / `_release_model` 维护共享实例的 refcount。

### 7.3.1 启动与停止 Agent

**前端动作**：用户主动开始/停止对话

**后端调用**：
- `POST /api/agents/{id}/start`
- `POST /api/agents/{id}/stop`

**后端行为**：
- `start_agent` 第一次会调 `_lazy_init_agent` 实例化 tools/skills/hooks，再启动事件循环；后续调用已 running 时 no-op
- `stop_agent` 取消任务并停止事件循环
- 两个方法都会把 `started: true/false` 写入 `agent_config.yaml`，**应用重启后可恢复**

**与 `create_agent` 的关系**：
- `create_agent` **不**自动 start（API 层解耦）
- 前端在拿到 `POST /api/agents` 响应后**立即**调 `start_agent`（这是默认行为）
- `create_agent` 完成后 yaml 写入 `started: false`；前端调 `start_agent` 后改为 `started: true`

### 7.4 删除 Agent

**前端动作**：鼠标悬停 Agent Tab → 点击删除（Trash2）图标 → 弹出 ConfirmDialog

**ConfirmDialog 内容**：
- 标题：`Delete Agent`
- 内容：`Are you sure you want to delete "{name}"? Do you want to delete the source files as well?`
- 三个按钮：
  - **Yes** → `DELETE /api/agents/{id}?delete_files=true` — 删除 agent 及其 basePath 下所有源文件
  - **No** → `DELETE /api/agents/{id}` — 仅删除 agent 记录，保留源文件
  - **Cancel** → 关闭弹窗，无操作

**状态更新**：`removeAgent` → `set({ agents: [...], activeAgentId: null })`

### 7.5 新建会话

**前端动作**：点击 "New Session" 按钮

**后端调用**：`POST /api/agents/{id}/sessions/new`

**后端行为**：`state_manager.new_agent_session(agent_id)` 创建新 Session 实例，清空当前对话上下文

**响应**：`{ "session_id": "uuid" }`

### 7.6 启动 Agent

**前端动作**：点击 AgentTab 的 ▶ (Play) 按钮

**后端调用**：`POST /api/agents/{id}/start`

**后端行为**：`state_manager.start_agent(agent_id)` 创建异步 Task 运行 `agent.start()` 事件循环，注册 `on_output` 回调到 dispatcher

**响应**：`{ "state": "waiting", "session_id": "uuid" }`

**状态更新**：`startAgent` → `setAgentState(agentId, "waiting")`

### 7.7 停止 Agent

**前端动作**：点击 AgentTab 的 ■ (Square) 按钮

**后端调用**：`POST /api/agents/{id}/stop`

**后端行为**：`state_manager.stop_agent(agent_id)` 调用 `agent.stop()`，取消异步 Task，通过 dispatcher 广播 stop 消息

**响应**：`{ "state": "ready", "session_id": "uuid" }`

**状态更新**：`stopAgent` → `setAgentState(agentId, "ready")`

### 7.8 查询 Agent 状态

**前端动作**：AgentTab 实时显示状态指示器（定时轮询或 WebSocket 推送）

**后端调用**：`GET /api/agents/{id}/state`

**响应**：`{ "state": "running", "session_id": "uuid" }`

### 7.9 列出 Agent 会话

**前端动作**：ChatWindow 加载时

**后端调用**：`GET /api/agents/{id}/sessions`

**响应**：
```json
[
  { "id": "session-uuid", "timestamp": "2026-05-30 10:00", "turnCount": 5, "isActive": true }
]
```

**状态更新**：`loadAgentSessions` → `agentSessions[agentId] = sessions`

### 7.10 切换会话

**前端动作**：Session 下拉菜单中点击某个历史会话

**后端调用**：`POST /api/agents/{id}/sessions/{session_id}/switch`

**后端行为**：`state_manager.switch_agent_session(agent_id, sessionId)` 加载指定 JSONL 会话文件

**响应**：`{ "session_id": "uuid", "status": "switched" }`

**状态更新**：`switchSession` → 更新 `agentSessions[agentId]` 的 `isActive` 标记 → `loadAgentMessages(agentId)` 重新加载历史消息

### 7.11 加载历史消息

**前端动作**：ChatWindow 挂载时 / 切换会话后

**后端调用**：`GET /api/agents/{id}/messages`

**响应**：消息数组，每条含 `role`, `content`, `chunkType`, `thinking`, `toolName`, `toolInput`, `toolResult`, `sourceAgent`, `timestamp`

**状态更新**：`loadAgentMessages` → 更新 `agents[agentId].messages`

### 7.12 定时任务管理（Timer CRUD）

前端在 ChatWindow 输入框上方提供 Timer 按钮和上拉面板，支持定时任务的增删改查及启停操作。

#### 7.12.1 获取定时任务列表

**前端动作**：切换 Agent 时自动加载 / Timer 面板展开时刷新

**后端调用**：`GET /api/agents/{id}/timers`

**响应**：TimerConfig 数组
```json
[
  { "name": "check", "seconds": 30, "hint": "check status", "enabled": true, "running": true },
  { "name": "report", "seconds": 60, "hint": "generate report", "enabled": true, "running": false }
]
```

**状态更新**：`loadTimers` → `set({ agentTimers: { ...s.agentTimers, [id]: timers } })`

#### 7.12.2 新建定时任务

**前端动作**：Timer 面板点击 "+ Add Timer" → 填写 name/seconds/hint → 保存

**后端调用**：`POST /api/agents/{id}/timers`

**请求体**：
```json
{ "name": "check", "seconds": 30, "hint": "check status", "enabled": true }
```

**name 处理规则**：
- name 为空时，后端自动生成唯一名称（格式 `timer_{N}`，N 递增直到不重复）
- name 非空但与已有 timer 重名时，后端返回 `409 Conflict`，前端即时校验并提示 "Name already exists"

**响应**：更新后的 TimerConfig 数组（同 list）

**错误响应**：
- `409 Conflict`：`{"detail": "Timer 'xxx' already exists"}` — 重名

**状态更新**：`addTimer` → 替换 `agentTimers[id]`

#### 7.12.3 更新定时任务

**前端动作**：Timer 面板点击编辑按钮 → 修改 seconds/hint 字段 → 保存（name 为只读，不支持重命名）

**后端调用**：`PUT /api/agents/{id}/timers/{name}`

**请求体**：
```json
{ "seconds": 45, "hint": "updated hint", "enabled": true }
```

> **注意**：`name` 是 Timer 的唯一标识（路径参数），后端不支持重命名。前端编辑模式下 name 字段为只读。

**响应**：更新后的 TimerConfig 数组

**状态更新**：`updateTimer` → 替换 `agentTimers[id]`

#### 7.12.4 启动定时任务

**前端动作**：Timer 面板点击 ▶ 按钮

**后端调用**：`POST /api/agents/{id}/timers/{name}/start`

**响应**：`{ "success": true }`

**状态更新**：`startTimer` → 重新 `loadTimers(id)` 刷新列表

#### 7.12.5 停止定时任务

**前端动作**：Timer 面板点击 ■ 按钮

**后端调用**：`POST /api/agents/{id}/timers/{name}/stop`

**响应**：`{ "success": true }`

**状态更新**：`stopTimer` → 重新 `loadTimers(id)` 刷新列表

#### 7.12.6 删除定时任务

**前端动作**：Timer 面板点击 🗑 → 直接删除

**后端调用**：`DELETE /api/agents/{id}/timers/{name}`

**响应**：更新后的 TimerConfig 数组

**状态更新**：`deleteTimer` → 替换 `agentTimers[id]`

---

## 八、Team 管理

### 8.1 创建 Team

**前端动作**："Create Agent" → 选择 "Agent Team" → 填写配置 → Save

**后端调用**：`POST /api/teams`

**请求体**（CreateTeamRequest）：

Team 创建请求将 team 级别配置与 member agent 配置分开，前端不再发送臃肿的单一对象：

```json
{
  "name": "dev-team",
  "teamDescription": "A team for development",
  "workingDir": "/Users/me/projects",
  "members": [
    {
      "name": "coder",
      "modelId": "model-uuid",
      "systemPrompt": "You are a coder",
      "workingDir": "/Users/me/projects/dev-team",
      "toolIds": ["bash", "read", "write"],
      "skillIds": [],
      "hookNames": ["built_in.memory"],
      "hookConfig": {},
      "toolPolicy": { "cwd": "/Users/me/projects/dev-team" }
    },
    {
      "name": "reviewer",
      "modelId": "model-uuid",
      "systemPrompt": "You are a reviewer",
      "workingDir": "/Users/me/projects/dev-team",
      "toolIds": ["read"],
      "skillIds": [],
      "hookNames": [],
      "hookConfig": {},
      "toolPolicy": { "cwd": "/Users/me/projects/dev-team" }
    }
  ],
  "contacts": {
    "coder": { "reviewer": "..." }
  }
}
```

**后端行为**：`state_manager.create_team(config, member_configs=req.members)` 先创建 member agents，再创建 team 并关联。

**响应**：`TeamConfig` + `members` 字段（包含每个 member agent 的完整 `AgentConfig` 详情），前端据此构建 `SingleAgent` 条目并关联到 team。

**状态更新**：`createTeamApi` → 成功后合并到 agents 列表

### 8.2 获取 Team 详情

**后端调用**：`GET /api/teams/{id}`

### 8.3 更新 Team

**后端调用**：`PUT /api/teams/{id}`

### 8.4 删除 Team

**后端调用**：`DELETE /api/teams/{id}`

### 8.5 启动 Team

**前端动作**：点击 Start Team

**后端调用**：`POST /api/teams/{id}/start`

**后端行为**：`team.start()` 启动团队内所有 Agent 的协作循环，然后通过 `team.update_state()` 聚合成员状态

**响应**：`{ "state": "waiting" }`

**状态更新**：`startTeam` → `setAgentState(id, result.state)` — 使用后端返回的真实聚合状态

### 8.6 停止 Team

**前端动作**：点击 Stop Team

**后端调用**：`POST /api/teams/{id}/stop`

**后端行为**：`team.stop()` 停止团队协作，然后通过 `team.update_state()` 聚合成员状态

**响应**：`{ "state": "ready" }`

**状态更新**：`stopTeam` → `setAgentState(id, result.state)` — 使用后端返回的真实聚合状态

---

## 九、文件系统操作

### 9.1 获取目录树

**前端动作**：展开 BasedirTree / WorkingDirView 中的文件夹

**后端调用**：`GET /api/files/tree?path={absolute_path}`

**响应**（FileNode）：
```json
{
  "name": "src",
  "path": "src",
  "type": "directory",
  "children": [
    { "name": "App.tsx", "path": "src/App.tsx", "type": "file", "size": 1200, "extension": "tsx", "modifiedAt": 1716123456 }
  ]
}
```

**注意**：目录按文件夹优先、字母序排序；遇到权限错误静默跳过。

### 9.2 读取文件内容

**前端动作**：点击文件节点 → 打开右侧预览面板

**后端调用**：`GET /api/files/read?path={absolute_path}`

**响应**：
```json
{
  "content": "file text content...",
  "mimeType": "text/typescript",
  "name": "App.tsx",
  "path": "/workspace/src/App.tsx"
}
```

**状态更新**：`openFilePreview({ path, name, content, mimeType })`

### 9.2.1 获取原始文件内容（用于图片/PDF预览）

**前端动作**：文件预览面板加载图片、PDF 等二进制文件时

**后端调用**：`GET /api/files/raw?path={absolute_path}`

**后端行为**：
- 根据扩展名检测 MIME 类型
- 文本类文件（`text/*`、`application/json`、`application/xml`、`image/svg+xml`）：以 UTF-8 读取并以相应 Content-Type 返回
- 二进制文件（`image/png`、`application/pdf` 等）：以原始字节返回

**Content-Type 响应头**：根据文件类型动态设置

**响应**：原始文件内容（非 JSON 封装），浏览器直接渲染

### 9.2.2 文件预览支持类型

### 9.3 写入文件

**前端动作**：在文件预览面板中编辑并保存

**后端调用**：`POST /api/files/write`

**请求体**：
```json
{
  "path": "/workspace/src/App.tsx",
  "content": "updated content..."
}
```

**后端行为**：自动创建父目录（`mkdir -p`），UTF-8 写入文件

**响应**：`{ "success": true }`

---

## 十、聊天对话（WebSocket）

### 10.1 建立连接

**前端动作**：ChatWindow 挂载时创建一条持久 WebSocket 连接

**WebSocket 连接**：
- 单 Agent：`ws://localhost:8000/api/ws/chat`（持久连接，通过 `switch_agent` 切换，发送 `agent_id`）
- Team 群聊：`ws://localhost:8000/api/ws/team/{team_id}`

**连接生命周期**：
1. ChatWindow 挂载时创建 WS，挂载时创建一次（不再随 Agent 切换重建）
2. WS `onopen` 时自动发送当前选中 Agent 的 `switch_agent`
3. Agent 切换时发送 `switch_agent` 而不关闭连接
4. WS 意外断开时自动重连（2秒延迟）
5. ChatWindow 卸载时关闭连接

**持久连接架构**（2026-06-01）：Chat WebSocket 从 per-agent 模式改为单一持久连接。前端切换 Agent 时发送 `{"type": "switch_agent", "agent_name": "..."}`,后端在 Dispatcher 层切换订阅，forwarder 通过 sentinel 机制无缝切换消费队列。

### 10.1.1 切换 Agent 订阅

**前端发送**：
```json
{"type": "switch_agent", "agent_name": "agent-2"}
```

**后端处理**：
1. `switch_lock` 加锁防竞态
2. 验证新 Agent 存在且 Dispatcher 可用（失败则返回 error，不丢失现有订阅）
3. 从旧 Agent Dispatcher 取消订阅（向旧队列推送 sentinel）
4. 向新 Agent Dispatcher 订阅 `subscribe(replay=True)`（回放 round buffer 中当前轮的 chunks）
5. 发送 `{"type": "switched", "agent_name": "agent-2"}` 确认

### 10.2 发送用户消息

**前端发送**：
```json
{"type": "user_message", "content": "Hello, agent!"}
```

**后端处理**：
1. `receiver()` 任务接收消息
2. 通过 `current_agent_name` 查找当前 Agent
3. 调用 `agent.input.push(content)` 推入 Agent 事件循环的 input 队列
4. Agent 事件循环消费 input queue → 处理消息 → 通过 dispatcher 输出 chunk
5. `forwarder()` 从 dispatcher 订阅队列拉 chunk → 发送回前端

### 10.3 Team 群聊消息发送

**前端发送**（通过 TeamChatWindow）：
```json
{"type": "user_message", "content": "@coder fix the bug in app.ts", "mentions": ["coder"]}
```

**后端处理**（`team_ws.py`）：
1. 优先使用 `mentions` 数组，否则正则提取 `@name` 前缀
2. 去除了 `@name` 前缀后的消息内容推入被 mention 的 Agent 的 input queue
3. 多个 mention → 消息分发到所有被 mention 的 agent
4. Forwarder 合并所有成员 dispatcher 的输出，标注 `source_agent` 字段后发送

### 10.4 接收流式响应

**后端推送**（逐 chunk）：
```json
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

**前端处理**：
- `agent_state` chunk：更新 `agentStates[name]` 和 `agent.state`；`running` 时启用流式标志，其他状态停用；同时更新 `agentContextTokens[name]` 用于上下文进度条显示
- `text` chunk：累积到 stream buffer，原地更新最后一条 assistant 消息的 content
- `thinking` chunk：追加紫色 thinking bubble
- `completed_tool_use`：追加橙色 tool_use bubble（含 tool name + JSON input）
- `tool_results`：追加橙色 tool_result bubble
- `completed_message`：重置 stream buffer
- `error`：追加红色 error bubble

### 10.5 中断 Agent

**前端动作**：当 `agentState === "running"` 时，Send 按钮变为红色中断按钮；当 `agentState === "waiting"` 时，Send 按钮启用；其他状态禁用

**前端发送**：
```json
{"type": "interrupt"}
```

**后端处理**：`agent.interrupt()` → 通过 dispatcher 发送 `{"type": "interrupted"}`

### 10.6 错误处理

**后端推送**：`{ "type": "error", "content": "error message" }`

**连接关闭**：
- Agent 不存在：code `4004`
- Dispatcher 不存在：code `4005`

---

## 十一、UI 状态持久化

### 11.1 保存 UI 状态

**前端动作**：切换 Agent、调整设置等操作时自动保存

**后端调用**：`POST /api/state`

**请求体**（UIState）：
```json
{
  "currentTab": "agent",
  "currentAgentName": "agent-1",
  "currentTeamName": null,
  "settingsOpen": false,
  "settingsTab": "models",
  "workingDirPath": "/workspace/project"
}
```

**后端行为**：`state_manager.ui_state = state` → `state_manager.save_ui_state()` 持久化到 JSON 文件

### 11.2 恢复 UI 状态

**前端动作**：应用启动时 `loadAll()` 中调用

**后端调用**：`GET /api/state`

---

## 十二、前端状态管理映射表

| Zustand State | 来源 | 后端 API | 更新 Action |
|--------------|------|---------|------------|
| `models` | `loadAll()` | `GET /api/models` | `addModel`, `updateModel` |
| `mcpServers` | `loadAll()` | `GET /api/mcps` | `addMcpServer`, `updateMcpConnection` |
| `prompts` | `loadAll()` | `GET /api/prompts` | `importPrompts`（本地合并） |
| `skills` | `loadAll()` | `GET /api/skills` | `importSkills`（本地合并） |
| `agents` | `loadAll()` | `GET /api/agents` + `GET /api/teams` | `createAgentApi`, `createTeamApi`, `updateAgent`, `removeAgent` |
| `agentStates` | `loadAll()` + WebSocket | `GET /api/agents` (含 state) + WebSocket `agent_state` chunk | `setAgentState`, `startAgent`, `stopAgent` |
| `agentStates` | HTTP + WebSocket | agent state (`agent_state` chunk / HTTP response) | `setAgentState` |
| `agentSessions` | `loadAll()` + 操作触发 | `GET /api/agents/{name}/sessions` | `loadAgentSessions`, `switchSession`, `createNewSession` |
| `workingDirPath` | `loadAll()` | `GET /api/state` | `setWorkingDirPath`, `setActiveAgentName` |
| `baseDirPath` | `loadAll()` | `GET /api/state` | `setBaseDirPath`, `setActiveAgentName` |
| `activeAgentName` | 用户操作 | — | `setActiveAgentName`, `createAgentApi`, `removeAgent` |
| `activeTeamMemberName` | 用户操作 | — | `selectTeamMember` |
| `configDialog` | 用户操作 | — | `openConfigDialog(agentName)`, `closeConfigDialog` |
| `tools` | 硬编码默认值 | 无 | 不变（内置 7 个工具） |
| `messages` | AgentConfig + `loadAgentMessages()` | `GET /api/agents/{name}/messages` | `addMessage`（WebSocket 发送），`loadAgentMessages`（历史加载） |

---

## 十三、类型对齐对照

| 前端 TypeScript 接口 | 后端 Pydantic 模型 | 说明 |
|---------------------|-------------------|------|
| `Model` | `ModelConfig` | 模型配置 |
| `Tool` | `ToolConfig` | 工具定义（`name` + `rawName?` + `mcpServerName?` 替代旧的 `id` + `isMcp`） |
| `Skill` | `SkillConfig` | 技能定义 |
| `MCPServer` | `MCPServerConfig` | MCP 服务器配置 |
| `Prompt` | `PromptConfig` | Prompt 模板 |
| `Message` | — (dict) | 聊天消息，含 `chunkType`, `thinking`, `toolName`, `sourceAgent` |
| `SessionInfo` | — (dict) | 会话信息，含 `id`, `timestamp`, `turnCount`, `isActive` |
| `Agent` | `AgentConfig` | Agent/Team 配置 + `state`, `sessions`, `currentSessionId` |
| `FileNode` | `FileNode` | 文件树节点 |
| - | `AgentSummary` | Agent 列表摘要（后端专用） |
| - | `TeamSummary` | Team 列表摘要（后端专用） |
| - | `UIState` | UI 持久化状态 |
| - | AgentStateResponse | `{state, session_id}` |

---

## 十四、错误处理规范

| HTTP 状态码 | 场景 | 前端行为 |
|------------|------|---------|
| 400 | 资源已存在（同名 Agent/Model/MCP/Prompt） | 显示错误提示 |
| 404 | 资源未找到 | 显示 Not Found 提示 |
| 500 | 后端执行错误 | 显示详细错误信息 |
| WebSocket 4004 | Agent 不存在 | 关闭连接，提示选择有效 Agent |

---

## 十五、尚未接入后端的本地功能

以下功能当前为前端本地 mock 或未完全接入后端：

| 功能 | 当前状态 | 待接入 API |
|-----|---------|-----------|
| ChatWindow 消息发送 | WebSocket 实时通信 | `ws /api/ws/chat` |
| PromptsModule 导入 | FolderPickerModal → `POST /api/prompts/import` | ✓ 已接入后端导入 API |
| SkillsModule 导入 | FolderPickerModal → `POST /api/skills/import` | ✓ 已接入后端导入 API |
| MCPsModule 导入 | FolderPickerModal → `POST /api/mcps/import` | ✓ 已接入后端导入 API |

---

*文档版本：v1.1*  
*更新日期：2026-05-30*


---

## 十六、近期更新 (2026-05-28)

### 16.1 目录浏览 API

`GET /api/files/dirs?path={absolute_path}` -- 返回指定路径下的直接子目录列表

```json
{"current": "/Users/gonglin", "parent": "/Users", "separator": "/", "directories": ["Desktop", "Documents"]}
```

前端用途：FolderPicker 组件（Base Path、Policy Working Directory、SkillsModule/MCPsModule/PromptsModule 的 Import from Folder）

### 16.2 模型测试 API

`POST /api/models/{model_id}/test`

请求体: `{"prompt": "test message"}`

后端用 HumanMessage 包装 prompt 传入 Model.async_invoke()，从响应提取纯文本返回。

### 16.3 AgentConfig 扩展

新增字段:
- `workingDir: str` -- Agent 工具允许操作的工作目录
- `policy: dict` -- Policy 配置（cwd, 读写限制, bash 输出/超时限制, sub-agent 配置）

### 16.4 list_agents 返回完整数据

`GET /api/agents` 现在返回完整 `AgentConfig` 对象（调用 `get_agent_config`），而非精简的 `AgentSummary`。前端可获取 basePath、workingDir、policy、toolIds、skillIds 等完整信息。

### 16.5 前端 Store 关联

| Store 字段 | 来源 |
|-----------|------|
| `workingDirPath` | agent.policy.cwd (顶部面板 Working Dir) |
| `baseDirPath` | agent.basePath (底部面板 Base Path) |
| `activeAgentName` | 刷新后为 null → 显示引导页，点击 tab 后设置 |

### 16.6 引导页逻辑变更

`App.tsx` 中 `isOnboarding` 从 `agents.length === 0` 改为 `!activeAgentName`。
刷新页面后总是显示引导页，点击 agent tab 切换到工作区。

### 16.7 Import 导入 API

| API | 方法 | 说明 |
|-----|------|------|
| `POST /api/skills/import` | `{path}` | 扫描子目录中的 SKILL.md 文件，返回 `{imported: N, skills: [...]}` |
| `POST /api/mcps/import` | `{path}` | 扫描 .json 文件，解析为 MCPServerConfig，返回 `{imported: N}` |
| `POST /api/prompts/import` | `{path}` | 扫描 .md/.txt 文件，创建 PromptConfig，返回 `{imported: N}` |

前端点击 "Import from Folder" → 弹出 FolderPickerModal 选择文件夹 → 选择后直接调用对应 import API，刷新 Store 数据。

### 16.8 Agent 删除与源文件清理

`DELETE /api/agents/{name}?delete_files=true`

- `delete_files=false` (默认): 仅从注册表移除 Agent，保留 basePath 下源文件
- `delete_files=true`: 同时删除 Agent 的 basePath 目录（`shutil.rmtree`）

前端通过 ConfirmDialog（Yes/No/Cancel）选择是否同时删除源文件。

### 16.9 Name-Based Identity

Agent/Team 的 `id` 字段已从前端类型和 Pydantic Schema 中移除。`name` 是唯一标识符（`state_manager.agents` 为 `Dict[name, Agent]`，文件存储在 `data/agents/{name}/`）。

Store 中 `activeAgentId` 重命名为 `activeAgentName`，所有 action 参数统一使用 `name`。

### 16.10 BasePath 字段移除

AgentConfigDialog 中不再包含 BasePath 表单字段。后端 `create_agent` 固定使用 `base_dir=DATA_DIR / "agents"`。Agent 的 basePath 仍存在于响应数据中，仅作展示用途。

---

## 十七、近期更新 (2026-05-30)

### 17.1 消除 Mock 数据

WorkingDirView 和 BasedirTree 中的硬编码文件树数据已删除，改为通过 `GET /api/files/tree` 获取真实数据。

### 17.2 文件预览系统重构

新增 `GET /api/files/raw` 端点，返回文件的原始内容（非 JSON 封装），支持：
- **文本/代码文件**：通过 `GET /api/files/read` 获取 JSON 格式内容，前端用 prism-react-renderer 语法高亮
- **Markdown (.md)**：使用 react-markdown 进行真 Markdown 渲染
- **图片 (.png/.jpg/.gif/.svg/.webp)**：通过 `<img src="/api/files/raw?path=...">` 直接加载
- **PDF (.pdf)**：通过 `<iframe src="/api/files/raw?path=...">` 内嵌预览

预览面板新增三种状态：
- **Loading**：spinner + "Loading file..."（content 为 null 且无 error）
- **Error**：红色错误提示 + 具体错误信息（catch 块不再静默吞掉错误）
- **Unsupported**：提示用外部编辑器打开（MIME 不被支持时）

`getMimeType()` 提取为 `src/lib/utils.ts` 的公共工具函数，消除 WorkingDirView 和 BasedirTree 中重复的 MIME 映射代码。

---

## 十八、近期更新 (2026-05-30) — Event Loop & Dispatcher 重构

### 18.1 Agent 生命周期端点

新增以下 REST 端点用于 Agent 生命周期管理：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agents/{name}/start` | 启动 Agent `start()` 事件循环 |
| POST | `/api/agents/{name}/stop` | 停止 Agent 事件循环 |
| GET | `/api/agents/{name}/state` | 查询 Agent 运行状态 |
| GET | `/api/agents/{name}/sessions` | 列出所有历史会话 |
| POST | `/api/agents/{name}/sessions/{id}/switch` | 切换到指定会话 |
| POST | `/api/agents/{name}/sessions/new` | 创建新会话 |
| GET | `/api/agents/{name}/messages` | 加载历史消息（含 chunkType/thinking/toolName 等） |

### 18.2 Agent 架构变更：`run()` → `start()` Event Loop

- **旧**：`agent.run(human_msg)` — 每次消息创建一次生成器迭代
- **新**：`agent.start()` — 持久 asyncio.Task 事件循环，通过 `agent.input.push()` 接收消息
- Agent 由 StateManager 管理生命周期：启动时 `start_all_agents()` 自动启动所有已加载 Agent
- Agent 状态机：Ready → Waiting → Running → Error

### 18.3 AgentOutputDispatcher（Fan-Out）

- 每个 Agent 绑定一个 `AgentOutputDispatcher`
- Agent 注册回调：`agent.on_output(dispatcher.on_chunk)`
- 多个 WebSocket 订阅者可通过 `dispatcher.subscribe()` 同时接收输出
- Chat handler 不再运行 runner task，改为从 dispatcher 订阅队列拉取 chunk

### 18.4 chat.py 重写

- `receiver`：读取 WS 消息 → `human_answer`/`interrupt` 直接处理，`user_message` 推入 `agent.input.push()`
- `forwarder`：从 dispatcher 订阅 asyncio.Queue 拉取 chunk，转发到 WS
- 不再使用 `asyncio.Queue` 传递消息给 agent

### 18.5 Team 群聊 WebSocket

- 新端点：`WS /api/ws/team/{team_name}`
- 新文件：`backend/api/team_ws.py`
- 订阅所有成员 Agent 的 dispatcher，合并输出（标注 `source_agent`）
- `@agent_name` mention 路由：解析 → 去前缀 → 推入对应 Agent 的 input queue
- 前端 TeamChatWindow：`@` 触发成员下拉自动补全，agent 颜色编码消息

### 18.6 前端 Store 新状态

| 状态 | 类型 | 用途 |
|------|------|------|
| `agentStates` | `Record<string, State>` | 每个 Agent 的运行状态（唯一真相来源，所有UI决策基于此） |
| `agentSessions` | `Record<string, SessionInfo[]>` | 每个 Agent 的会话列表 |

### 18.7 Agent 响应增强

`GET /api/agents` 和 `GET /api/agents/{name}` 响应新增字段：
- `state`: 运行时状态（`ready`/`waiting`/`running`/`error`）
- `currentSessionId`: 当前活跃会话 UUID

### 18.8 WebSocket 新消息类型

| 方向 | Type | 说明 |
|------|------|------|
| Backend → Frontend | `agent_state` | `{state: "waiting", session_id: "..."} ` |
| Team Backend → Frontend | (所有类型) | 均附加 `source_agent` 字段 |

---

## 十九、近期更新 (2026-06-01) — 启动优化

### 19.1 懒加载架构

Agent 加载拆分为两个阶段：

**Phase 1 — Load（快速，并行）**：
- `_load_agents()` 使用 `asyncio.to_thread()` 并行加载所有 Agent
- 仅实例化 Model + Session，不构建 Tools/Skills/Hooks/Timers
- YAML 解析一次，提取 metadata 缓存到 `_agent_tool_metas` 等字段
- Agent 返回 `state: "ready"`（前端显示灰色圆点）

**Phase 2 — Start（按需触发）**：
- 用户点击 ▶ → `POST /api/agents/{name}/start` → `_lazy_init_agent()` 一次性初始化
- 内置工具通过 `asyncio.to_thread()` 并行构建
- MCP 工具并行连接（15s 超时）
- 初始化完成后启动 event loop

### 19.2 移除启动时自动启动

`start_all_agents()` 已从 `lifespan` 中移除。Agent 启动后均为 `Ready` 状态，用户手动点击 ▶ 启动。

### 19.3 `get_agent_config` 从缓存读取

当 Agent 尚未启动（`agent.tools` 为空）时，`toolIds` / `skillIds` 从缓存的 `_agent_configs` 中读取，确保前端在任何时候都能看到正确的工具/技能列表。

### 19.4 缓存生命周期

| 操作 | 行为 |
|------|------|
| 创建 Agent | Metadata 写入缓存，`start_agent()` 触发 lazy init |
| 更新 toolIds/skillIds | config 刷新，`_agent_started` 移除（下次 start 重新构建） |
| 删除 Agent | 所有缓存清理 |

---

## 二十、近期更新 (2026-06-01) — 持久 WebSocket 连接

### 20.1 单一持久 WS 连接

Chat WebSocket 从 per-agent 模式（`WS /api/ws/chat/{agent_name}`）改为单一持久连接（`WS /api/ws/chat`）。前端切换 Agent 时发送 `{"type": "switch_agent", "agent_name": "..."}`，后端在 Dispatcher 层切换订阅，forwarder 通过 sentinel 机制无缝切换消费队列。

**优势**：
- 消除 TCP 重连开销（~50-200ms）
- 避免快速切换 Agent 时的竞态条件
- 支持自动重连（指数退避：1s → 2s → 4s → ... → 30s max）

### 20.2 AgentOutputDispatcher Round Buffer

`AgentOutputDispatcher` 维护当前 round 的 chunk 缓冲（`_round_buffer`，容量 500 条 / 500 KB）。新订阅者使用 `subscribe(replay=True)` 时，先回放缓冲中的所有 chunks，再接收实时 chunks。确保切换回正在流式输出的 Agent 时，能完整回放当前轮次的所有消息。

### 20.3 队列切换 Sentinel

`unsubscribe()` 时向订阅者队列推送 sentinel 对象（`_SWITCH`）。forwarder 检测到 sentinel 后继续循环，重新读取 `holder.queue` 引用（已被 `subscribe_to` 替换为新队列），实现零延迟切换。

### 20.4 前端自动重连

`ChatWindow` 在 mount 时创建一次 WebSocket。断开时自动重连并重新发送 `switch_agent`。`streamBufferRef` 在每次 Agent 切换和 Session 切换时重置，防止跨 Agent 文本污染。

### 20.5 历史消息字段对齐

`GET /api/agents/{name}/messages` 现在返回的消息格式与 WebSocket 流式 chunks 完全一致：
- `thinking` → `chunkType: "thinking"` 的 system 消息
- `tool_use` → `chunkType: "tool_use"`，`content` 为序列化 JSON
- `tool_result` → `chunkType: "tool_result"`

确保 `MessageBubble` 组件对历史消息和实时消息的渲染逻辑完全一致。

---

## 二十一、近期更新 (2026-06-01) — 全局错误边界

### 21.1 ErrorBoundary 组件

新增 `src/components/ErrorBoundary.tsx`，全局 React 错误边界：
- 捕获子组件渲染错误
- 显示友好的错误页面（红色图标 + 错误信息 + Reload 按钮）
- 在 `App.tsx` 中包裹 `AppContent`

### 21.2 ConfirmDialog 组件

新增 `src/components/ConfirmDialog.tsx`，通用三按钮确认对话框：
- 支持 confirm / secondary / cancel 三个操作
- `variant="danger"` 时 confirm 按钮显示红色
- 用于 Agent 删除确认（Yes = 删除+源文件，No = 仅删除记录，Cancel = 取消）

### 21.3 组件文件结构重组

所有组件按功能分类到子目录：
- `components/agents/` — Agent/Team 相关
- `components/chat/` — 聊天相关
- `components/common/` — 通用组件（FolderPicker, ConfirmDialog）
- `components/config/` — 配置模块
- `components/layout/` — 布局组件
- `components/onboarding/` — 引导页
- `components/settings/` — Settings Popover
- `components/workspace/` — 工作区面板

---

## 二十二、API 端点汇总表

### REST API

| 方法 | 路径 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | `/api/models` | 列出所有模型 | - | `ModelConfig[]` |
| POST | `/api/models` | 创建模型 | `ModelConfig` | `ModelConfig` |
| PUT | `/api/models/{id}` | 更新模型 | 部分 `ModelConfig` | `ModelConfig` |
| DELETE | `/api/models/{id}` | 删除模型 | - | `{success: true}` |
| POST | `/api/models/{id}/test` | 测试模型 | `{prompt: string}` | `{content: string}` |
| GET | `/api/mcps` | 列出所有 MCP | - | `MCPServerConfig[]` |
| POST | `/api/mcps` | 创建 MCP | `MCPServerConfig` | `MCPServerConfig` |
| PUT | `/api/mcps/{name}` | 更新 MCP | 部分 `MCPServerConfig` | `MCPServerConfig` |
| DELETE | `/api/mcps/{name}` | 删除 MCP | - | `{success: true}` |
| POST | `/api/mcps/{name}/discover` | 发现 MCP 工具 | - | `{tools: [...]}` |
| POST | `/api/mcps/import` | 导入 MCP | `{path: string}` | `{imported: int}` |
| GET | `/api/prompts` | 列出所有 Prompt | - | `PromptConfig[]` |
| POST | `/api/prompts` | 创建 Prompt | `PromptConfig` | `PromptConfig` |
| PUT | `/api/prompts/{id}` | 更新 Prompt | 部分 `PromptConfig` | `PromptConfig` |
| DELETE | `/api/prompts/{id}` | 删除 Prompt | - | `{success: true}` |
| POST | `/api/prompts/import` | 导入 Prompt | `{path: string, group?: string}` | `{imported: int}` |
| GET | `/api/skills` | 列出所有 Skill | - | `SkillConfig[]` |
| POST | `/api/skills/import` | 导入 Skill | `{path: string}` | `{imported: int, skills: [...]}` |
| GET | `/api/agents` | 列出所有 Agent | - | `AgentConfig[]` (含 state, currentSessionId) |
| GET | `/api/agents/{name}` | 获取 Agent 详情 | - | `AgentConfig` (含 state, currentSessionId) |
| POST | `/api/agents` | 创建 Agent | `AgentConfig` | `AgentConfig` (含生成的 name) |
| PUT | `/api/agents/{name}` | 更新 Agent | 部分字段 | `AgentConfig` |
| DELETE | `/api/agents/{name}?delete_files=true/false` | 删除 Agent | - | `{success: true}` |
| POST | `/api/agents/{name}/start` | 启动 Agent | - | `{state, session_id}` |
| POST | `/api/agents/{name}/stop` | 停止 Agent | - | `{state, session_id}` |
| GET | `/api/agents/{name}/state` | 查询状态 | - | `{state, session_id}` |
| GET | `/api/agents/{name}/sessions` | 列会话 | - | `SessionInfo[]` |
| POST | `/api/agents/{name}/sessions/{id}/switch` | 切换会话 | - | `{session_id, status}` |
| POST | `/api/agents/{name}/sessions/new` | 新建会话 | - | `{session_id}` |
| GET | `/api/agents/{name}/messages` | 加载历史 | - | `Message[]` |
| GET | `/api/teams` | 列出所有 Team | - | `TeamConfig[]` |
| GET | `/api/teams/{name}` | 获取 Team 详情 | - | `TeamConfig` |
| POST | `/api/teams` | 创建 Team | `CreateTeamRequest` | `TeamConfig + members` |
| PUT | `/api/teams/{name}` | 更新 Team | 部分 `TeamConfig` | `TeamConfig` |
| DELETE | `/api/teams/{name}` | 删除 Team | - | `{success: true}` |
| POST | `/api/teams/{name}/start` | 启动 Team | - | `{state: str}` |
| POST | `/api/teams/{name}/stop` | 停止 Team | - | `{state: str}` |
| GET | `/api/files/tree?path=` | 获取目录树 | - | `FileNode` |
| GET | `/api/files/read?path=` | 读取文件 | - | `{content, mimeType, name, path}` |
| GET | `/api/files/raw?path=` | 原始文件 | - | 原始内容 |
| POST | `/api/files/write` | 写入文件 | `{path, content}` | `{success: true}` |
| GET | `/api/files/dirs?path=` | 列出子目录 | - | `{current, parent, separator, directories}` |
| GET | `/api/state` | 获取 UI 状态 | - | `UIState` |
| POST | `/api/state` | 保存 UI 状态 | `UIState` | `UIState` |

### WebSocket API

| 端点 | 方向 | 消息类型 | 字段 | 描述 |
|------|------|---------|------|------|
| `WS /api/ws/chat` | Frontend → Backend | `switch_agent` | `agent_name: string` | 切换订阅的 Agent |
| `WS /api/ws/chat` | Frontend → Backend | `user_message` | `content: string` | 发送用户消息 |
| `WS /api/ws/chat` | Frontend → Backend | `human_answer` | `content: string` | 回答 ask_human 问题 |
| `WS /api/ws/chat` | Frontend → Backend | `interrupt` | - | 中断 Agent |
| `WS /api/ws/chat` | Backend → Frontend | `switched` | `agent_name, agent_state` | 切换确认 |
| `WS /api/ws/chat` | Backend → Frontend | `text` | `content, message_id?` | 流式文本 |
| `WS /api/ws/chat` | Backend → Frontend | `thinking` | `content` | 思考过程 |
| `WS /api/ws/chat` | Backend → Frontend | `completed_tool_use` | `content: {name, input}` | 工具调用 |
| `WS /api/ws/chat` | Backend → Frontend | `tool_results` | `content: [...]` | 工具结果 |
| `WS /api/ws/chat` | Backend → Frontend | `completed_message` | `content` | 消息完成 |
| `WS /api/ws/chat` | Backend → Frontend | `human_question` | `content` | 向用户提问 |
| `WS /api/ws/chat` | Backend → Frontend | `agent_state` | `state` | 状态变更 |
| `WS /api/ws/chat` | Backend → Frontend | `interrupted` | - | 中断确认 |
| `WS /api/ws/chat` | Backend → Frontend | `error` | `content` | 错误信息 |
| `WS /api/ws/team/{name}` | Frontend → Backend | `user_message` | `content, mentions?` | 发送团队消息 |
| `WS /api/ws/team/{name}` | Backend → Frontend | `text` | `content, source_agent` | 成员流式文本 |
| `WS /api/ws/team/{name}` | Backend → Frontend | `thinking` | `content, source_agent` | 成员思考过程 |
| `WS /api/ws/team/{name}` | Backend → Frontend | `system` | `content` | 系统消息 |
| `WS /api/ws/team/{name}` | Backend → Frontend | `error` | `content, source_agent` | 成员错误 |

---

## v1.3 — Unified ID URL 变更（2026-06-04）

> 配套设计文档：[`issue/unified-id-design.md`](../issue/unified-id-design.md)

### URL 路径总览

| 旧路径 | 新路径 | 说明 |
|---|---|---|
| `GET /api/agents/{name}` | `GET /api/agents/{id}` | 后端 `_resolve_agent` 也接受 name（fallback） |
| `PUT /api/agents/{name}` | `PUT /api/agents/{id}` | |
| `DELETE /api/agents/{name}` | `DELETE /api/agents/{id}` | |
| `POST /api/agents/{name}/start` | `POST /api/agents/{id}/start` | |
| `POST /api/agents/{name}/stop` | `POST /api/agents/{id}/stop` | |
| `GET /api/agents/{name}/state` | `GET /api/agents/{id}/state` | |
| `GET /api/agents/{name}/sessions` | `GET /api/agents/{id}/sessions` | |
| `POST /api/agents/{name}/sessions/{sid}/switch` | `POST /api/agents/{id}/sessions/{sid}/switch` | |
| `POST /api/agents/{name}/sessions/new` | `POST /api/agents/{id}/sessions/new` | |
| `GET /api/agents/{name}/messages` | `GET /api/agents/{id}/messages` | |
| `GET /api/teams/{name}` | `GET /api/teams/{id}` | |
| `PUT /api/teams/{name}` | `PUT /api/teams/{id}` | |
| `DELETE /api/teams/{name}` | `DELETE /api/teams/{id}` | |
| `POST /api/teams/{name}/start` | `POST /api/teams/{id}/start` | |
| `POST /api/teams/{name}/stop` | `POST /api/teams/{id}/stop` | |
| `PUT /api/mcps/{name}` | `PUT /api/mcps/{id}` | |
| `DELETE /api/mcps/{name}` | `DELETE /api/mcps/{id}` | |
| `POST /api/mcps/{name}/discover` | `POST /api/mcps/{id}/discover` | |
| `WS /api/ws/team/{name}` | `WS /api/ws/team/{id}` | team chat 走 id |

### 新增 / 调整字段

- `AgentConfig.id`、`TeamConfig.id`、`MCPServerConfig.id`、`SkillConfig.id`、`ToolConfig.id`：UUID
- `AgentConfig.toolIds`：ToolConfig.id（UUID）列表
- `AgentConfig.skillIds`：SkillConfig.id（UUID）列表
- `UIState.currentAgentName` → `UIState.currentAgentId`
- `UIState.currentTeamName` → `UIState.currentTeamId`
- `GET /api/tools` 响应里每条 tool 现在带 `id`（template_id）、`source`、`mcpServerId` 字段
- `TeamSummary` 加 `id` 字段

### 前端 API client 变更

`frontend/src/lib/api.ts` 所有方法参数从 `name: string` 改为 `id: string`（同名 / 别名）。Store 在内部按 name 查 id 后再发请求。ChatWindow、TeamChatWindow 在打开 socket 时使用 `agent.id` / `team.id`。

---

*文档版本：v1.4*
*更新日期：2026-06-08*

---

## 十、全局 Session 管理

### 10.1 列出所有 Session

**前端动作**：打开 Session Manager 页面

**后端调用**：`GET /api/sessions?agent_id={可选}`

**响应**：
```json
[
  {
    "session_id": "2026-06-08_03-20-50_0ab4e3e7a1b2c3d4",
    "agent_id": "5903a57a-...",
    "agent_name": "Coder",
    "timestamp": "2026-06-08_03-20-50",
    "turn_count": 5,
    "is_active": true,
    "parent_session_id": "",
    "fork_turn_index": -1,
    "session_dir": "/path/to/session/dir"
  }
]
```

**状态更新**：`listAllSessions` → 存入全局 session 列表

### 10.2 获取 Session 详情

**前端动作**：点击某个 session 展开详情

**后端调用**：`GET /api/sessions/{session_id}`

**响应**：
```json
{
  "sessionId": "2026-06-08_03-20-50_0ab4e3e7a1b2c3d4",
  "agentId": "5903a57a-...",
  "agentName": "Coder",
  "timestamp": "2026-06-08_03-20-50",
  "turnCount": 5,
  "parentSessionId": "",
  "forkTurnIndex": -1,
  "turns": [
    {
      "index": 0,
      "userMessage": "帮我写一个排序算法",
      "tokenCount": 150,
      "everUsedTools": ["bash", "read_file"],
      "startTimestamp": 1749361250,
      "endTimestamp": 1749361260,
      "messageCount": 4
    }
  ]
}
```

**说明**：`turns` 只包含已完成的 turn（`is_complete=True`），`userMessage` 为该 turn 中第一条用户消息的文本预览（截取前 120 字符）。

### 10.3 Fork Session

**前端动作**：点击某个 turn 末尾的 "Fork" 按钮 → 确认对话框（可选目标 agent）

**后端调用**：`POST /api/sessions/{session_id}/fork`

**请求体**（SessionForkRequest）：
```json
{
  "turnIndex": 2,
  "targetAgentId": "可选"
}
```

**响应**：
```json
{
  "sessionId": "2026-06-08_...",
  "agentId": "...",
  "turnCount": 3,
  "parentSessionId": "2026-06-08_03-20-50_0ab4e3e7a1b2c3d4",
  "forkTurnIndex": 2
}
```

### 10.4 重建索引

**前端动作**：管理员操作

**后端调用**：`POST /api/sessions/reindex`

**响应**：`{ "ok": true }`

### 10.5 删除 Session

**前端动作**：点击删除按钮 → 确认对话框

**后端调用**：`DELETE /api/sessions/{session_id}`

**后端行为**：不允许删除当前活跃 session（返回 409），否则删除文件并移除索引

**响应**：`{ "ok": true }`
