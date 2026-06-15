# BBagent Frontend Design Documentation v7

## 1. Overview

### 1.1 Project Introduction

BBagent Frontend 是一个基于 React 18 + TypeScript 的单页应用（SPA），为 BBagent 多代理系统提供可视化交互界面。

本版本（v7）对架构进行了重大更新：
- 移除左侧导航栏，改为**顶部导航栏**（类浏览器标签页）
- 核心区采用**三栏动态布局**：文件面板（上下分屏） + 对话窗口 + 文件预览（条件显示）
- 配置项全部收进 **Settings Popover**，不占用工作区空间
- 新增 **Onboarding 引导页**，帮助新用户完成初始化流程
- 配置页面对齐 **BBagent 基础库**数据结构：Model 按 provider 区分字段、Agent 支持 tools/skills 勾选、Team 三步配置流程、MCP/Skill/Prompt 支持文件夹导入
- Agent 标识统一使用 `id`（UUID 机器标识），`name` 仅作显示名（unified-id 设计）
- AgentConfigDialog 重新设计为双栏布局（左侧基础配置，右侧 Tools + Policy）
- 新增全局 **Session Manager** 面板，支持跨 Agent 的 session 列表、fork、删除
- 新增 **Team Conversation** 面板，支持 Team 级别的对话管理
- 新增 **File Watch** WebSocket，实时监控文件变化
- 新增 **Template Import/Export**，支持 Agent/Team 配置的导入导出
- 新增 **Toast 通知**组件
- 新增 **MarkdownContent** 组件，统一 Markdown 渲染

> **最后更新**：2026-06-15 — 重构文档对齐当前代码库，更新文件结构、类型定义、API client、Store 状态

### 1.2 Tech Stack

| Category | Technology | Version |
|---------|-----------|---------|
| Framework | React | 18.x |
| Language | TypeScript | 5.x |
| Build Tool | Vite | 8.x |
| Styling | Tailwind CSS | 4.x |
| State Management | Zustand | 5.x |
| Icons | Lucide React | Latest |
| UI Primitives | Radix UI | Latest |

需要的 Radix UI 组件包：

```
@radix-ui/react-popover       # AgentTab 中 TeamDropdown 的 Trigger
@radix-ui/react-dialog        # Agent 配置弹窗
@radix-ui/react-dropdown-menu # Team 成员下拉菜单
@radix-ui/react-tabs          # Settings 面板内部 Tab 切换
@radix-ui/react-tooltip       # 悬浮提示
```

### 1.3 Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── agents/
│   │   │   ├── AgentConfigDialog.tsx   # 新建/编辑 Agent/Team 弹窗（双栏布局）
│   │   │   ├── AgentTab.tsx            # 单个选项卡（含删除按钮 + ConfirmDialog）
│   │   │   ├── AgentTabs.tsx           # Agent/Team 选项卡列表
│   │   │   └── TeamDropdown.tsx        # Team 成员下拉菜单
│   │   ├── layout/
│   │   │   ├── TopNav.tsx              # 顶部导航栏容器
│   │   │   ├── AppIcon.tsx             # 应用图标 + Settings Popover 触发器
│   │   │   └── UserMenu.tsx            # 用户菜单
│   │   ├── onboarding/
│   │   │   ├── OnboardingView.tsx      # 引导页容器
│   │   │   └── OnboardingStep.tsx      # 单个引导步骤组件
│   │   ├── settings/
│   │   │   └── SettingsPopover.tsx     # Settings Popover（内嵌 4 个 Module）
│   │   ├── workspace/
│   │   │   ├── WorkspaceView.tsx       # 三栏核心工作区容器
│   │   │   ├── PanelA_FilePanel.tsx    # 文件面板（上下分屏容器）
│   │   │   ├── WorkingDirView.tsx      # 上半部分：working dir
│   │   │   ├── BasedirTree.tsx         # 下半部分：basedir 完整项目树
│   │   │   ├── Splitter.tsx            # 可拖拽分割条
│   │   │   ├── PanelC_FilePreview.tsx  # 文件预览面板（条件渲染）
│   │   │   ├── SessionManagerPanel.tsx # 全局 Session 管理面板
│   │   │   ├── TeamGraphView.tsx       # Team 拓扑图/列表视图（React Flow）
│   │   │   └── TeamConversationPanel.tsx # Team 对话管理面板
│   │   ├── ChatWindow.tsx             # 单 Agent 对话窗口
│   │   ├── TeamChatWindow.tsx         # Team 群聊窗口（@mention，颜色编码消息）
│   │   ├── TimerPanel.tsx             # 定时任务管理面板
│   │   ├── MarkdownContent.tsx        # 统一 Markdown 渲染组件
│   │   ├── ToastContainer.tsx         # Toast 通知容器
│   │   ├── ConfirmDialog.tsx          # 通用确认对话框（Yes/No/Cancel）
│   │   ├── FolderPicker.tsx           # 可复用文件夹选择下拉组件
│   │   ├── FolderPickerModal.tsx      # 全屏居中 Modal 文件夹选择器
│   │   ├── TemplatePicker.tsx         # 模板文件选择器
│   │   ├── GroupedPromptPicker.tsx    # 分组 Prompt 选择器
│   │   ├── ErrorBoundary.tsx          # 全局错误边界组件
│   │   ├── ModelsModule.tsx           # Models 模块
│   │   ├── SkillsModule.tsx           # Skills 模块
│   │   ├── MCPsModule.tsx             # MCPs 模块
│   │   └── PromptsModule.tsx          # Prompts 模块
│   ├── hooks/
│   │   └── useGlobalAgentState.ts     # 全局 Agent 状态 hook
│   ├── store/
│   │   └── index.ts                   # Zustand Store
│   ├── types/
│   │   └── index.ts                   # TypeScript 类型定义
│   ├── lib/
│   │   ├── api.ts                     # 后端 API 客户端
│   │   └── utils.ts                   # 工具函数（cn, getMimeType, agentToTemplate, resolveTemplate）
│   ├── App.tsx                        # 根组件
│   └── index.css                      # 全局样式（CSS 变量定义）
├── package.json
└── vite.config.ts
```

---

## 2. Layout Architecture

### 2.1 Overall Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ 🏠 │ [Agent Tab 1 ⚙🗑] [Agent Tab 2 ⚙🗑] [Team Tab ▼ ⚙🗑] [+]    │  👤  │
│    │           Top Navigation Bar (48px)                             │
├────┴──────────────────────────────────────────────────────────────┬──┤
│                      ← Core Workspace Area →                       │   │
├──────────────┬────────────────────────────┬────────────────────────┤   │
│   Panel A    │         Panel B            │       Panel C          │   │
│  File Panel  │       Chat Window          │    File Preview        │   │
│  (300px)     │       (flex-1)             │    (360px, conditional)│   │
│              │                            │                        │   │
│  ─────────── │                            │                        │   │
│  working dir │                            │                        │   │
│    (上, 40%)  │                            │                        │   │
│  ═══splitter │                            │                        │   │
│   basedir    │                            │                        │   │
│    (下, 60%)  │                            │                        │   │
│              │                            │                        │   │
└──────────────┴────────────────────────────┴────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 Responsive Strategy

- **TopNav**：固定高度 48px，`w-full`
- **Panel A 默认宽度**：300px，拖拽范围 200px ~ 500px
- **Panel B**：`flex-1`，填充中间剩余空间
- **Panel C 默认宽度**：360px，拖拽范围 220px ~ 600px，无预览时宽度为 0（不渲染），Panel B 自动扩展
- **面板间拖拽分隔条**：`Splitter` 组件，宽 4px，hover 时高亮，拖拽时全局禁用文本选择
- **应用最小宽度**：`min-w-[900px]`
- **应用最小高度**：`min-h-[600px]`

### 2.3 Panel C 条件渲染

Panel C 有四种互斥内容：SessionManagerPanel、FilePreview、TeamGraphView、TeamConversationPanel。

- **SessionManagerPanel**：`sessionPanelOpen` 为 true 时显示
- **FilePreview**：`previewFile` 非空时显示
- **TeamGraphView**：选中 team 且 `teamGraphOpen` 为 true 时显示，支持拓扑图/列表双视图切换
- **TeamConversationPanel**：选中 team 且 `teamConversationOpen` 为 true 时显示

```typescript
// 在 WorkspaceView.tsx 中
const isTeamTab = !!showTeamChat && isTeam(activeAgent) && activeAgent.members.length > 0;
const showTeamGraph = isTeamTab && teamGraphOpen;
const showTeamConversation = isTeamTab && teamConversationOpen;
const showRightPanel = sessionPanelOpen || !!previewFile || showTeamGraph || showTeamConversation;

