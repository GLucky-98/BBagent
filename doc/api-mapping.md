# BBagent API Mapping Documentation v7

## 1. Overview

本文档描述 BBagent 后端提供的所有 REST API 和 WebSocket 接口。

所有 API 路径前缀为 `/api`。资源标识统一使用 `id`（UUID），`name` 仅作显示名。

> **最后更新**：2026-06-15 — 对齐当前代码库，新增 tools、hooks、sessions、file_watch、team conversations 等端点

---

## 2. Health Check

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | 健康检查，返回 `{"status": "ok"}` |

---

## 3. Models

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/api/models` | 列出所有模型 | — | `ModelConfig[]` |
| POST | `/api/models` | 创建模型 | `ModelConfig` | `ModelConfig` |
| PUT | `/api/models/{model_id}` | 更新模型（热更新受影响 Agent） | `dict` (partial) | `ModelConfig & {affectedAgents: string[]}` |
| DELETE | `/api/models/{model_id}` | 删除模型（先停止受影响 Agent） | — | `{success: bool, affectedAgents: string[]}` |
| POST | `/api/models/{model_id}/test` | 测试模型连接 | `{prompt: string}` | `{content: string}` |

**ModelConfig 字段**：

| Field | Type | Description |
|-------|------|-------------|
| id | string | UUID |
| name | string | 显示名 |
| provider | "anthropic" \| "openai" | 模型提供商 |
| modelName | string | 模型名称 |
| apiKey | string | API Key |
| baseUrl | string | API Base URL |
| maxContextTokens | int | 最大上下文 token |
| maxCompletionTokens | int | 最大输出 token |
| temperature | float | 温度参数 |
| topP | float | Top-P 参数 |
| thinking | bool | 是否启用思考模式 |

---

## 4. Tools

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/api/tools` | 列出所有工具蓝图 | — | `ToolConfig[]` |

**ToolConfig 字段**：

| Field | Type | Description |
|-------|------|-------------|
| id | string | UUID (template_id) |
| name | string | 显示名 |
| source | "built_in" \| "hook" \| "mcp" \| "team" | 工具来源 |
| description | string | 工具描述 |
| mcpServerId | string \| null | MCP 服务器 ID（仅 MCP 工具） |
| mcpServerName | string \| null | MCP 服务器名称（仅 MCP 工具，API 响应附加） |

---

## 5. Hooks

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/api/hooks` | 列出所有 Hook 描述符 | — | `HookListResponse` |

**HookListResponse 结构**：

```json
{
  "hooks": [
    {
      "name": "built_in.memory",
      "displayName": "Memory",
      "description": "...",
      "defaultEnabled": true,
      "fieldSections": [
        {
          "title": "Memory Settings",
          "fields": [
            {"key": "max_inject", "type": "number", "label": "Max Inject", "default": 5, "description": "..."}
          ]
        }
      ]
    }
  ],
  "sharedSections": [
    {
      "title": "Shared Settings",
      "fields": [...]
    }
  ]
}
```

---

## 6. MCP Servers

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/api/mcps` | 列出所有 MCP 服务器 | — | `MCPServerConfig[]` |
| POST | `/api/mcps` | 创建 MCP 服务器 | `MCPServerConfig` | `MCPServerConfig` |
| PUT | `/api/mcps/{mcp_id}` | 更新 MCP 服务器 | `dict` (partial) | `MCPServerConfig & {hint: string}` |
| DELETE | `/api/mcps/{mcp_id}` | 删除 MCP 服务器 | — | `{success: bool}` |
| POST | `/api/mcps/{mcp_id}/discover` | 重新发现 MCP 工具 | — | `MCPServerConfig` |
| POST | `/api/mcps/import` | 从路径导入 MCP 配置 | `{path: string}` | `{success: bool, imported: int, skipped: int}` |

**MCPServerConfig 字段**：

| Field | Type | Description |
|-------|------|-------------|
| id | string | UUID |
| name | string | 显示名 |
| command | string | 启动命令 |
| args | string[] | 命令参数 |
| env | dict | 环境变量 |
| tools | ToolConfig[] | 已发现的工具列表 |