// Panel C 渲染优先级：SessionManager > FilePreview > TeamGraphView > TeamConversationPanel
```

---

## 3. Top Navigation Bar

### 3.1 TopNav Container

**文件**：`src/components/layout/TopNav.tsx`

**Props**：无（从 Store 读取状态）

**结构**：

```
┌──────────────────────────────────────────────────────────────────┐
│  [AppIcon]  │  [AgentTabs                          [+]  ] │ [UserMenu] │
│   48×48     │           flex-1                         │   48×48    │
└──────────────────────────────────────────────────────────────────┘
```

**样式**：
- 高度 `h-12`（48px）
- 背景 `bg-white border-b border-border`
- 使用 `flex items-center`
- `z-50` 确保在最上层

---

### 3.2 AppIcon + Settings Dialog Trigger

**文件**：`src/components/layout/AppIcon.tsx`

**组件职责**：
1. 渲染应用 Logo 图标
2. 点击 🏠 后以居中 overlay Dialog 方式打开 Settings 配置页面

**交互行为**：
- Click：打开/关闭 Settings Popover
- Active 态：背景变为 `bg-secondary`
- 引导页期间：仍然可点击，用于配置 Models/Skills/MCPs

---

### 3.3 AgentTabs

**文件**：`src/components/agents/AgentTabs.tsx`

**组件职责**：渲染所有 Agent/Team 选项卡 + 新建按钮

**关键变更**：Agent 标识统一使用 `id`（UUID），`name` 仅作显示名。

---

### 3.4 AgentTab

**文件**：`src/components/agents/AgentTab.tsx`

**Props**：

```typescript
interface AgentTabProps {
  agent: Agent;
  isActive: boolean;
  onClick: () => void;
  onConfig: () => void;
}
```

**Single Agent 选项卡渲染**：

```
┌──────────────────────────────┐
│ ▶● Code Agent         [⚙][🗑]│
└──────────────────────────────┘
```

- 点击名称区域 → 切换当前 Agent
- 点击 ⚙ → 打开该 Agent 的配置弹窗
- 点击 🗑 → 弹出 ConfirmDialog 确认删除（Yes/No/Cancel，Yes 表示同时删除源文件）
- ⚙ 和 🗑 按钮默认隐藏，hover 时显示
- ▶/■ 按钮：启动/停止 Agent 事件循环（始终可见）

**启动/停止按钮**：
- ▶ (Play 图标，灰色) — Agent 处于 Ready 状态，点击启动 Agent 后台事件循环
- ■ (Square 图标，绿色) — Agent 处于 Waiting/Running 状态，点击停止 Agent
- 点击 ▶ 调用 `POST /agents/{id}/start`，点击 ■ 调用 `POST /agents/{id}/stop`

**状态指示器（彩色圆点）**：

| 颜色 | 状态 | 含义 |
|------|------|------|
| 灰色静点 `bg-gray-400` | Ready | Agent 已加载但未启动 |
| 绿色静点 `bg-green-500` | Waiting | 事件循环运行中，等待用户输入 |
| 绿色脉冲 `bg-green-500 animate-pulse` | Running | 正在处理消息/执行工具 |
| 红色静点 `bg-red-500` | Error | Agent 运行出错 |

**Team Agent 选项卡渲染**：

```
┌─────────────────────────────────┐
│ ▶● Dev Team                [▼]  │    ← 未展开时
└─────────────────────────────────┘

┌───────────────────────────────────────┐
│ ▶● Dev Team › Code Assistant     [▼]  │    ← 选中成员后
└───────────────────────────────────────┘
```

**删除按钮 + ConfirmDialog**：

AgentTab 包含一个删除按钮（Trash2 图标），hover 时显示。点击后弹出 ConfirmDialog：

- **Yes**：调用 `removeAgent(agent.id, true)` — 删除 agent + 源文件
- **No**：调用 `removeAgent(agent.id, false)` — 仅删除 agent 记录
- **Cancel**：关闭对话框，不执行操作

后端 API：`DELETE /api/agents/{id}?delete_files=true` 或 `DELETE /api/agents/{id}`

---

### 3.5 TeamDropdown

**文件**：`src/components/agents/TeamDropdown.tsx`

**Props**：

```typescript
interface TeamDropdownProps {
  agent: Agent; // type === "team"
}
```

**渲染内容**：

```
┌─────────────────────────────┐
│ 👤 Code Assistant       [⚙] │  ← 点击行 → 选中该成员，更新工作区
│ 👤 Research Bot         [⚙] │  ← 点击 ⚙ → 打开该成员配置弹窗
│ 👤 Tester Bot           [⚙] │
│ ─────────────────────────── │  ← 分隔线
│ 👥 Team Settings        [⚙] │  ← 返回 Team 整体视图 + 打开 Team 配置
└─────────────────────────────┘
```

**与旧版差异**：成员标识统一使用 `member.id`（UUID），Team 标识统一使用 `agent.id`。

**选中逻辑**：

```typescript
// store 中的 action（使用 id (UUID) 作为标识）
selectTeamMember: (teamId: string, memberName: string | null) => {
  if (memberName) {
    const team = get().agents.find(a => a.id === teamId);
    const member = team?.members?.find(m => m.name === memberName);
    set({ activeAgentId: teamId, activeTeamMemberName: memberName, workingDirPath: member?.workingDir || "" });
  } else {
    const team = get().agents.find(a => a.id === teamId);
    set({ activeAgentId: teamId, activeTeamMemberName: null, workingDirPath: team?.workingDir || "" });
  }
}
```

---

### 3.6 UserMenu

**文件**：`src/components/layout/UserMenu.tsx`

**职责**：用户菜单占位符，当前阶段仅显示一个用户图标。后续可扩展：主题切换、快捷键帮助、关于页面等。

---

## 4. Settings Popover

### 4.1 Overview

**文件**：`src/components/settings/SettingsPopover.tsx`

**Props**：

```typescript
interface SettingsPopoverProps {
  onClose: () => void;
}
```

**结构**：

```
┌───────────────────────────────────────────┐
│ ⚙ Settings                           [×]  │  ← 标题栏
├───────────────────────────────────────────┤
│ [Models] [Skills] [MCPs] [Prompts]        │  ← Tab 标签栏
├───────────────────────────────────────────┤
│                                           │
│        当前 Tab 对应的配置内容              │
│         （复用现有 *Module 组件）           │
│                                           │
└───────────────────────────────────────────┘
```

**规格**：
- 宽度：`w-[800px]`
- 高度：`h-[80vh]`（固定高度，切换 Tab 时窗口大小不变）
- 内部布局：左侧列表栏 `w-[300px]`，右侧详情面板 `flex-1`，各 Module 自行处理滚动
- 展示方式：通过 `AppIcon.tsx` 中的 `fixed inset-0 flex items-center justify-center` 居中 overlay 展示

**Settings 的有效 Tab 类型**：

```typescript
export type SettingsTab = "models" | "skills" | "mcps" | "prompts";
```

### 4.2 四个 Module 组件

`ModelsModule`、`SkillsModule`、`MCPsModule`、`PromptsModule` 当前设计为独立全宽组件。嵌入 `SettingsPopover` 后需要确保：

1. 移除组件内部的 `min-h-screen` 类
2. 调整内部 `padding` 以适配 Popover 的 `p-4` 包裹
3. 如有内部状态（如 `selectedModelId`），保留在 Store 中共享

**SkillsModule 新增功能**：
- Skill 删除：`DELETE /api/skills/{id}`
- Skill 刷新：`POST /api/skills/{id}/refresh`

**MCPsModule 新增功能**：
- Discover Tools 按钮：`POST /api/mcps/{id}/discover`

**PromptsModule 新增功能**：
- 分组管理（`group` 字段）
- 分组 Prompt 选择器：`GroupedPromptPicker.tsx`

---

## 5. Agent Configuration Dialog

### 5.1 Overview

**文件**：`src/components/agents/AgentConfigDialog.tsx`

重构自现有的 `CreateAgentDialog.tsx`，统一处理**新建**和**编辑**两种模式。当前为双栏布局。

**Props**：

```typescript
interface AgentConfigDialogProps {
  open: boolean;
  onClose: () => void;
  mode: "create" | "edit";          // 新建 或 编辑
  type: "agent" | "team" | "";      // Agent 或 Team（空字符串表示让用户选择）
  agentId?: string;                  // 编辑模式时传入，用于回填表单（使用 id 而非 name）
}
```

### 5.2 双栏布局

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Configure Agent                                          [Create Agent]   │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  左栏（基础配置）                                    右栏（Tools + Policy）  │
│  ┌─────────────────────────────┐   ┌──────────────────────────────────┐   │
│  │ Name          [___________] │   │ Tools                             │   │
│  │ Model         [select ▼   ] │   │ ┌──────────────────────────────┐ │   │
│  │ System Prompt [textarea  ] │   │ │ Built-in Tools           [☑] │ │   │
│  │              [From Prompt]  │   │ │ ☐ bash  ☐ read  ☐ write      │ │   │
│  │ Skills                      │   │ │ ☐ edit  ☐ grep  ☐ find       │ │   │
│  │ ☐ skill-a  ☐ skill-b      │   │ │ ☐ ls    ☐ sub_agent           │ │   │
│  │ Built-in Hook    [on off]  │   │ ├──────────────────────────────┤ │   │
│  └─────────────────────────────┘   │ │ MCP: server-a           [☑] │ │   │
│                                     │ │ ☐ mcp-tool-1                  │ │   │
│                                     │ └──────────────────────────────┘ │   │
│                                     │                                    │   │
│                                     │ Policy                             │   │
│                                     │ ┌──────────────────────────────┐ │   │
│                                     │ │ Working Dir (cwd)            │ │   │
│                                     │ │ [___________] [📂 Browse]    │ │   │
│                                     │ │ Bash Max Output Size [____]  │ │   │
│                                     │ │ Bash Default Timeout [____]  │ │   │
│                                     │ │ Web Timeout [____]           │ │   │
│                                     │ │ ...                          │ │   │
│                                     │ └──────────────────────────────┘ │   │
│                                     └──────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 字段三组分类

AgentConfigDialog 提交的 payload 字段按三组分类：

| 组 | 字段 | 说明 |
|----|------|------|
| Basic | `name`、`modelId`、`systemPrompt`、`workingDir` | Working Directory 是用户可填的 cwd，映射到后端 `toolPolicy.cwd` |
| Tools | `toolIds`、`skillIds`、`toolPolicy` | `toolPolicy` 是所有内置工具共享的配置，**不含 cwd** |
| Hooks | `hookNames`、`hookConfig` | `hookNames` 是启用的 hook 列表；`hookConfig` 是共享大字典 |

### 5.4 BaseDir 字段

`baseDir` 字段已从 AgentConfigDialog 的 UI 中移除（前端不发送）。后端 `create_agent` 中 `base_dir` 固定设为 `DATA_DIR/agents/{id}/`，在响应中回填 `baseDir` 字段供 BasedirTree 渲染文件树。

### 5.5 Name 自动生成

Agent 的 `name` 字段支持留空。如果用户不填写 name，后端 `CoreAgentConfig` 会自动生成一个默认名称。创建/更新后的响应数据中的 `name` 会回传来给前端 Store。

### 5.6 Template Import/Export

**文件**：`src/components/TemplatePicker.tsx`、`src/lib/utils.ts`

Template import/export 允许用户将 agent/team 配置保存为可移植的 JSON 文件并恢复为表单预填。Template 使用**人类可读的名称**（无 UUID），使其可跨实例移植。

**Template JSON 格式**：

```json
// Agent template
{
  "type": "agent",
  "name": "Architect",
  "systemPrompt": "You are an architect...",
  "tools": ["read", "write", "bash"],
  "skills": ["code-review"],
  "hooks": ["built_in.memory", "built_in.compress"],
  "hookConfig": {},
  "toolPolicy": { "maxReadSize": 30000 }
}
```

- `model` 和 `workingDir` 字段故意排除（不可移植）
- `hookConfig` 和 `toolPolicy` 中的模型引用（如 `subAgentModel`）使用模型**名称**

**Export**：编辑弹窗 header 中的下载按钮，`agentToTemplate()` 将 UUID 映射回名称

**Import**：TypeSelection 新增 "From Template" 选项 → `TemplatePicker` 选择 `.json` 文件 → `resolveTemplate()` 将名称映射回 UUID → 表单预填

---

## 6. ChatWindow

**文件**：`src/components/ChatWindow.tsx`

ChatWindow connects to the backend via a single persistent WebSocket (`ws://.../api/ws/chat`) for real-time streaming. Agent subscription is changed via `switch_agent` messages instead of closing and reopening the connection.