---

## 7. Prompts

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/api/prompts` | 列出所有 Prompt | — | `PromptConfig[]` |
| POST | `/api/prompts` | 创建 Prompt | `PromptConfig` | `PromptConfig` |
| PUT | `/api/prompts/{prompt_id}` | 更新 Prompt | `dict` (partial) | `PromptConfig` |
| DELETE | `/api/prompts/{prompt_id}` | 删除 Prompt | — | `{success: bool}` |
| POST | `/api/prompts/import` | 从目录导入 Prompt | `{path: string, group: string}` | `{success: bool, imported: int, skipped: int}` |

**PromptConfig 字段**：

| Field | Type | Description |
|-------|------|-------------|
| id | string | UUID |
| name | string | 显示名 |
| content | string | Prompt 内容 |
| group | string | 分组名 |

---

## 8. Skills

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/api/skills` | 列出所有 Skill | — | `SkillConfig[]` |
| POST | `/api/skills/import` | 从路径导入 Skill | `{path: string}` | `{success: bool, imported: int, skipped: int, items: string[], skipped_items: string[]}` |
| DELETE | `/api/skills/{skill_id}` | 删除 Skill | — | `{success: bool}` |
| POST | `/api/skills/{skill_id}/refresh` | 刷新 Skill | — | `SkillConfig` |

**SkillConfig 字段**：

| Field | Type | Description |
|-------|------|-------------|
| id | string | UUID |
| name | string | 显示名 |
| description | string | 描述 |
| path | string | 文件路径 |

---