**Connection lifecycle**:
1. On mount: create a single WebSocket connection
2. WS `onopen`: send `switch_agent` for the current `activeAgentId`
3. On agent switch: first `await loadAgentMessages()` (HTTP), then send `switch_agent` with replay
4. On session switch: only `loadAgentMessages()` (HTTP), no WS switch needed
5. On unmount: close WebSocket, clear reconnect timer
6. On unexpected disconnect: auto-reconnect with exponential backoff (1s → 2s → 4s → ... → 30s max), re-send `switch_agent` on reconnect

**Streaming text accumulation**: When `text` chunks arrive via WebSocket, the accumulated text replaces the last assistant message's `content` field in-place. When `completed_message` arrives, the buffer resets.

**Interrupt button toggle**: The send button toggles between Send and Interrupt based on agent state. When `agentState === "running"`, the Interrupt button is shown.

**Session switcher dropdown**: A dropdown in the chat header shows all sessions. A "New Session" button creates a new session.

**WebSocket message types (frontend → backend)**:
- `switch_agent` — `{"agent_id": "uuid", "agent_name": "..."}`
- `user_message` — `{"content": "..."}`
- `human_answer` — `{"content": "..."}`
- `interrupt`

**WebSocket message types (backend → frontend)**:
- `switched` — `{"agent_name": "...", "agent_state": "...", "context_tokens": 12345}`
- `agent_state` — `{"state": "running", "context_tokens": 12345}`
- `text` — streaming text chunks
- `thinking` — thinking/reasoning chunks
- `completed_tool_use` — tool call made
- `tool_results` — tool execution results
- `completed_message` — full message completed
- `human_question` — question to user (ask_human tool)
- `error` — error information

---

## 7. TimerPanel

**文件**：`src/components/TimerPanel.tsx`

ChatWindow 输入框上方集成上下文进度条和定时任务管理功能。

**布局**：

```
┌──────────────────────────────────────────────────────────┐
│  [████████████░░░░░░░░░░░░░░] 12,345 / 200,000          │  ← 上下文进度条
│  [⏱ Timers (3)]  [输入框........................] [发送] │  ← 输入栏
├──────────────────────────────────────────────────────────┤
│  Name     │ Interval │ Hint   │ Status   │ Actions      │  ← 上拉面板
│  ─────────┼──────────┼────────┼──────────┼──────────────│
│  check    │ 30s      │ check  │ ●Running │ [■][✏][🗑]   │
│  report   │ 60s      │ report │ ○Stopped │ [▶][✏][🗑]   │
│           │          │        │          │       [+ Add] │
└──────────────────────────────────────────────────────────┘
```

**API 调用**：
- `GET /agents/{id}/timers` — 加载列表
- `POST /agents/{id}/timers` — 新建
- `PUT /agents/{id}/timers/{name}` — 更新
- `POST /agents/{id}/timers/{name}/start` — 启动
- `POST /agents/{id}/timers/{name}/stop` — 停止
- `DELETE /agents/{id}/timers/{name}` — 删除

**TimerConfig 类型**：
```typescript
interface TimerConfig {
  name: string;
  seconds: number;
  hint: string;
  enabled: boolean;
  running?: boolean;
}
```

---

## 8. TeamChatWindow

**文件**：`src/components/TeamChatWindow.tsx`

Team group chat component shown when a team is selected without picking a specific member. Connects via WebSocket to `ws://.../api/ws/team/{team_id}`.

**Features**:
- **@mention autocomplete**: Typing `@` triggers a dropdown listing all team members
- **Agent-colored messages**: Each agent member gets a unique color from a palette
- **Multi-member routing**: Messages can @mention multiple agents simultaneously
- **Mention parsing**: Frontend extracts `@name` patterns via regex before sending

**Color palette for agents**:
```typescript
const AGENT_COLORS = [
  "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
  "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
];
```

---

## 9. Workspace View

### 9.1 WorkspaceView Container

**文件**：`src/components/workspace/WorkspaceView.tsx`

**组件职责**：核心工作区的布局容器，管理三栏动态布局和面板宽度状态。

**routing logic**:
- No agent selected → empty state placeholder
- Single agent selected → `ChatWindow` (standard chat)
- Team selected **without** a member → `TeamChatWindow` (group chat with @mention)
- Team selected **with** a member → `ChatWindow` (1:1 chat with that member)

### 9.2 PanelSplitter Component

**文件**：`src/components/workspace/Splitter.tsx`

**Props**：`onResize: (delta: number) => void` — 鼠标拖动时的位移回调。

### 9.3 Panel A: File Panel

**文件**：`src/components/workspace/PanelA_FilePanel.tsx`

面板顶部 Working Dir 初始值来自 `agent.workingDir`，底部 Base Dir 来自 `agent.baseDir`（后端自动生成）。

文件树数据通过 `GET /api/files/tree` 获取，支持 `depth` 参数控制展开深度。

### 9.4 Panel C: File Preview

**文件**：`src/components/workspace/PanelC_FilePreview.tsx`

支持的文件类型与查看器：

| MIME 类型 | 文件扩展名 | 查看器 | 渲染方式 |
|-----------|-----------|--------|----------|
| `text/typescript` | `.ts`, `.tsx` | `CodeViewer` | prism-react-renderer 语法高亮 |
| `text/x-python` | `.py` | `CodeViewer` | prism-react-renderer 语法高亮 |
| `application/json` | `.json` | `CodeViewer` | prism-react-renderer 语法高亮 |
| `text/markdown` | `.md` | `MarkdownViewer` | react-markdown 渲染 |
| `image/*` | `.png`, `.jpg`, `.gif`, `.svg`, `.webp` | `ImageViewer` | `<img src="/api/files/raw?path=...">` |
| `application/pdf` | `.pdf` | `PdfViewer` | `<iframe src="/api/files/raw?path=...">` |

### 9.5 Panel C: TeamGraphView

**文件**：`src/components/workspace/TeamGraphView.tsx`

**依赖**：`@xyflow/react`（React Flow）、`dagre`（自动布局）

当选中 Team 且 `teamGraphOpen` 为 true 时显示，支持拓扑图/列表双视图切换。

- **拓扑图（默认）**：React Flow + dagre 自动布局，自定义 AgentNode 和 BidirectionalEdge
- **列表**：卡片列表，每个 agent 一张卡片，点击展开显示其 contacts

### 9.6 Panel C: SessionManagerPanel

**文件**：`src/components/workspace/SessionManagerPanel.tsx`

全局 Session 管理面板，支持跨 Agent 的 session 列表、详情查看、fork、删除。

**API 调用**：
- `GET /api/sessions?agent_id={可选}` — 全局 session 列表
- `GET /api/sessions/{session_id}` — session 详情 + turn 摘要
- `POST /api/sessions/{session_id}/fork` — 从指定 turn fork
- `DELETE /api/sessions/{session_id}` — 删除 session
- `POST /api/sessions/reindex` — 重建索引

### 9.7 Panel C: TeamConversationPanel

**文件**：`src/components/workspace/TeamConversationPanel.tsx`

Team 对话管理面板，支持 Team 级别的对话创建、加载、删除。

**API 调用**：
- `GET /api/teams/{id}/conversations` — 列出 Team 对话
- `POST /api/teams/{id}/conversations` — 创建新对话
- `POST /api/teams/{id}/conversations/{conversationId}/load` — 加载对话
- `DELETE /api/teams/{id}/conversations/{conversationId}` — 删除对话

---

## 10. TypeScript 类型定义

### 10.1 Agent 类型（可辨识联合类型）