## 9. Agents

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/api/agents` | 列出所有 Agent | — | `AgentConfig[]` (含 state, currentSessionId, contextTokens) |
| GET | `/api/agents/{agent_id}` | 获取 Agent 详情 | — | `AgentConfig` (含 state, currentSessionId, contextTokens) |
| POST | `/api/agents` | 创建 Agent | `AgentConfig` | `AgentConfig` (含 state, currentSessionId, contextTokens) |
| PUT | `/api/agents/{agent_id}` | 更新 Agent | `dict` (partial) | `Agent` |
| DELETE | `/api/agents/{agent_id}` | 删除 Agent | Query: `delete_files=true` (可选) | `{success: bool}` |
| POST | `/api/agents/{agent_id}/start` | 启动 Agent | — | `{success: bool}` |
| POST | `/api/agents/{agent_id}/stop` | 停止 Agent | — | `{success: bool}` |
| GET | `/api/agents/{agent_id}/state` | 获取 Agent 状态 | — | `{state, session_id, context_tokens}` |
| GET | `/api/agents/{agent_id}/sessions` | 列出 Agent 的 Session | — | `SessionInfo[]` |
| POST | `/api/agents/{agent_id}/sessions/{session_id}/switch` | 切换 Session | — | `{success: bool}` |
| POST | `/api/agents/{agent_id}/sessions/new` | 创建新 Session | — | `{session_id: string}` |
| GET | `/api/agents/{agent_id}/messages` | 获取当前 Session 消息 | — | `Message[]` |
| GET | `/api/agents/{agent_id}/timers` | 列出定时器 | — | `TimerConfig[]` |
| POST | `/api/agents/{agent_id}/timers` | 创建定时器 | `{name, seconds, hint, enabled}` | `TimerConfig` |
| PUT | `/api/agents/{agent_id}/timers/{name}` | 更新定时器 | `dict` (partial) | `TimerConfig` |
| POST | `/api/agents/{agent_id}/timers/{name}/start` | 启动定时器 | — | `TimerConfig` |
| POST | `/api/agents/{agent_id}/timers/{name}/stop` | 停止定时器 | — | `TimerConfig` |
| DELETE | `/api/agents/{agent_id}/timers/{name}` | 删除定时器 | — | `{success: bool}` |

**AgentConfig 字段**：

| Field | Type | Description |
|-------|------|-------------|
| id | string | UUID（后端生成） |
| name | string | 显示名 |
| modelId | string | 模型 ID |
| systemPrompt | string | 系统提示词 |
| workingDir | string | 工作目录（映射到 toolPolicy.cwd） |
| baseDir | string | 基础目录（后端自动生成，只读） |
| toolIds | string[] | 工具 ID 列表（UUID） |
| skillIds | string[] | 技能 ID 列表（UUID） |
| toolPolicy | dict | 工具策略 |
| hookNames | string[] | 启用的 Hook 列表 |
| hookConfig | dict | Hook 配置 |
| timers | TimerConfig[] | 定时器列表 |
| lastSessionId | string | 上次 Session ID |

**Agent 列表/详情响应附加字段**：

| Field | Type | Description |
|-------|------|-------------|
| state | "ready" \| "waiting" \| "running" \| "error" | Agent 运行状态 |
| currentSessionId | string | 当前 Session ID |
| contextTokens | int | 当前上下文 token 数 |

**toolPolicy 支持的字段**：

| Field | Type | Description |
|-------|------|-------------|
| maxReadSize | int | 最大读取大小 |
| bashMaxOutputSize | int | Bash 最大输出大小 |
| bashDefaultTimeout | int | Bash 默认超时 |
| webTimeout | int | Web 请求超时 |
| webMaxResponseSize | int | Web 最大响应大小 |
| webMaxOutputSize | int | Web 最大输出大小 |
| webSearchMaxResults | int | Web 搜索最大结果数 |
| webAllowedDomains | string[] | Web 允许域名 |
| webUserAgent | string | Web User-Agent |
| subAgentModel | string | 子 Agent 模型 ID |
| subAgentBlockedTools | string[] | 子 Agent 禁用工具 |

---

## 10. Teams

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/api/teams` | 列出所有 Team | — | `TeamConfig[]` (含 state) |
| GET | `/api/teams/{team_id}` | 获取 Team 详情 | — | `TeamConfig` (含 state) |
| POST | `/api/teams` | 创建 Team | `CreateTeamRequest` | `TeamConfig` |
| PUT | `/api/teams/{team_id}` | 更新 Team | `dict` (partial, 含 deleteRemovedMemberIds) | `Team` |
| DELETE | `/api/teams/{team_id}` | 删除 Team | — | `{success: bool}` |
| POST | `/api/teams/{team_id}/start` | 启动 Team | — | `{success: bool}` |
| POST | `/api/teams/{team_id}/stop` | 停止 Team | — | `{success: bool}` |
| GET | `/api/teams/{team_id}/messages` | 获取 Team 消息 | — | `TeamMessage[]` |
| GET | `/api/teams/{team_id}/conversations` | 列出 Team 对话 | — | `Conversation[]` |
| POST | `/api/teams/{team_id}/conversations` | 创建 Team 对话 | `{name?: string}` | `Conversation` |
| POST | `/api/teams/{team_id}/conversations/{conversation_id}/load` | 加载 Team 对话 | — | `Conversation` |
| DELETE | `/api/teams/{team_id}/conversations/{conversation_id}` | 删除 Team 对话 | — | `{success: bool}` |

**TeamConfig 字段**：

| Field | Type | Description |
|-------|------|-------------|
| id | string | UUID |
| name | string | 显示名 |
| teamDescription | string | Team 描述 |
| workingDir | string | 工作目录 |
| baseDir | string | 基础目录 |
| memberIds | string[] | 成员 Agent ID 列表 |
| contacts | dict | 成员间通信配置 |
| started | bool | 是否已启动 |

**CreateTeamRequest 字段**：

| Field | Type | Description |
|-------|------|-------------|
| name | string | Team 名称 |
| teamDescription | string | Team 描述 |
| workingDir | string | 工作目录 |
| members | AgentConfig[] | 成员 Agent 配置列表 |
| contacts | dict | 成员间通信配置 |

**UpdateTeamPayload 附加字段**：

| Field | Type | Description |
|-------|------|-------------|
| deleteRemovedMemberIds | string[] | 需要删除的成员 Agent ID 列表 |