```typescript
// 共有运行时字段
interface AgentBase {
  id: string;                        // UUID 机器标识（后端生成，unified-id 设计）
  name: string;                      // 显示名，可重复
  state: "ready" | "waiting" | "running" | "error";
  messages: Message[];
  sessions: SessionInfo[];
  currentSessionId: string;
}

// Single Agent 运行时类型
export interface SingleAgent extends AgentBase {
  type: "single";
  baseDir: string;                   // 后端自动生成，前端只读不写
  workingDir: string;                // 映射到后端 toolPolicy.cwd
  modelId: string;
  systemPrompt: string;
  toolIds: string[];                 // ToolConfig.id (UUID) 列表
  skillIds: string[];                // SkillConfig.id (UUID) 列表
  hookNames: string[];
  hookConfig: Record<string, unknown>;
  toolPolicy: ToolPolicy;
}

// Team 运行时类型
export interface Team extends AgentBase {
  type: "team";
  baseDir: string;
  workingDir: string;
  teamDescription: string;
  members: SingleAgent[];
  contacts: Record<string, Record<string, string>>;
}

// 可辨识联合
export type Agent = SingleAgent | Team;
```

### 10.2 ToolPolicy 类型

```typescript
export interface ToolPolicy {
  maxReadSize?: number;
  bashMaxOutputSize?: number;
  bashDefaultTimeout?: number;
  webTimeout?: number;
  webMaxResponseSize?: number;
  webMaxOutputSize?: number;
  webSearchMaxResults?: number;
  webAllowedDomains?: string[];
  webUserAgent?: string;
  subAgentModel?: string;           // modelId for sub-agent
  subAgentBlockedTools?: string[];  // tool names blocked for sub-agent
}
```

### 10.3 Message 类型

```typescript
export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  sourceAgent?: string;
  chunkType?: "text" | "thinking" | "tool_use" | "tool_result" | "todo_list" | "error" | "input_event";
  toolName?: string;
  toolInput?: Record<string, unknown>;
  messageId?: string;
  toolCallId?: string;
  runtime?: boolean;
}
```

### 10.4 其他类型

| 类型 | 标识字段 | 说明 |
|------|---------|------|
| `Model` | `id: string` | UUID 标识，`thinking: boolean` |
| `Tool` | `id: string` | UUID 标识，`source` 区分 built_in/mcp/hook/team，`mcpServerId` 标识 MCP 来源 |
| `Skill` | `id: string` | UUID 标识 |
| `MCPServer` | `id: string` | UUID 标识，含 `tools: Tool[]` |
| `Prompt` | `id: string` | UUID 标识，`group` 字段支持分组管理 |
| `SessionInfo` | `id: string` | 会话 ID，含 `timestamp`, `turnCount`, `isActive` |
| `TimerConfig` | `name: string` | 定时任务，`seconds: number`, `hint`, `enabled`, `running` |
| `GlobalSessionIndex` | `session_id: string` | 全局 session 索引，含 `agent_id`, `agent_name`, `parent_session_id`, `fork_turn_index` |
| `SessionDetail` | `sessionId: string` | Session 详情，含 `turns: TurnInfo[]` |
| `TeamConversation` | `id: string` | Team 对话，含 `memberSessions`, `messageCount` |
| `TeamChatMessage` | — | Team 聊天消息，含 `fromAgent`, `toAgent`, `type` |

### 10.5 Template 类型

```typescript
export interface AgentTemplate {
  type: "agent";
  name: string;
  systemPrompt: string;
  tools: string[];        // 人类可读的工具名（非 UUID）
  skills: string[];       // 人类可读的技能名
  hooks: string[];
  hookConfig: Record<string, unknown>;
  toolPolicy: Record<string, unknown>;
}

export interface TeamTemplate {
  type: "team";
  name: string;
  teamDescription: string;
  members: AgentTemplate[];
  contacts: Record<string, Record<string, string>>;
}

export type Template = AgentTemplate | TeamTemplate;

export interface TemplateResolveResult {
  type: "agent" | "team";
  warnings: string[];
  name: string;
  systemPrompt: string;
  toolIds: string[];
  skillIds: string[];
  hookNames: string[];
  hookConfig: Record<string, unknown>;
  toolPolicy: Record<string, unknown>;
  teamDescription?: string;
  members?: TemplateResolveResult[];
  contacts?: Record<string, Record<string, string>>;
}
```

---

## 11. Zustand Store

### 11.1 Store 核心状态

```typescript
export interface AppState {
  agents: Agent[];
  activeAgentId: string | null;           // 使用 id (UUID)
  activeTeamMemberName: string | null;
  setActiveAgentId: (id: string | null) => void;
  selectTeamMember: (teamId: string, memberName: string | null) => void;
  updateAgent: (id: string, updates: UpdateAgentPayload) => Promise<void>;
  updateTeam: (id: string, updates: UpdateTeamPayload) => Promise<void>;
  removeAgent: (id: string, deleteFiles?: boolean) => Promise<void>;
  addMessage: (agentId: string, message: Message) => void;
  upsertMessage: (agentId: string, message: Message) => void;
  patchMessage: (agentId: string, messageId: string, patch: Partial<Message>) => void;
  agentInputs: Record<string, string>;
  setAgentInput: (agentId: string, value: string) => void;
  clearAgentInput: (agentId: string) => void;

  // Hook descriptors from GET /api/hooks
  hooksDescriptor: HookListResponse | null;
  fetchHooksDescriptor: () => Promise<void>;

  isSettingsOpen: boolean;
  settingsActiveTab: SettingsTab;
  openSettings: (tab?: SettingsTab) => void;
  closeSettings: () => void;

  configDialog: {
    open: boolean;
    mode: "create" | "edit";
    type: "agent" | "team" | "";
    agentId?: string;                     // 使用 agentId（UUID）
  };
  openConfigDialog: (mode: "create" | "edit", type: "agent" | "team" | "", agentId?: string) => void;
  closeConfigDialog: () => void;

  // File tree refresh keys
  workingDirRefreshKey: number;
  baseDirRefreshKey: number;
  refreshFileTreeKey: number;
  refreshWorkingDir: () => void;
  refreshBaseDir: () => void;
  refreshFileTree: () => void;

  workingDirPath: string;
  setWorkingDirPath: (path: string) => void;
  baseDirPath: string;
  setBaseDirPath: (path: string) => void;
  basedirExpandedPaths: Set<string>;
  toggleBasedirExpand: (path: string) => void;
  workingDirExpandedPaths: Set<string>;
  toggleWorkingDirExpand: (path: string) => void;

  // Agent lifecycle state
  agentStates: Record<string, "ready" | "waiting" | "running" | "error">;
  agentSessions: Record<string, SessionInfo[]>;
  agentTimers: Record<string, TimerConfig[]>;
  agentContextTokens: Record<string, number>;

  // ... 其他状态（models, tools, mcpServers, skills, prompts, etc.）
}
```