---

## 11. Sessions (Global)

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/api/sessions` | 全局 Session 列表 | Query: `agent_id` (可选) | `GlobalSessionIndex[]` |
| GET | `/api/sessions/{session_id}` | Session 详情 + turn 摘要 | — | `SessionDetail` |
| POST | `/api/sessions/{session_id}/fork` | 从指定 turn fork Session | `{turnIndex: int, targetAgentId?: string}` | `{session_id: string, agent_id: string}` |
| POST | `/api/sessions/reindex` | 重建全局 Session 索引 | — | `{ok: bool}` |
| DELETE | `/api/sessions/{session_id}` | 删除 Session | — | `{ok: bool}` |

**GlobalSessionIndex 字段**：

| Field | Type | Description |
|-------|------|-------------|
| session_id | string | Session ID |
| agent_id | string | 所属 Agent ID |
| agent_name | string | Agent 显示名 |
| timestamp | string | 创建时间 |
| turn_count | int | Turn 数量 |
| is_active | bool | 是否为当前活跃 Session |
| parent_session_id | string | 父 Session ID（fork 来源） |
| fork_turn_index | int | Fork 的 turn 位置 |

**SessionDetail 字段**：

| Field | Type | Description |
|-------|------|-------------|
| sessionId | string | Session ID |
| agentId | string | Agent ID |
| agentName | string | Agent 显示名 |
| timestamp | string | 创建时间 |
| turnCount | int | Turn 数量 |
| parentSessionId | string | 父 Session ID |
| forkTurnIndex | int | Fork 的 turn 位置 |
| turns | TurnInfo[] | Turn 摘要列表 |

**TurnInfo 字段**：

| Field | Type | Description |
|-------|------|-------------|
| index | int | Turn 索引 |
| userMessage | string | 用户消息摘要 |
| tokenCount | int | Token 数量 |
| everUsedTools | string[] | 使用过的工具 |
| startTimestamp | int | 开始时间戳 |
| endTimestamp | int | 结束时间戳 |
| messageCount | int | 消息数量 |

---

## 12. Files

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/api/files/tree` | 获取文件树 | Query: `path`, `depth` (可选) | `FileNode` |
| GET | `/api/files/read` | 读取文件内容 | Query: `path` | `{content, mimeType, name, path}` |
| GET | `/api/files/raw` | 获取原始文件（二进制/文本） | Query: `path` | Response (binary/text) |
| POST | `/api/files/write` | 写入文件 | `{path, content}` | `{success: bool}` |
| GET | `/api/files/dirs` | 列出目录 | Query: `path` | `{current, parent, separator, directories}` |
| POST | `/api/files/open` | 在系统文件管理器中打开 | `{path}` | `{success: bool}` |
| POST | `/api/files/dirs` | 创建目录 | `{path}` | `{success: bool, path}` |
| PUT | `/api/files/dirs` | 重命名/移动目录 | `{oldPath, newPath}` | `{success: bool, path}` |
| DELETE | `/api/files/dirs` | 删除目录 | Query: `path`, `recursive` | `{success: bool}` |

**FileNode 字段**：

| Field | Type | Description |
|-------|------|-------------|
| name | string | 文件/目录名 |
| path | string | 完整路径 |
| type | "file" \| "directory" | 类型 |
| children | FileNode[] | 子节点（仅目录） |
| size | int \| null | 文件大小 |
| extension | string \| null | 文件扩展名 |
| modifiedAt | int \| null | 修改时间戳 |

---