### 11.2 关键 Store Actions

```typescript
// setActiveAgentId: 切换 agent 时同步更新 working dir 和 base dir
setActiveAgentId: (id) => {
  const agent = id ? get().agents.find((a) => a.id === id) : null;
  set({
    activeAgentId: id,
    activeTeamMemberName: null,
    workingDirPath: agent?.workingDir || "",
    baseDirPath: (agent as SingleAgent)?.baseDir || "",
    previewFile: null,
  });
},

// createAgentApi: 发送到后端，使用后端返回的数据
createAgentApi: async (agent: CreateAgentPayload) => {
  const created = await api.createAgent(agent);
  set((state) => ({
    agents: [...state.agents, created],
    activeAgentId: created.id,
  }));
},

// removeAgent: 支持可选的 deleteFiles 参数
removeAgent: async (id, deleteFiles) => {
  await api.deleteAgent(id, deleteFiles);
  set((state) => ({
    agents: state.agents.filter((a) => a.id !== id),
    activeAgentId: state.activeAgentId === id ? null : state.activeAgentId,
    previewFile: state.activeAgentId === id ? null : state.previewFile,
  }));
},
```

### 11.3 builtin tool UUID 同步

`frontend/src/store/index.ts` 顶部声明 `BUILTIN_TOOL_IDS`（与 `BBagent/built_in_tool/__init__.py` 保持完全一致）：

```typescript
const BUILTIN_TOOL_IDS: Record<string, string> = {
  bash: "5a40e5e1-6931-4126-b142-581379f4f2eb",
  read: "4c48a29c-a52a-4ec7-b7d7-d265316091c7",
  write: "20c41591-9b4e-4ff0-9182-f11db46fef41",
  edit: "2d35e797-d8f7-41cf-aa12-e439ec74230b",
  grep: "4dc7319f-7ff7-484b-aa19-c39fa5efa772",
  find: "023a166d-246b-4aeb-be56-3119210b9bba",
  ls: "20ae9084-3a2c-413b-bdbb-86f04fb9fdd3",
  sub_agent: "5596651c-ee17-4ad4-ae79-7ed73e6dad29",
};
```

---

## 12. API Client

**文件**：`src/lib/api.ts`

基于 `fetch` 的 API 客户端，所有 `id` 类型的参数使用 UUID：