## 13. UI State

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/api/state` | 获取 UI 状态 | — | `UIState` |
| POST | `/api/state` | 保存 UI 状态 | `UIState` | `{success: bool}` |

**UIState 字段**：

| Field | Type | Description |
|-------|------|-------------|
| currentTab | "agent" \| "team" | 当前标签页 |
| currentAgentId | string \| null | 当前 Agent ID |
| currentTeamId | string \| null | 当前 Team ID |
| settingsOpen | bool | Settings 是否打开 |
| settingsTab | string | Settings 当前 Tab |
| workingDirPath | string | 工作目录路径 |

---

## 14. WebSocket Endpoints

### 14.1 Chat WebSocket

**路径**：`WS /api/ws/chat`

**前端 → 后端消息**：

| Type | Payload | Description |
|------|---------|-------------|
| `switch_agent` | `{agent_id: string, agent_name: string}` | 切换订阅的 Agent |
| `user_message` | `{content: string}` | 发送用户消息 |
| `human_answer` | `{content: string}` | 回答 Agent 提问 |
| `interrupt` | — | 中断 Agent 执行 |

**后端 → 前端消息**：

| Type | Payload | Description |
|------|---------|-------------|
| `switched` | `{agent_name, agent_state, context_tokens}` | Agent 切换完成 |
| `agent_state` | `{state, context_tokens}` | Agent 状态变化 |
| `text` | `{content}` | 流式文本块 |
| `thinking` | `{content}` | 思考/推理块 |
| `completed_tool_use` | `{...}` | 工具调用完成 |
| `tool_results` | `{...}` | 工具执行结果 |
| `completed_message` | `{content, stop_reason}` | 完整消息完成 |
| `human_question` | `{...}` | Agent 向用户提问 |
| `error` | `{message}` | 错误信息 |

### 14.2 Team Chat WebSocket

**路径**：`WS /api/ws/team/{team_id}`

**前端 → 后端消息**：

| Type | Payload | Description |
|------|---------|-------------|
| `team_message` | `{content, mentions}` | 发送 Team 消息（含 @mention） |

**后端 → 前端消息**：

| Type | Payload | Description |
|------|---------|-------------|
| `team_message` | `{fromAgent, toAgent, content, type}` | 路由后的 Team 消息 |
| `agent_state` | `{agent_id, state}` | 成员 Agent 状态变化 |

### 14.3 File Watch WebSocket

**路径**：`WS /api/ws/files`

**前端 → 后端消息**：

| Type | Payload | Description |
|------|---------|-------------|
| `watch` | `{path: string}` | 开始监控指定路径 |
| `unwatch` | `{path: string}` | 停止监控指定路径 |

**后端 → 前端消息**：

| Type | Payload | Description |
|------|---------|-------------|
| `file_change` | `{event_type, path, is_directory}` | 文件变化事件 |

**忽略规则**：
- 目录：`.git`, `__pycache__`, `node_modules`, `.venv`, `dist`, `build` 等
- 后缀：`.pyc`, `.pyo`, `.swp`, `.tmp`, `.temp`
- 事件类型：`opened`, `closed`, `closed_no_write`
- 防抖：0.5 秒

---

## 15. Error Response Format

所有 API 错误返回统一格式：

```json
{
  "error": {
    "code": "AGENT_NOT_FOUND",
    "message": "Agent 'xxx' not found",
    "detail": "..."  // 可选
  }
}
```

**常见错误码**：

| Code | HTTP Status | Description |
|------|-------------|-------------|
| AGENT_NOT_FOUND | 404 | Agent 不存在 |
| AGENT_ALREADY_RUNNING | 409 | Agent 已在运行 |
| AGENT_NOT_RUNNING | 409 | Agent 未运行 |
| MODEL_NOT_FOUND | 404 | Model 不存在 |
| SESSION_NOT_FOUND | 404 | Session 不存在 |
| TEAM_NOT_FOUND | 404 | Team 不存在 |
| MCP_NOT_FOUND | 404 | MCP 服务器不存在 |
| SKILL_NOT_FOUND | 404 | Skill 不存在 |
| PROMPT_NOT_FOUND | 404 | Prompt 不存在 |
| TEAM_CONVERSATION_LOCKED | 409 | Team 对话锁定中，不允许切换 session |
| VALIDATION_ERROR | 400 | 请求验证失败 |
| FILE_NOT_FOUND | 404 | 文件不存在 |
| INTERNAL_ERROR | 500 | 内部错误 |