```typescript
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

export const api = {
  // Models
  listModels: () => request("/models"),
  createModel: (data) => request("/models", { method: "POST", body: JSON.stringify(data) }),
  updateModel: (id, data) => request(`/models/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteModel: (id) => request(`/models/${id}`, { method: "DELETE" }),
  testModel: (id, prompt) => request(`/models/${id}/test`, { method: "POST", body: JSON.stringify({ prompt }) }),

  // Tools & Hooks
  listTools: () => request("/tools"),
  listHooks: () => request("/hooks"),

  // MCPs — per unified-id, paths use id (UUID)
  listMcps: () => request("/mcps"),
  createMcp: (data) => request("/mcps", { method: "POST", body: JSON.stringify(data) }),
  updateMcp: (id, data) => request(`/mcps/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteMcp: (id) => request(`/mcps/${id}`, { method: "DELETE" }),
  discoverMcp: (id) => request(`/mcps/${id}/discover`, { method: "POST" }),
  importMcps: (path) => request("/mcps/import", { method: "POST", body: JSON.stringify({ path }) }),

  // Prompts
  listPrompts: () => request("/prompts"),
  createPrompt: (data) => request("/prompts", { method: "POST", body: JSON.stringify(data) }),
  updatePrompt: (id, data) => request(`/prompts/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deletePrompt: (id) => request(`/prompts/${id}`, { method: "DELETE" }),
  importPrompts: (path) => request("/prompts/import", { method: "POST", body: JSON.stringify({ path }) }),

  // Skills
  listSkills: () => request("/skills"),
  importSkills: (path) => request("/skills/import", { method: "POST", body: JSON.stringify({ path }) }),
  deleteSkill: (id) => request(`/skills/${id}`, { method: "DELETE" }),
  refreshSkill: (id) => request(`/skills/${id}/refresh`, { method: "POST" }),

  // Agents — per unified-id, all paths use agent.id (UUID)
  listAgents: () => request("/agents"),
  getAgent: (id) => request(`/agents/${id}`),
  createAgent: (data) => request("/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgent: (id, data) => request(`/agents/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteAgent: (id, deleteFiles?) =>
    request(`/agents/${id}${deleteFiles ? '?delete_files=true' : ''}`, { method: "DELETE" }),
  startAgent: (id) => request(`/agents/${id}/start`, { method: "POST" }),
  stopAgent: (id) => request(`/agents/${id}/stop`, { method: "POST" }),
  getAgentState: (id) => request(`/agents/${id}/state`),
  listSessions: (id) => request(`/agents/${id}/sessions`),
  switchSession: (id, sessionId) => request(`/agents/${id}/sessions/${sessionId}/switch`, { method: "POST" }),
  newSession: (id) => request(`/agents/${id}/sessions/new`, { method: "POST" }),
  getAgentMessages: (id) => request(`/agents/${id}/messages`),

  // Timers
  listTimers: (id) => request(`/agents/${id}/timers`),
  addTimer: (id, data) => request(`/agents/${id}/timers`, { method: "POST", body: JSON.stringify(data) }),
  updateTimer: (id, name, data) => request(`/agents/${id}/timers/${encodeURIComponent(name)}`, { method: "PUT", body: JSON.stringify(data) }),
  startTimer: (id, name) => request(`/agents/${id}/timers/${encodeURIComponent(name)}/start`, { method: "POST" }),
  stopTimer: (id, name) => request(`/agents/${id}/timers/${encodeURIComponent(name)}/stop`, { method: "POST" }),
  deleteTimer: (id, name) => request(`/agents/${id}/timers/${encodeURIComponent(name)}`, { method: "DELETE" }),

  // Teams — paths use team.id
  listTeams: () => request("/teams"),
  getTeam: (id) => request(`/teams/${id}`),
  createTeam: (data) => request("/teams", { method: "POST", body: JSON.stringify(data) }),
  updateTeam: (id, data) => request(`/teams/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteTeam: (id) => request(`/teams/${id}`, { method: "DELETE" }),
  startTeam: (id) => request(`/teams/${id}/start`, { method: "POST" }),
  stopTeam: (id) => request(`/teams/${id}/stop`, { method: "POST" }),
  getTeamMessages: (id) => request(`/teams/${id}/messages`),
  listTeamConversations: (id) => request(`/teams/${id}/conversations`),
  createTeamConversation: (id, name?) => request(`/teams/${id}/conversations`, { method: "POST", body: JSON.stringify({ name }) }),
  loadTeamConversation: (id, conversationId) => request(`/teams/${id}/conversations/${conversationId}/load`, { method: "POST" }),
  deleteTeamConversation: (id, conversationId) => request(`/teams/${id}/conversations/${conversationId}`, { method: "DELETE" }),

  // Files
  getFileTree: (path, depth?) => { /* supports depth parameter */ },
  readFile: (path) => request(`/files/read?path=${encodeURIComponent(path)}`),
  writeFile: (path, content) => request("/files/write", { method: "POST", body: JSON.stringify({ path, content }) }),
  listDirs: (path) => request(`/files/dirs?path=${encodeURIComponent(path)}`),
  openPath: (path) => request("/files/open", { method: "POST", body: JSON.stringify({ path }) }),
  createDir: (path) => request("/files/dirs", { method: "POST", body: JSON.stringify({ path }) }),
  renameDir: (oldPath, newPath) => request("/files/dirs", { method: "PUT", body: JSON.stringify({ oldPath, newPath }) }),
  deleteDir: (path, recursive) => request(`/files/dirs?path=...&recursive=...`, { method: "DELETE" }),

  // UI State
  getState: () => request("/state"),
  saveState: (data) => request("/state", { method: "POST", body: JSON.stringify(data) }),

  // Global Session Manager
  listGlobalSessions: (agentId?) => request(`/sessions${agentId ? `?agent_id=${agentId}` : ''}`),
  getSessionDetail: (sessionId) => request(`/sessions/${sessionId}`),
  forkSession: (sessionId, turnIndex, targetAgentId?) =>
    request(`/sessions/${sessionId}/fork`, { method: "POST", body: JSON.stringify({ turnIndex, targetAgentId }) }),
  deleteGlobalSession: (sessionId) => request(`/sessions/${sessionId}`, { method: "DELETE" }),
};

// WebSocket creators
export function createChatWs(): WebSocket { /* ws://.../api/ws/chat */ }
export function createFileWatchWs(): WebSocket { /* ws://.../api/ws/files */ }
export function createTeamChatWs(teamId: string): WebSocket { /* ws://.../api/ws/team/{teamId} */ }
```

---

## 13. Hooks

### 13.1 useGlobalAgentState

**文件**：`src/hooks/useGlobalAgentState.ts`

全局 Agent 状态 hook，从 Zustand store 中提取当前活跃 agent 的状态信息。

---

## 14. Styling Conventions

### 14.1 CSS Variables

All components use CSS variables for theming:

```css
:root {
  --color-background: #ffffff;
  --color-foreground: #09090b;
  --color-muted: #f4f4f5;
  --color-muted-foreground: #71717a;
  --color-primary: #18181b;
  --color-primary-foreground: #fafafa;
  --color-secondary: #f4f4f5;
  --color-border: #e4e4e7;
  --color-ring: #a1a1aa;
}
```

### 14.2 Tailwind Patterns

- **Bordered buttons**: All buttons use `border border-(--color-border)`
- **Rounded corners**: Consistent `rounded-lg` (8px) or `rounded-xl` (12px)
- **Transitions**: `transition-colors` or `transition-all duration-200`
- **Focus states**: `focus:outline-none focus:ring-2 focus:ring-(--color-ring)`

---

## 15. ErrorBoundary Component

**文件**：`src/components/ErrorBoundary.tsx`

全局 React 错误边界，捕获子组件渲染错误，显示友好的错误页面（红色图标 + 错误信息 + Reload 按钮）。在 `App.tsx` 中包裹 `AppContent`。

---

## 16. ToastContainer Component

**文件**：`src/components/ToastContainer.tsx`

Toast 通知容器，用于显示操作结果提示（info/warning）。

---

## 17. MarkdownContent Component

**文件**：`src/components/MarkdownContent.tsx`

统一 Markdown 渲染组件，使用 react-markdown + prism-react-renderer 语法高亮。支持标题、粗体、斜体、代码块、表格、列表、任务列表、链接、图片、引用块等格式。

---

## 18. File Watch WebSocket

前端通过 `createFileWatchWs()` 创建 WebSocket 连接到 `ws://.../api/ws/files`，实时接收文件系统变化通知，自动刷新 WorkingDirView 和 BasedirTree。

---

## 19. Onboarding Flow

**文件**：`src/components/onboarding/OnboardingView.tsx`

New user onboarding flow shown when no agents exist. Guides users through:
1. Welcome screen
2. Model configuration
3. First agent creation
