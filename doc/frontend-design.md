# GLagent Frontend Design Documentation v6

> **v7 fork**: 见 [`frontend_apple/`](../../frontend_apple) 目录 —— 基于 v6 的 **Apple Refined** 美学改造分支
> - 设计预览：[`design-preview/d-apple.html`](../../design-preview/d-apple.html)
> - 改造方案：[`doc/apple-refactor-plan.md`](./apple-refactor-plan.md)
> - 主要变化：系统字体 (SF Pro) · Apple 蓝 `#0066cc` · 浮毛玻璃顶栏 · Pill 标签 · 无气泡对话 · 抽屉式 Settings

## 1. Overview

### 1.1 Project Introduction

GLagent Frontend 是一个基于 React 18 + TypeScript 的单页应用（SPA），为 GLagent 多代理系统提供可视化交互界面。

本版本（v6）对架构进行了重大重构：
- 移除左侧导航栏，改为**顶部导航栏**（类浏览器标签页）
- 核心区采用**三栏动态布局**：文件面板（上下分屏） + 对话窗口 + 文件预览（条件显示）
- 配置项全部收进 **Settings Popover**，不占用工作区空间
- 新增 **Onboarding 引导页**，帮助新用户完成初始化流程
- 配置页面对齐 **BBagent 基础库**数据结构：Model 按 provider 区分字段、Agent 支持 tools/skills 勾选、Team 三步配置流程、MCP/Skill/Prompt 支持文件夹导入
- Agent 标识统一使用 `id`（UUID 机器标识），`name` 仅作显示名（unified-id 设计）
- AgentConfigDialog 重新设计为双栏布局（左侧基础配置，右侧 Tools + Policy）

> **最后更新**：2026-06-01 — 新增 ErrorBoundary 组件、更新组件文件结构、完善样式约定

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
@radix-ui/react-popover       # AgentTab 中 TeamDropdown 的 Trigger（始终需要）
@radix-ui/react-dialog        # Agent 配置弹窗（已有）
@radix-ui/react-dropdown-menu # Team 成员下拉菜单
@radix-ui/react-tabs          # Settings 面板内部 Tab 切换
@radix-ui/react-tooltip       # 悬浮提示（已有）
```

### 1.3 Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── TopNav.tsx              # 顶部导航栏容器
│   │   │   ├── AppIcon.tsx             # 应用图标 + Settings Popover 触发器
│   │   │   └── UserMenu.tsx            # 用户菜单
│   │   ├── settings/
│   │   │   └── SettingsPopover.tsx     # Settings Popover（内嵌 4 个 Module）
│   │   ├── agents/
│   │   │   ├── AgentTabs.tsx           # Agent/Team 选项卡列表
│   │   │   ├── AgentTab.tsx            # 单个选项卡（含删除按钮 + ConfirmDialog）
│   │   │   ├── TeamDropdown.tsx        # Team 成员下拉菜单
│   │   │   └── AgentConfigDialog.tsx   # 新建/编辑 Agent/Team 弹窗（双栏布局）
│   │   ├── workspace/
│   │   │   ├── WorkspaceView.tsx       # 三栏核心工作区容器
│   │   │   ├── PanelA_FilePanel.tsx    # 文件面板（上下分屏容器）
│   │   │   ├── WorkingDirView.tsx      # 上半部分：working dir
│   │   │   ├── BasedirTree.tsx         # 下半部分：basedir 完整项目树
│   │   │   ├── Splitter.tsx            # 可拖拽分割条
│   │   │   └── PanelC_FilePreview.tsx  # 文件预览面板（条件渲染）
│   │   ├── onboarding/
│   │   │   ├── OnboardingView.tsx      # 引导页容器
│   │   │   └── OnboardingStep.tsx      # 单个引导步骤组件
│   │   ├── chat/
│   │   │   ├── ChatWindow.tsx          # 对话窗口组件（复用）
│   │   │   ├── TeamChatWindow.tsx      # Team 群聊窗口（@mention，颜色编码消息）
│   │   │   ├── TimerPanel.tsx          # 定时任务管理面板（ChatWindow 输入框上方上拉展开）
│   │   │   └── MessageBubble.tsx       # 消息气泡组件
│   │   ├── config/
│   │   │   ├── ModelsModule.tsx        # Models 模块（复用）
│   │   │   ├── SkillsModule.tsx        # Skills 模块（复用）
│   │   │   ├── MCPsModule.tsx          # MCPs 模块（复用）
│   │   │   └── PromptsModule.tsx       # Prompts 模块（复用）
│   │   ├── common/
│   │   │   ├── FolderPicker.tsx        # 可复用文件夹选择下拉组件
│   │   │   ├── FolderPickerModal.tsx   # 全屏居中 Modal 文件夹选择器（用于 Import 流程）
│   │   │   ├── TemplatePicker.tsx      # 模板文件选择器（目录树 + .json 文件选择）
│   │   │   └── ConfirmDialog.tsx       # 通用确认对话框（Yes/No/Cancel）
│   │   └── ErrorBoundary.tsx           # 全局错误边界组件
│   ├── store/
│   │   └── index.ts                    # Zustand Store
│   ├── types/
│   │   └── index.ts                    # TypeScript 类型定义
│   ├── lib/
│   │   ├── api.ts                      # 后端 API 客户端
│   │   └── utils.ts                    # 工具函数（cn, getMimeType）
│   ├── App.tsx                         # 根组件
│   └── index.css                       # 全局样式（CSS 变量定义）
├── package.json
└── vite.config.ts
```

需要**移除**的文件：
- `src/components/Sidebar.tsx`
- `src/components/AgentList.tsx`
- `src/components/ToolsModule.tsx`
- `src/components/CreateAgentDialog.tsx`（重构为 `AgentConfigDialog.tsx`）

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
- **面板间拖拽分隔条**：`PanelSplitter` 组件，宽 4px，hover 时高亮，拖拽时全局禁用文本选择
- **应用最小宽度**：`min-w-[900px]`
- **应用最小高度**：`min-h-[600px]`

### 2.3 Panel C 条件渲染

Panel C 有三种互斥内容：SessionManagerPanel、FilePreview、TeamGraphView。

- **SessionManagerPanel**：`sessionPanelOpen` 为 true 时显示
- **FilePreview**：`previewFile` 非空时显示
- **TeamGraphView**：选中 team 且 `teamGraphOpen` 为 true 时显示，支持拓扑图/列表双视图切换，右上角关闭按钮

```typescript
// 在 WorkspaceView.tsx 中
const isTeamTab = !!showTeamChat && isTeam(activeAgent) && activeAgent.members.length > 0;
const showTeamGraph = isTeamTab && teamGraphOpen;
const showRightPanel = sessionPanelOpen || !!previewFile || showTeamGraph;

// Panel C 渲染优先级：SessionManager > FilePreview > TeamGraphView
{sessionPanelOpen ? (
  <SessionManagerPanel width={panelCWidth} />
) : previewFile ? (
  <PanelC_FilePreview ref={panelCRef} width={panelCWidth} />
) : showTeamGraph ? (
  <div ref={panelCRef} style={{ width: panelCWidth }}>
    <TeamGraphView width={panelCWidth} />
  </div>
) : null}
```

- **Panel A 右侧**和 **Panel C 左侧**各有一个 `PanelSplitter`，拖拽时实时调整相邻面板宽度
- Panel A 往右拖 = 增大宽度，Panel C 往左拖 = 增大宽度（delta 方向取反）
- 宽度有最小值（Panel A: 200px, Panel C: 220px）和最大值（Panel A: 500px, Panel C: 600px）限制
- 拖拽过程中添加 `body` 级别的 `select-none` 和 `cursor-col-resize` 类以改善体验

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

**实现伪代码**：

```tsx
function TopNav() {
  return (
    <div className="flex items-center h-12 bg-white border-b border-border shrink-0 z-50">
      <AppIcon />
      <div className="flex-1 flex items-center h-full overflow-x-auto">
        <AgentTabs />
      </div>
      <UserMenu />
    </div>
  );
}
```

---

### 3.2 AppIcon + Settings Dialog Trigger

**文件**：`src/components/layout/AppIcon.tsx`

**组件职责**：
1. 渲染应用 Logo 图标
2. 点击 🏠 后以居中 overlay Dialog 方式打开 Settings 配置页面

**渲染**：

```tsx
function AppIcon() {
  const isSettingsOpen = useAppStore((s) => s.isSettingsOpen);
  const openSettings = useAppStore((s) => s.openSettings);
  const closeSettings = useAppStore((s) => s.closeSettings);
  const settingsActiveTab = useAppStore((s) => s.settingsActiveTab);

  const handleToggle = () => {
    if (isSettingsOpen) {
      closeSettings();
    } else {
      openSettings();
    }
  };

  return (
    <>
      <button
        onClick={handleToggle}
        className={cn(
          "flex items-center justify-center w-12 h-12 shrink-0",
          "hover:bg-(--color-secondary) rounded-md transition-colors",
          isSettingsOpen && "bg-(--color-secondary)"
        )}
      >
        <Bot className="w-6 h-6 text-(--color-primary)" />
      </button>

      {isSettingsOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={closeSettings} />
          <div className="relative">
            <SettingsPopover
              activeTab={settingsActiveTab}
              onTabChange={(tab: SettingsTab) => useAppStore.setState({ settingsActiveTab: tab })}
              onClose={closeSettings}
            />
          </div>
        </div>
      )}
    </>
  );
}
```

**交互行为**：
- Click：打开/关闭 Settings Popover
- Active 态：背景变为 `bg-secondary`
- 引导页期间：仍然可点击，用于配置 Models/Skills/MCPs

---

### 3.3 AgentTabs

**文件**：`src/components/agents/AgentTabs.tsx`

**组件职责**：渲染所有 Agent/Team 选项卡 + 新建按钮

**关键变更**：Agent 标识统一使用 `id`（UUID），`name` 仅作显示名。

**渲染逻辑**：

```tsx
function AgentTabs() {
  const agents = useAppStore((s) => s.agents);
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const setActiveAgentId = useAppStore((s) => s.setActiveAgentId);
  const openConfigDialog = useAppStore((s) => s.openConfigDialog);

  if (agents.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-sm text-muted-foreground">
          No agents yet. Complete onboarding to create your first agent.
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center h-full gap-0.5">
      {agents.map((agent) => (
        <AgentTab
          key={agent.id}
          agent={agent}
          isActive={agent.id === activeAgentId}
          onClick={() => setActiveAgentId(agent.id)}
          onConfig={() => openConfigDialog("edit", agent.type === "single" ? "agent" : "team", agent.id)}
        />
      ))}
      <button
        onClick={() => openConfigDialog("create", "")}
        className="flex items-center justify-center w-8 h-8 ml-1 
                   rounded-md hover:bg-secondary text-muted-foreground 
                   hover:text-foreground transition-colors shrink-0"
        title="New Agent"
      >
        <Plus className="w-4 h-4" />
      </button>
    </div>
  );
}
```

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
- 点击 ▶ 调用 `POST /agents/{name}/start`，点击 ■ 调用 `POST /agents/{name}/stop`

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

- 点击名称区域 → 展开下拉菜单（调用 `TeamDropdown`）
- 点击 ▼ → 同样展开下拉菜单
- 当选中了 Team 的某个成员时，名称显示为 `TeamName › MemberName`

**删除按钮 + ConfirmDialog**：

AgentTab 包含一个删除按钮（Trash2 图标），hover 时显示。点击后弹出 ConfirmDialog：

```
┌───────────────────────────────────────────┐
│ Delete Agent                          [×] │
├───────────────────────────────────────────┤
│ Are you sure you want to delete "agent"?  │
│ Do you want to delete the source files    │
│ as well?                                   │
├───────────────────────────────────────────┤
│                     [Cancel] [No] [Yes]   │
└───────────────────────────────────────────┘
```

- **Yes**：调用 `removeAgent(agent.id, true)` — 删除 agent + 源文件
- **No**：调用 `removeAgent(agent.id, false)` — 仅删除 agent 记录
- **Cancel**：关闭对话框，不执行操作

后端 API：`DELETE /api/agents/{id}?delete_files=true` 或 `DELETE /api/agents/{id}`

**样式规范**：

| 状态 | 样式 |
|------|------|
| 默认 | `bg-transparent`, `text-muted-foreground`, `border-b-2 border-transparent` |
| Hover | `bg-secondary/50` |
| Active | `bg-background`, `text-foreground`, `border-bottom-color: #3b82f6`（蓝色底边） |

**所有按钮均为 bordered 样式**，不使用 `font-medium`，统一带有 `border border-[--color-border]`。

**实现伪代码**：

```tsx
function AgentTab({ agent, isActive, onClick, onConfig }: AgentTabProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const activeTeamMemberName = useAppStore((s) => s.activeTeamMemberName);
  const removeAgent = useAppStore((s) => s.removeAgent);
  const isTeam = agent.type === "team";
  
  const displayName = useMemo(() => {
    if (!isTeam) return agent.name;
    if (agent.name !== activeAgentId || !activeTeamMemberName) return agent.name;
    const member = agent.members?.find(m => m.name === activeTeamMemberName);
    return member ? `${agent.name} › ${member.name}` : agent.name;
  }, [agent, isTeam, activeAgentId, activeTeamMemberName]);

  const handleDelete = (deleteFiles: boolean) => {
    setDeleteDialogOpen(false);
    removeAgent(agent.id, deleteFiles);
  };

  // ... return JSX with DropdownMenu, Settings2 button, Trash2 button, ConfirmDialog
}
```

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

```tsx
function TeamDropdown({ agent }: TeamDropdownProps) {
  const activeTeamMemberName = useAppStore((s) => s.activeTeamMemberName);
  const selectTeamMember = useAppStore((s) => s.selectTeamMember);
  const openConfigDialog = useAppStore((s) => s.openConfigDialog);

  return (
    <div className="w-52 bg-white rounded-lg shadow-lg border border-border p-1.5">
      {agent.members?.map((member) => (
        <button key={member.name} onClick={() => selectTeamMember(agent.id, member.name)}
          className={cn(/* ... */, activeTeamMemberName === member.name && "bg-primary/10 text-primary")}>
          <div className="flex items-center gap-2"><User className="w-4 h-4" /><span>{member.name}</span></div>
          <button onClick={(e) => { e.stopPropagation(); openConfigDialog("edit", "agent", member.name); }}
            className="w-5 h-5 flex items-center justify-center rounded hover:bg-muted">
            <Settings2 className="w-3 h-3" />
          </button>
        </button>
      ))}
      {/* Separator + Team Settings row */}
    </div>
  );
}
```

**选中逻辑**：

```typescript
// store 中的 action（使用 id (UUID) 作为标识；workingDir 是顶层字段，旧的 policy.cwd 已弃用）
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

当 `activeTeamMemberName === null` 时，展示的是 Team 整体的视图；当有值时，展示的是特定成员的视图。

---

### 3.6 UserMenu

**文件**：`src/components/layout/UserMenu.tsx`

**职责**：用户菜单占位符，当前阶段仅显示一个用户图标。

```tsx
function UserMenu() {
  return (
    <button className="flex items-center justify-center w-12 h-12 
                       hover:bg-(--color-secondary) rounded-md transition-colors">
      <UserCircle2 className="w-5 h-5 text-(--color-muted-foreground)" />
    </button>
  );
}
```

后续可扩展：主题切换、快捷键帮助、关于页面等。

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
- 展示方式：通过 `AppIcon.tsx` 中的 `fixed inset-0 flex items-center justify-center` 居中 overlay 展示（非 Popover 锚定）
- 背景：`bg-white`
- 圆角：`rounded-xl`
- 阴影：`shadow-2xl`
- 边框：`border border-border`
- 使用 `flex flex-col` 布局

**Settings 的有效 Tab 类型**：

```typescript
export type SettingsTab = "models" | "skills" | "mcps" | "prompts";
```

### 4.2 标题栏

```
┌───────────────────────────────────────────┐
│ ⚙  Settings                          [×]  │
└───────────────────────────────────────────┘
```

- 高度 48px，`flex items-center justify-between`
- 左侧：Settings 图标 + "Settings" 标题
- 右侧：关闭按钮（Lucide `X` 图标）
- 底部 `border-b border-border`

### 4.3 Tab 标签栏

```
┌───────────────────────────────────────────┐
│  Models   Skills    MCPs    Prompts       │
└───────────────────────────────────────────┘
```

使用 Radix Tabs 组件。Skills 和 MCPs 模块包含 "Import from Folder" 按钮，点击后打开 `FolderPickerModal` 选择文件夹，选择后直接调用对应的后端 import API（`POST /api/skills/import`、`POST /api/mcps/import`、`POST /api/prompts/import`），成功后刷新 Store 列表。

MCPs 模块的详情页 header 右侧包含 "Discover Tools" 按钮（RefreshCw 图标），点击后调用 `POST /api/mcps/{id}/discover` 重新发现该 MCP 服务器的工具列表，同时更新 MCPServerConfig.tools 和 ToolFactory 注册。按钮在请求期间显示旋转动画和 "Discovering..." 文字，完成后 toast 提示发现的工具数量。

### 4.4 初始 Tab 指定

在 Store 中维护 `settingsActiveTab`，`AppIcon` 打开 Popover 时从 Store 读取初始值。

```typescript
// store 中新增：
isSettingsOpen: boolean;
settingsActiveTab: SettingsTab;
openSettings: (tab?: SettingsTab) => void;
closeSettings: () => void;
```

`SettingsPopover` 内部使用本地 state 追踪当前 Tab（允许用户在 Popover 内自由切换），但初始化时从 `settingsActiveTab` 取值。

### 4.5 四个 Module 组件的兼容性

`ModelsModule`、`SkillsModule`、`MCPsModule`、`PromptsModule` 当前设计为独立全宽组件。嵌入 `SettingsPopover` 后需要确保：

1. 移除组件内部的 `min-h-screen` 类
2. 调整内部 `padding` 以适配 Popover 的 `p-4` 包裹
3. 如有内部状态（如 `selectedModelId`），保留在 Store 中共享

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
  agentName?: string;                // 编辑模式时传入，用于回填表单（使用 name 而非 id）
}
```

### 5.2 与旧版 CreateAgentDialog 的差异

| 旧版 | 新版 |
|------|------|
| 始终为新建模式 | 支持新建 + 编辑两种模式 |
| 步骤 1 选择类型 | `type` 由 props 传入，跳过类型选择 |
| 独立的 `isCreateDialogOpen` | 合并到统一的 `configDialog` 状态 |
| 创建后关闭弹窗 | 编辑模式下保存后更新 Store 数据并关闭 |
| Dialog 宽度 `max-w-lg` | `max-w-4xl`，双栏布局 |
| Agent 表单包含 BasePath 字段 | BasePath 字段已移除 |
| 单栏布局 | 双栏布局（左：基本配置 / 右：Tools + Policy） |
| `agentId` 标识 | `agentName` 标识 |

### 5.3 双栏布局

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
│  │ ☐ skill-a  ☐ skill-b      │   │ │ ☐ ls                           │ │   │
│  │ ☐ skill-c                  │   │ ├──────────────────────────────┤ │   │
│  │ Built-in Hook    [on off]  │   │ │ MCP: server-a           [☑] │ │   │
│  └─────────────────────────────┘   │ │ ☐ mcp-tool-1                  │ │   │
│                                     │ └──────────────────────────────┘ │   │
│                                     │                                    │   │
│                                     │ Policy                             │   │
│                                     │ ┌──────────────────────────────┐ │   │
│                                     │ │ Working Dir (cwd)            │ │   │
│                                     │ │ [___________] [📂 Browse]    │ │   │
│                                     │ │ Allowed Dirs [___________]   │ │   │
│                                     │ │ Max Read Size [______]       │ │   │
│                                     │ │ ...                          │ │   │
│                                     │ └──────────────────────────────┘ │   │
│                                     └──────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

**布局细节**：
- 对话框宽度：`max-w-4xl`（896px），container 内边距 `p-8`（32px）
- 使用 `grid grid-cols-2 gap-8` 实现双栏布局
- 标题栏使用 `flex items-start justify-between`，右侧放置 Create Agent / Save Changes 按钮（`pr-10` 避免与右上角关闭按钮重叠）
- **左栏**（基本信息 + Skills）：Name、**Working Directory**（新位置：Name 之下、Model 之上）、Model、System Prompt（含 Prompt Library 选择器）、Skills
- **右栏**（Tools + Hooks）：Tools 标题旁**单个齿轮**打开全局 `ToolPolicy` 弹窗；Built-in Hooks 每个 hook 一个 toggle，标题旁**单个齿轮**打开 `HookConfig` 弹窗；**Built-in Tools 和每个 MCP Server 标题行右侧有全选勾选框**，勾选后全选/取消全选其下方所有工具，支持半选（indeterminate）状态
- **二级弹窗**：
  - `ToolPolicyDialog`：maxReadSize / maxReadLines / maxWriteSize / writeCreateDirectories / bashMaxOutputLines / bashDefaultTimeout（不含 cwd）
  - `HookConfigDialog`：由 `GET /api/hooks` 描述符动态驱动，按 section 折叠，字段类型覆盖 string/text/number/float/boolean/modelId
- 两栏右内边距 `pr-4`（16px），确保内容与滚动条之间有足够间距
- Working Directory 使用 `FolderPicker` 组件让用户浏览并选择文件夹；后端将其映射到 `toolPolicy.cwd`，前端 `toolPolicy` 字典中不再含 `cwd` 字段

### 5.4 字段三组分类

AgentConfigDialog 提交的 payload 字段按三组分类（与 [api-mapping.md#7.1](file:///Users/gonglin/Desktop/note/BBagent/doc/api-mapping.md) 对齐）：

| 组 | 字段 | 说明 |
|----|------|------|
| Basic | `name`、`modelId`、`systemPrompt`、`workingDir` | Working Directory 是用户可填的 cwd，映射到后端 `toolPolicy.cwd` |
| Tools | `toolNames`、`skillNames`、`toolPolicy` | `toolPolicy` 是所有内置工具共享的配置，**不含 cwd** |
| Hooks | `hookNames`、`hookConfig` | `hookNames` 是启用的 hook 列表；`hookConfig` 是共享大字典 |

### 5.5 BasePath 字段移除

BasePath 字段已从 AgentConfigDialog 的 UI 中移除（前端不发送）。后端 `create_agent` 中 `base_dir` 固定设为 `DATA_DIR/agents`，在响应中回填 `basePath` 字段供 BasedirTree 渲染文件树。

### 5.5 Name 自动生成

Agent 的 `name` 字段支持留空。如果用户不填写 name，后端 `CoreAgentConfig` 会自动生成一个默认名称。创建/更新后的响应数据中的 `name` 会回流传给前端 Store，确保前端始终知道正确的 agent name。

**前端创建流程**：

```typescript
// store.ts
createAgentApi: async (agent: Agent) => {
    const created = await api.createAgent(agent);   // POST /api/agents, 返回完整 AgentConfig
    set((state) => ({
      agents: [...state.agents, created],
      activeAgentId: created.id,                // 使用后端返回的 id（UUID）
    }));
},
```

### 5.6 ChatWindow Layout & Message Display

**消息区域布局**：
- 消息列表使用 `w-full max-w-[880px] mx-auto px-4` 居中显示，`w-full` 确保面板宽度小于 880px 时内容自适应收缩
- 消息内容区使用 `flex-1 min-w-0 overflow-hidden`，确保 flex 子元素不会超出容器宽度
- 滚动容器设置 `overflow-x-hidden`，禁止横向滚动
- 当文件预览面板（Panel C）出现时，消息窗口宽度被压缩，消息内容自动换行
- 拖拽调整面板宽度时，消息内容同样自动换行以适应新的可用宽度

**文本换行处理**：
- 所有 Markdown 渲染内容（p、li、blockquote、h1-h4）均设置 `break-words`（`overflow-wrap: break-word`），确保长单词/长 URL 自动断行
- 用户消息段落使用 `whitespace-pre-wrap break-words`，保留空白同时防止溢出
- 代码块内部保留 `overflow-x-auto`，允许代码块独立横向滚动（不影响外层窗口）
- 内联代码使用 `whitespace-nowrap`，保持格式完整
- TurnBlock/TurnGroup 的内容容器添加 `min-w-0 break-words`，确保 Markdown 内容在 flex 布局中正确换行

**消息列表居中**：
- 消息内容 wrapper 使用 `w-full max-w-[880px] mx-auto px-4` 实现水平居中，`px-4` 提供左右留白
- 输入区域同样使用 `w-full max-w-[880px] mx-auto px-4` 居中对齐
- TurnBlock/TurnGroup 使用 `mx-4` 替代 `mx-8`，配合外层 `px-4` 实现合理留白
- TurnDots 导航点位于消息内容右侧，随内容居中布局

**Markdown 渲染格式支持**：

| 格式 | 支持情况 | 组件 | 说明 |
|------|---------|------|------|
| 标题 (h1-h4) | ✅ | `h1`-`h4` | 自定义样式，不同字号 |
| 粗体 | ✅ | `strong` | 默认渲染 |
| 斜体 | ✅ | `em` | 默认渲染 |
| 删除线 | ✅ | `del` | `remark-gfm` 支持 |
| 行内代码 | ✅ | `code` | 灰色背景 + 边框样式 |
| 代码块 | ✅ | `pre` + `CodeBlock` | Prism 语法高亮，支持语言标识 |
| 表格 | ✅ | `table`/`th`/`td` | 自定义样式，响应式滚动 |
| 无序列表 | ✅ | `ul`/`li` | 圆点样式 |
| 有序列表 | ✅ | `ol`/`li` | 数字样式 |
| 任务列表 | ✅ | `input[type=checkbox]` | GFM checkbox 支持 |
| 链接 | ✅ | `a` | 新窗口打开，primary 颜色 |
| 图片 | ✅ | `img` | 自适应宽度，圆角边框 |
| 引用块 | ✅ | `blockquote` | 左侧边框样式 |
| 分割线 | ✅ | `hr` | 软边框样式 |

**代码块高亮实现**：

使用 `prism-react-renderer` v2 进行语法高亮，支持语言包括：JavaScript/TypeScript、Python、HTML/CSS、JSON、YAML、Bash 等常见语言。

关键实现细节：
- 通过 `pre` 组件检测代码块结构（`pre > code`），提取语言标识和内容
- 行内代码（无 `className`）使用简单样式渲染
- 代码块内的 `code` 组件返回 `null`，由 `pre` 组件统一处理
- 流式渲染时，`SafeMarkdown` 错误边界捕获不完整 Markdown 解析错误，回退到纯文本显示

### 5.7 ChatWindow WebSocket + Session Management + Streaming

ChatWindow connects to the backend via a single persistent WebSocket (`ws://.../api/ws/chat`) for real-time streaming. Agent subscription is changed via `switch_agent` messages instead of closing and reopening the connection. It also handles history loading, session management, and streaming text accumulation.

**Connection lifecycle**:
1. On mount: create a single WebSocket connection
2. WS `onopen`: send `switch_agent` for the current `activeAgentId`
3. On agent switch: first `await loadAgentMessages()` (HTTP), then send `switch_agent` with replay
4. On session switch: only `loadAgentMessages()` (HTTP), no WS switch needed
5. On unmount: close WebSocket, clear reconnect timer
6. On unexpected disconnect: auto-reconnect with exponential backoff (1s → 2s → 4s → ... → 30s max), re-send `switch_agent` on reconnect

**History loading and replay**: Before sending `switch_agent`, `GET /agents/{name}/messages` fetches past conversation turns and populates the agent's `messages` array. After `switch_agent`, the backend replays any buffered chunks from the current in-progress round (via dispatcher `replay=True`). Since history loading must complete before `switch_agent`, HTTP history and WS replay are guaranteed non-overlapping.

**Streaming text accumulation**: When `text` chunks arrive via WebSocket, the accumulated text replaces the last assistant message's `content` field in-place (not appending new messages). When `completed_message` arrives, the buffer resets. This gives the effect of text appearing character-by-character in the last bubble.

**Interrupt button toggle**: The send button toggles between Send (Send icon) and Interrupt (Square icon, red background) based on agent state. When `agentState === "running"`, the Interrupt button is shown. When `agentState === "waiting"`, the Send button is enabled (disabled when input is empty). When `agentState` is `"ready"` or `"error"`, the Send button is disabled:
- Not streaming → Send button (enabled when input non-empty)
- Streaming → Cancel/Interrupt button (sends `{"type": "interrupt"}` via WebSocket)
- Pressing Enter while streaming also triggers interrupt

**Session switcher dropdown**: A dropdown in the chat header shows all sessions (from `agentSessions`). Each session entry shows:
- Session ID (truncated to 19 chars)
- Turn count
- Active indicator

A "New Session" button at the bottom calls `POST /agents/{name}/sessions/new`, which creates a new session, refreshes the session list, and clears messages. Clicking an existing session calls `POST /agents/{name}/sessions/{id}/switch` then reloads messages.

**Thinking and tool chunk display**: `MessageBubble` renders messages by `chunkType`:
- `thinking` — Purple background, italic text, "Thinking" label
- `tool_use` — Orange background, shows tool name and JSON input
- `tool_result` — Orange background, shows tool name and truncated result

**Agent state display**: The chat header shows the current agent state with a colored dot:
- `ready` — gray dot
- `waiting` — green dot
- `running` — green pulsing dot
- `error` — red dot

State is updated from both HTTP response (agent list) and WebSocket `agent_state` chunks. The backend now emits `agent_state` on every state transition (`running`, `waiting`, `error`, `ready`), making the frontend a passive receiver of authoritative state from the backend — no optimistic state guessing.

**WebSocket message types (backend → frontend)**:
- `agent_state` — agent state change notification: `{"state": "running", "context_tokens": 12345}` (before processing starts), `{"state": "waiting", "context_tokens": 23456}` (after turn completes), `{"state": "error", "context_tokens": 0}` (on unhandled error), `{"state": "ready", "context_tokens": 23456}` (on stop)
- `text` — streaming text chunks from the agent
- `thinking` — thinking/reasoning chunks
- `completed_tool_use` — a tool call was made
- `tool_results` — tool execution results
- `completed_message` — full message completed (reset stream buffer)
- `switched` — confirmation of agent subscription switch (`{"agent_name": "...", "agent_state": "...", "context_tokens": 12345}`)
- `error` — error information

**WebSocket message types (frontend → backend)**:
- `switch_agent` — switch subscription to a different agent (`{"agent_id": "uuid", "agent_name": "..."}`)
- `user_message` — user's chat message
- `interrupt` — interrupt the agent

```typescript
// store 中（使用 agentName 而非 agentId）
configDialog: {
  open: false,
  mode: "create" as "create" | "edit",
  type: "agent" as "agent" | "team" | "",
  agentName: undefined as string | undefined,     // 使用 name 而非 id
},
openConfigDialog: (mode: "create" | "edit", type: "agent" | "team" | "", agentName?: string) => {
  set({
    configDialog: { open: true, mode, type, agentName },
  });
},
closeConfigDialog: () => {
  set({
    configDialog: { open: false, mode: "create", type: "", agentName: undefined },
  });
},
```

### 5.8 Timer Panel（定时任务管理面板）

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

**交互**：
- **Timer 按钮**：输入框左侧，显示 `⏱` + 任务数量 badge，点击切换面板展开/收起
- **启停按钮**：▶ 启动 / ■ 停止，运行中显示绿色圆点，停止显示黄色圆点，禁用显示灰色圆点
- **编辑按钮**：点击进入 inline 编辑模式，修改 name/seconds/hint 后保存
- **删除按钮**：点击后二次确认（✓/✗），确认后删除
- **Add Timer**：右下角按钮，点击在列表底部新增空表单行

**API 调用**：
- `GET /agents/{id}/timers` — 加载列表
- `POST /agents/{id}/timers` — 新建
- `PUT /agents/{id}/timers/{name}` — 更新
- `POST /agents/{id}/timers/{name}/start` — 启动
- `POST /agents/{id}/timers/{name}/stop` — 停止
- `DELETE /agents/{id}/timers/{name}` — 删除

**状态管理**：
- `agentTimers: Record<string, TimerConfig[]>` — 按 agentId 存储
- 切换 agent 时自动 `loadTimers(agentId)`
- 增删改操作后刷新列表

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

### 5.9 保存逻辑

**新建 Agent**：调用 `createAgentApi()` → 后端创建并返回完整 AgentConfig → Store 中 `agents` 增加一条 → 自动选中新 Agent → 关闭弹窗
**新建 Team**：调用 `createTeamApi()` → 同理
**编辑 Agent**：调用 `updateAgent(name, updates)` → 更新 Store → 关闭弹窗
**编辑 Team**：调用 `updateTeam(name, updates)`

---

## 6. FolderPicker Component

### 6.1 Overview

**文件**：`src/components/common/FolderPicker.tsx`

**组件职责**：可复用的文件夹选择下拉组件。提供文本输入框 + 浏览文件夹按钮，点击按钮展开文件系统目录树让用户导航并选择文件夹。

**Props**：

```typescript
interface FolderPickerProps {
  value: string;              // 当前选中的路径
  onChange: (path: string) => void;  // 路径变更回调
  placeholder?: string;       // 占位文本
}
```

**使用场景**：
- AgentConfigDialog 中 Policy 的 Working Directory (cwd) 选择
- Policy 中其他需要路径选择的场景

**实现**：调用 `GET /api/files/dirs?path=` 获取子目录列表，支持逐级导航和返回上级目录。

### 6.2 FolderPickerModal

**文件**：`src/components/common/FolderPickerModal.tsx`

**与 FolderPicker 的区别**：
- FolderPicker 是内联下拉组件（嵌入式，用于表单字段）
- FolderPickerModal 是全屏居中 Modal 对话框（用于独立选择流程，如 Import）

**Props**：

```typescript
interface FolderPickerModalProps {
  open: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
  title?: string;
}
```

**使用场景**：
- SkillsModule "Import from Folder" → 选择后调用 `POST /api/skills/import`
- MCPsModule "Import from Folder" → 选择后调用 `POST /api/mcps/import`
- PromptsModule "Import from Folder" → 选择后调用 `POST /api/prompts/import`

**UI 结构**：

```
┌─────────────────────────────────────┐
│ Select Folder                   [×] │  ← 标题栏
├─────────────────────────────────────┤
│ 📁 /Users/gonglin/Desktop           │  ← 当前路径面包屑
├─────────────────────────────────────┤
│ 📂 ..                               │  ← 返回上级
│ 📂 Documents                        │  ← 导航进入
│ 📂 Downloads                        │
│ 📂 Projects                         │
│ ...                                 │
├─────────────────────────────────────┤
│    [Select This Folder]  [Cancel]   │  ← 操作按钮
└─────────────────────────────────────┘
```

对话框尺寸：`w-[480px] max-h-[60vh]`。

---

## 7. ConfirmDialog Component

### 7.1 Overview

**文件**：`src/components/common/ConfirmDialog.tsx`

**组件职责**：通用确认对话框，支持三按钮（confirm / secondary / cancel）。

**Props**：

```typescript
interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;         // 主操作按钮标签
  secondaryLabel: string;       // 次操作按钮标签
  cancelLabel?: string;         // 取消按钮标签（默认 "Cancel"）
  onConfirm: () => void;
  onSecondary: () => void;
  onCancel: () => void;
  variant?: "danger" | "default";  // confirm 按钮样式变体
}
```

**使用场景**：
- AgentTab 删除 Agent：Yes（confirm, danger）= 删除 + 删文件，No（secondary）= 仅删除记录，Cancel = 取消

**按钮样式**：
- 所有按钮均为 bordered 样式（`border border-[--color-border]`），hover 时背景色变化
- Confirm 按钮：`variant="danger"` 时红色背景（`border-red-500 bg-red-500`），`variant="default"` 时使用 primary 色

---

## 8. ErrorBoundary Component

### 8.1 Overview

**文件**：`src/components/ErrorBoundary.tsx`

**组件职责**：全局错误边界，捕获 React 组件渲染错误，防止整个应用崩溃。

**实现**：

```tsx
import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-screen gap-4 bg-(--color-background)">
          <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center">
            <span className="text-2xl text-red-500">!</span>
          </div>
          <p className="text-lg font-medium text-(--color-foreground)">Something went wrong</p>
          <p className="text-sm text-(--color-muted-foreground) max-w-md text-center">
            {this.state.error?.message || "An unexpected error occurred"}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-lg bg-(--color-primary) text-(--color-primary-foreground) text-sm hover:opacity-90"
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

**使用方式**：在 `App.tsx` 中包裹应用根组件：

```tsx
<ErrorBoundary>
  <AppContent />
</ErrorBoundary>
```

---

## 9. TypeScript 类型定义

### 9.1 Agent 类型（可辨识联合类型）

Agent 拆分为 `SingleAgent` 和 `Team` 两个独立接口，通过 `type` 字段构成可辨识联合类型（discriminated union），避免单一接口包含所有可选字段。

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
  basePath: string;                  // 后端自动生成，前端只读不写
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
  basePath: string;                  // 后端自动生成
  workingDir: string;
  teamDescription: string;
  members: SingleAgent[];
  contacts: Record<string, Record<string, string>>;
}

// 可辨识联合
export type Agent = SingleAgent | Team;

// 类型守卫
export function isSingleAgent(agent: Agent): agent is SingleAgent {
  return agent.type === "single";
}

export function isTeam(agent: Agent): agent is Team {
  return agent.type === "team";
}

// 创建 Single Agent 的请求体（不含运行时字段）
export interface CreateAgentPayload {
  name: string;
  modelId: string;
  systemPrompt: string;
  workingDir: string;
  toolIds: string[];
  skillIds: string[];
  hookNames: string[];
  hookConfig: Record<string, unknown>;
  toolPolicy: ToolPolicy;
}

// 创建 Team 的请求体（包含 member 配置列表）
export interface CreateTeamPayload {
  name: string;
  teamDescription: string;
  workingDir: string;
  members: CreateAgentPayload[];
  contacts: Record<string, Record<string, string>>;
}

// toolPolicy 字段都是可选；缺失的字段由 ToolPolicyDialog 的默认值兜底
export interface ToolPolicy {
  maxReadSize?: number;
  maxReadLines?: number;
  maxWriteSize?: number;
  writeCreateDirectories?: boolean;
  bashMaxOutputLines?: number;
  bashDefaultTimeout?: number;
}

// === Hook 描述符（GET /api/hooks 响应）===
export type HookFieldType = "string" | "text" | "number" | "float" | "boolean" | "modelId";
export interface HookFieldSchema { key: string; type: HookFieldType; label: string; default: unknown; description: string; }
export interface HookSection { title: string; fields: HookFieldSchema[]; }
export interface HookDescriptor {
  name: string; displayName: string; description: string;
  defaultEnabled: boolean; fieldSections: HookSection[];
}
export interface HookListResponse { hooks: HookDescriptor[]; sharedSections: HookSection[]; }
```

### 9.2 其他类型

| 类型 | 标识字段 | 说明 |
|------|---------|------|
| `Model` | `id: string` | UUID 标识 |
| `Skill` | `name: string` | 名称为标识，`source` 区分 default/imported |
| `MCPServer` | `name: string` | 名称为标识，`source` 区分 default/imported |
| `Prompt` | `id: string` | UUID 标识，`group` 字段支持分组管理（空字符串=未分组） |
| `Message` | `id: string` | UUID 标识，含 `chunkType`, `thinking`, `toolName`, `toolInput`, `toolResult`, `sourceAgent` |
| `SessionInfo` | `id: string` | 会话 ID，含 `timestamp`, `turnCount`, `isActive` |
| `Tool` | `id: string` | UUID 标识 |

---

## 10. Zustand Store

### 10.1 Store 核心状态

```typescript
export interface AppState {
  agents: Agent[];
  activeAgentId: string | null;           // 使用 id (UUID) 而非 name
  activeTeamMemberName: string | null;
  setActiveAgentId: (name: string | null) => void;
  selectTeamMember: (teamId: string, memberName: string | null) => void;
  addAgent: (agent: Agent) => void;
  addTeam: (agent: Agent) => void;
  updateAgent: (name: string, updates: Partial<Agent>) => void;
  updateTeam: (name: string, updates: Partial<Agent>) => void;
  removeAgent: (name: string, deleteFiles?: boolean) => Promise<void>;
  addMessage: (agentName: string, message: Message) => void;

  // Agent lifecycle state — single source of truth for all UI decisions
  agentStates: Record<string, "ready" | "waiting" | "running" | "error">;
  agentSessions: Record<string, SessionInfo[]>;
  setAgentState: (name: string, state: "ready" | "waiting" | "running" | "error") => void;
  loadAgentSessions: (name: string) => Promise<void>;
  switchSession: (name: string, sessionId: string) => Promise<void>;
  createNewSession: (name: string) => Promise<void>;
  loadAgentMessages: (name: string) => Promise<void>;
  startAgent: (name: string) => Promise<void>;
  stopAgent: (name: string) => Promise<void>;

  isSettingsOpen: boolean;
  settingsActiveTab: SettingsTab;
  openSettings: (tab?: SettingsTab) => void;
  closeSettings: () => void;

  configDialog: {
    open: boolean;
    mode: "create" | "edit";
    type: "agent" | "team" | "";
    agentName?: string;                     // 使用 agentName 而非 agentId
  };
  openConfigDialog: (mode: "create" | "edit", type: "agent" | "team" | "", agentName?: string) => void;
  closeConfigDialog: () => void;

  workingDirPath: string;
  setWorkingDirPath: (path: string) => void;
  baseDirPath: string;
  setBaseDirPath: (path: string) => void;

  // Agent lifecycle state — single source of truth for all UI decisions
  agentStates: Record<string, "ready" | "waiting" | "running" | "error">;
  agentSessions: Record<string, SessionInfo[]>;

  // ... 其他状态（models, tools, mcpServers, skills, prompts, etc.）
}
```

### 10.2 关键 Store Actions

```typescript
// setActiveAgentId: 切换 agent 时同步更新 working dir 和 base dir
setActiveAgentId: (id) => {
  const agent = id ? get().agents.find((a) => a.id === id) : null;
  set({
    activeAgentId: id,
    activeTeamMemberName: null,
    workingDirPath: agent?.workingDir || "",
    baseDirPath: agent?.basePath || "",
    previewFile: null,
  });
},

// createAgentApi: 发送到后端，使用后端返回的数据（可能包含自动生成的 name）
createAgentApi: async (agent: Agent) => {
  const created = await api.createAgent(agent);
  set((state) => ({
    agents: [...state.agents, created],
    activeAgentId: created.id,
  }));
},

// createTeamApi: 同上
createTeamApi: async (team: Agent) => {
  const created = await api.createTeam(team);
  set((state) => ({
    agents: [...state.agents, created],
    activeAgentId: created.id,
  }));
},

// removeAgent: 支持可选的 deleteFiles 参数
removeAgent: async (name, deleteFiles) => {
  const agent = get().agents.find((a) => a.id === id);
  if (!agent) return;
  await api.deleteAgent(agent.id, deleteFiles);
  set((state) => ({
    agents: state.agents.filter((a) => a.id !== id),
    activeAgentId: state.activeAgentId === id ? null : state.activeAgentId,
    previewFile: state.activeAgentId === id ? null : state.previewFile,
  }));
},

// Agent lifecycle
startAgent: async (name: string) => {
  const result = await api.startAgent(name);
  get().setAgentState(name, result.state);
},

stopAgent: async (name: string) => {
  const result = await api.stopAgent(name);
  get().setAgentState(name, result.state);
},

setAgentState: (name, state) =>
  set((s) => ({
    agentStates: { ...s.agentStates, [name]: state },
    agents: s.agents.map((a) => (a.id === id ? { ...a, state } : a)),
  })),

// Session management
loadAgentSessions: async (name: string) => {
  const sessions = await api.listSessions(name);
  set((s) => ({ agentSessions: { ...s.agentSessions, [name]: sessions } }));
},

switchSession: async (name: string, sessionId: string) => {
  await api.switchSession(name, sessionId);
  // mark selected session as active
  const sessions = get().agentSessions[name] || [];
  set((s) => ({
    agentSessions: {
      ...s.agentSessions,
      [name]: sessions.map((sess) => ({ ...sess, isActive: sess.id === sessionId })),
    },
  }));
  await get().loadAgentMessages(name);
},

createNewSession: async (name: string) => {
  const result = await api.newSession(name);
  await get().loadAgentSessions(name);
  set((s) => ({
    agents: s.agents.map((a) =>
      a.id === id ? { ...a, messages: [], currentSessionId: result.session_id } : a
    ),
  }));
},

loadAgentMessages: async (name: string) => {
  const messages = await api.getAgentMessages(name);
  set((s) => ({
    agents: s.agents.map((a) =>
      a.id === id ? { ...a, messages } : a
    ),
  }));
},
```

### 10.3 导入 Actions

```typescript
// Skills import: FolderPickerModal → api.importSkills(path) → refresh list
importSkills: async (path: string) => {
  const result = await api.importSkills(path);
  if (result.imported > 0) {
    const skills = await api.listSkills();
    set({ skills: skills || [] });
  }
},

// MCPs import: FolderPickerModal → api.importMcps(path) → refresh list
importMcpServers: async (path: string) => {
  const result = await api.importMcps(path);
  if (result.imported > 0) {
    const mcps = await api.listMcps();
    set({ mcpServers: mcps || [] });
  }
},

// Prompts import: FolderPickerModal → api.importPrompts(path) → refresh list
importPrompts: async (path: string) => {
  const result = await api.importPrompts(path);
  if (result.imported > 0) {
    const prompts = await api.listPrompts();
    set({ prompts: prompts || [] });
  }
},
```

---

## 11. API Client

**文件**：`src/lib/api.ts`

基于 `fetch` 的简单 API 客户端，所有 `id` 类型的参数已更新为 `name`：

```typescript
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

async function request(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  listModels: () => request("/models"),
  createModel: (data) => request("/models", { method: "POST", body: JSON.stringify(data) }),
  updateModel: (id, data) => request(`/models/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteModel: (id) => request(`/models/${id}`, { method: "DELETE" }),
  testModel: (id, prompt) => request(`/models/${id}/test`, { method: "POST", body: JSON.stringify({ prompt }) }),

  listMcps: () => request("/mcps"),
  importMcps: (path) => request("/mcps/import", { method: "POST", body: JSON.stringify({ path }) }),
  // ...

  listPrompts: () => request("/prompts"),
  importPrompts: (path) => request("/prompts/import", { method: "POST", body: JSON.stringify({ path }) }),
  // ...

  listSkills: () => request("/skills"),
  importSkills: (path) => request("/skills/import", { method: "POST", body: JSON.stringify({ path }) }),

  listAgents: () => request("/agents"),
  createAgent: (data) => request("/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgent: (name, data) => request(`/agents/${name}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteAgent: (name, deleteFiles?) =>
    request(`/agents/${name}${deleteFiles ? '?delete_files=true' : ''}`, { method: "DELETE" }),
  // ...

  listTeams: () => request("/teams"),
  createTeam: (data) => request("/teams", { method: "POST", body: JSON.stringify(data) }),
  // ...

  listDirs: (path) => request(`/files/dirs?path=${encodeURIComponent(path)}`),
  getFileTree: (path) => request(`/files/tree?path=${encodeURIComponent(path)}`),
  readFile: (path) => request(`/files/read?path=${encodeURIComponent(path)}`),
  writeFile: (path, content) => request("/files/write", { method: "POST", body: JSON.stringify({ path, content }) }),

  getState: () => request("/state"),
  saveState: (data) => request("/state", { method: "POST", body: JSON.stringify(data) }),
};
```

---

## 12. Workspace View

### 12.1 WorkspaceView Container

**文件**：`src/components/workspace/WorkspaceView.tsx`

**组件职责**：核心工作区的布局容器，管理三栏动态布局和面板宽度状态。

面板宽度通过 `useState` 管理，A/C 面板之间各有一个 `PanelSplitter` 分隔条供拖拽调整宽度。

```tsx
function WorkspaceView() {
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const activeTeamMemberName = useAppStore((s) => s.activeTeamMemberName);
  const agents = useAppStore((s) => s.agents);
  const previewFile = useAppStore((s) => s.previewFile);
  const [panelAWidth, setPanelAWidth] = useState(300);
  const [panelCWidth, setPanelCWidth] = useState(360);

  const activeAgent = agents.find((a) => a.id === activeAgentId);
  const showTeamChat = activeAgent?.type === "team" && !activeTeamMemberName;

  return (
    <div className="flex flex-1 overflow-hidden">
      <PanelA_FilePanel width={panelAWidth} />
      <PanelSplitter onResize={handlePanelAResize} />
      <div className="flex-1 flex flex-col overflow-hidden">
        {showTeamChat ? <TeamChatWindow /> : <ChatWindow />}
      </div>
      {previewFile && (
        <>
          <PanelSplitter onResize={handlePanelCResize} />
          <PanelC_FilePreview width={panelCWidth} />
        </>
      )}
    </div>
  );
}
```

**routing logic**:
- No agent selected → empty state placeholder
- Single agent selected → `ChatWindow` (standard chat)
- Team selected **without** a member → `TeamChatWindow` (group chat with @mention)
- Team selected **with** a member → `ChatWindow` (1:1 chat with that member)

### 12.2 PanelSplitter Component

**文件**：`src/components/workspace/Splitter.tsx`

**Props**：`onResize: (delta: number) => void` — 鼠标拖动时的位移回调。

面板间的垂直分隔条（左右拖拽），宽 4px，hover 时颜色加深。拖拽过程中全局禁用文本选择并锁定光标样式为 `col-resize`，松手后恢复。

### 12.3 useSelectedAgent Hook

```typescript
export const useSelectedAgent = () => {
  const agents = useAppStore((s) => s.agents);
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const activeTeamMemberName = useAppStore((s) => s.activeTeamMemberName);
  if (!activeAgentId) return null;
  const agent = agents.find((a) => a.id === activeAgentId);
  if (!agent) return null;
  if (agent.type === "team" && activeTeamMemberName) {
    return agent.members?.find((m) => m.name === activeTeamMemberName) ?? null;
  }
  return agent;
};
```

---

## 13. Panel A: File Panel (上下分屏)

### 13.1 PanelA_FilePanel Container

**文件**：`src/components/workspace/PanelA_FilePanel.tsx`

**Props**：`width: number` — 面板像素宽度，由父组件 `WorkspaceView` 传入，范围 200px ~ 500px。

参考布局与之前版本一致。面板顶部 Working Dir 初始值来自 `agent.workingDir`（顶层字段，旧的 `agent.policy.cwd` 已弃用），底部 Base Dir 来自 `agent.basePath`（后端自动生成）。

### 13.2 WorkingDirView & BasedirTree

与 v4 设计保持一致。文件树数据通过 `GET /api/files/tree` 和 `GET /api/files/read` 获取。

## 13.3 Panel C: File Preview

**文件**：`src/components/workspace/PanelC_FilePreview.tsx`

**Props**：`width: number` — 面板像素宽度，由父组件 `WorkspaceView` 传入，范围 220px ~ 600px。

右侧文件预览面板，通过 `renderPreview()` 函数根据 MIME 类型分发到对应查看器。

### 预览状态

| 状态 | 条件 | 组件 | 说明 |
|------|------|------|------|
| Loading | `content === null && !error` | `LoadingViewer` | Spinner + "Loading file..." |
| Error | `error` 字段存在 | `ErrorViewer` | 红色错误图标 + 错误信息 |
| Unsupported | MIME 不被支持 | `UnsupportedViewer` | 提示用外部编辑器打开 |

### 支持的文件类型与查看器

| MIME 类型 | 文件扩展名 | 查看器 | 渲染方式 |
|-----------|-----------|--------|----------|
| `text/typescript` | `.ts`, `.tsx` | `CodeViewer` | prism-react-renderer 语法高亮 (lang=tsx) |
| `text/javascript` | `.js`, `.jsx` | `CodeViewer` | prism-react-renderer 语法高亮 (lang=js) |
| `text/x-python` | `.py` | `CodeViewer` | prism-react-renderer 语法高亮 (lang=python) |
| `text/html` | `.html` | `CodeViewer` | prism-react-renderer 语法高亮 (lang=html) |
| `text/css` | `.css` | `CodeViewer` | prism-react-renderer 语法高亮 (lang=css) |
| `application/json` | `.json` | `CodeViewer` | prism-react-renderer 语法高亮 (lang=json) |
| `text/yaml` | `.yaml`, `.yml` | `CodeViewer` | prism-react-renderer 语法高亮 (lang=yaml) |
| `text/plain` | `.txt`, `.env`, `.gitignore` 等 | `CodeViewer` | 无语法高亮 (lang=text) |
| `text/markdown` | `.md` | `MarkdownViewer` | react-markdown 渲染 + Tailwind prose 样式 |
| `image/png` | `.png` | `ImageViewer` | `<img src="/api/files/raw?path=...">` |
| `image/jpeg` | `.jpg`, `.jpeg` | `ImageViewer` | 同上 |
| `image/gif` | `.gif` | `ImageViewer` | 同上 |
| `image/svg+xml` | `.svg` | `ImageViewer` | 同上 |
| `image/webp` | `.webp` | `ImageViewer` | 同上 |
| `application/pdf` | `.pdf` | `PdfViewer` | `<iframe src="/api/files/raw?path=...">` |

### MIME 类型推断

公共工具函数 `getMimeType()` 位于 `src/lib/utils.ts`，基于文件扩展名映射到 MIME 类型。`WorkingDirView` 和 `BasedirTree` 共用此函数。

### 数据加载流程

```
点击文件 → openFilePreview({ content: null }) → 显示 LoadingViewer
        → api.readFile(path) 获取文本内容
        → 成功: openFilePreview({ content: "..." }) → 显示对应查看器
        → 失败: openFilePreview({ error: message }) → 显示 ErrorViewer

图片/PDF 渲染: ImageViewer/PdfViewer 通过 <img>/<iframe> src="/api/files/raw?path=..." 加载
```

---

## 13.4 Panel C: Team Contacts View

**文件**：`src/components/workspace/TeamGraphView.tsx`

**依赖**：`@xyflow/react`（React Flow）、`dagre`（自动布局）

**Props**：`width: number` — 面板像素宽度

当选中 Team 且 `teamGraphOpen` 为 true 时，右侧面板显示 Team Contacts 视图，支持拓扑图/列表双视图切换。

### 双视图模式

| 模式 | 说明 |
|------|------|
| 拓扑图（默认） | React Flow + dagre 自动布局，支持缩放/平移/拖拽，自定义 AgentNode 和 BidirectionalEdge |
| 列表 | 卡片列表，每个 agent 一张卡片，点击展开显示其 contacts（队友名 + role） |

- **左上角切换按钮**：在拓扑图/列表之间切换
- **右上角关闭按钮**：关闭面板（设置 `teamGraphOpen = false`）

### 数据来源

- **节点**：`team.members`（每个 member 是一个节点）
- **边**：`team.contacts`（`Record<string, Record<string, string>>`），key 是源 agent name，内层 key 是目标 agent name，value 是 role
- **状态色**：从 `agentStates[id]` 获取各节点实时状态

### 拓扑图布局

使用 dagre 层次布局算法，参数：
- `rankdir: "TB"`（从上到下）
- `nodesep: 70`（同层节点间距）
- `ranksep: 90`（层间距）

React Flow 提供 `fitView` 自动适配视口，`minZoom: 0.3`，`maxZoom: 2`。

### 自定义组件

| 组件 | 说明 |
|------|------|
| AgentNode | 圆角矩形卡片，左侧状态点 + agent 名字，边框色/背景色按状态 |
| BidirectionalEdge | 贝塞尔曲线，沿法线偏移 25px，中间显示 role 标签 |

### Store 状态

- `teamGraphOpen: boolean` — 控制面板显示/隐藏
- `toggleTeamGraph()` — 切换面板（同时关闭其他互斥面板）
- `closeTeamGraph()` — 关闭面板

---

## 14. TeamChatWindow

**文件**：`src/components/chat/TeamChatWindow.tsx`

Team group chat component shown when a team is selected without picking a specific member. Connects via WebSocket to `ws://.../api/ws/team/{team_name}`.

**Features**:

- **@mention autocomplete**: Typing `@` triggers a dropdown listing all team members. Filtered by partial name input. Clicking a member inserts `@name ` into the input. Each member is shown with a colored avatar circle.
- **Agent-colored messages**: Each agent member gets a unique color from a palette (blue, red, green, amber, purple, pink, cyan, lime, orange, indigo). Messages from agent members are color-coded with the agent name label and agent-colored avatar.
- **Multi-member routing**: Messages can @mention multiple agents simultaneously. Backend distributes the same message to all mentioned agents' input queues.
- **Mention parsing**: Frontend extracts `@name` patterns via regex before sending. If no `@mentions` are found, the backend returns a system message prompting the user to use `@agent_name`.

**WebSocket protocol**:

| Direction | Type | Fields | Description |
|-----------|------|--------|-------------|
| Frontend → Backend | `user_message` | `content`, `mentions` (optional array) | Message with optional explicit mention list |
| Backend → Frontend | `text` | `content`, `source_agent` | Text chunk from a team member |
| Backend → Frontend | `thinking` | `content`, `source_agent` | Thinking/reasoning chunks |
| Backend → Frontend | `system` | `content` | System messages (join/leave, etc.) |
| Backend → Frontend | `error` | `content`, `source_agent` | Error messages from agents |

**Message bubble styling**:
- User messages: Primary color avatar, right-aligned
- Agent messages: Colored avatar (based on agent color mapping), left-aligned with agent name label
- System messages: Centered, muted style

**Color palette for agents**:
```typescript
const AGENT_COLORS = [
  "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
  "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
];
```

**Component structure**:
```tsx
function TeamChatWindow() {
  // Get current team from store
  const team = agents.find((a) => a.id === activeAgentId && a.type === "team");
  
  // WebSocket connection to team endpoint
  const connectWs = useCallback((teamName: string) => {
    const ws = new WebSocket(`${wsBase}/ws/team/${teamName}`);
    // Handle incoming messages: text, thinking, system, error
  }, []);
  
  // @mention autocomplete logic
  const handleInputChange = (e) => {
    // Detect @pattern at end of input
    // Show dropdown with filtered members
  };
  
  // Send message with mentions parsing
  const handleSend = () => {
    // Extract @mentions via regex
    // Send user_message with mentions array
  };
}
```

---

## 15. Onboarding Flow

**文件**：`src/components/onboarding/OnboardingView.tsx`

New user onboarding flow shown when no agents exist. Guides users through:
1. Welcome screen
2. Model configuration
3. First agent creation

---

## 16. Styling Conventions

### 16.1 CSS Variables

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

### 16.2 Tailwind Patterns

- **Bordered buttons**: All buttons use `border border-(--color-border)`
- **Rounded corners**: Consistent `rounded-lg` (8px) or `rounded-xl` (12px)
- **Transitions**: `transition-colors` or `transition-all duration-200`
- **Focus states**: `focus:outline-none focus:ring-2 focus:ring-(--color-ring)`
- **Hover opacity**: `hover:opacity-90` for primary actions

---

## 17. File Structure Summary

```
frontend/src/
├── components/
│   ├── agents/           # Agent/Team related components
│   ├── chat/             # Chat windows and message bubbles
│   ├── common/           # Reusable components (FolderPicker, ConfirmDialog)
│   ├── config/           # Configuration modules (Models, Skills, MCPs, Prompts)
│   ├── layout/           # Layout components (TopNav, AppIcon, UserMenu)
│   ├── onboarding/       # Onboarding flow
│   ├── settings/         # Settings popover
│   └── workspace/        # Workspace panels (FilePanel, FilePreview, Splitter)
├── lib/
│   ├── api.ts            # API client and WebSocket creators
│   └── utils.ts          # Utility functions (cn, getMimeType)
├── store/
│   └── index.ts          # Zustand store with all state and actions
├── types/
│   └── index.ts          # TypeScript type definitions
├── App.tsx               # Root component with ErrorBoundary
└── index.css             # Global styles and CSS variables

---

## v2 — Unified ID & Entity Lifecycle（2026-06）

> 配套设计文档：[`issue/unified-id-design.md`](../issue/unified-id-design.md)

### 类型层（`frontend/src/types/index.ts`）

```typescript
export interface Tool {
  id: string;                // 唯一 template_id（UUID）
  name: string;              // builtin=name, mcp=rawName
  source: "built_in" | "hook" | "mcp" | "team";
  description: string;
  inputSchema: { ... };
  mcpServerId?: string;
  mcpServerName?: string;    // legacy: UI 分组用，不参与路由
}

export interface Skill {
  id: string;
  name: string;
  ...
}

export interface MCPServer {
  id: string;
  name: string;
  ...
  tools: Tool[];
}

export interface Agent {
  id: string;                // 新增：后端生成的 UUID
  name: string;              // 展示名，可重名
  ...
  toolNames: string[];       // 存的是 Tool.id（UUID）列表
  skillNames: string[];      // 存的是 Skill.id（UUID）列表
  ...
}
```

### API client（`frontend/src/lib/api.ts`）

所有方法参数从 `name: string` 改为 `id: string`。`/api/agents/{id}`、`/api/teams/{id}`、`/api/mcps/{id}` 是新 URL 形式。后端 `_resolve_agent/team/mcp` 兼容 name（fallback），过渡期不会破坏旧调用。

`createTeamChatWs(teamId)`：team chat WebSocket 路径也用 id。

### Store（`frontend/src/store/index.ts`）

- 增加了 `BUILTIN_TOOL_IDS` 常量（与后端 `BUILTIN_TOOL_IDS` 同步）
- `defaultTools` 改为带 `id`、`source: "built_in"` 字段
- 所有 API 调用（`updateAgent`, `removeAgent`, `startAgent`, `stopAgent`, `switchSession`, `createNewSession`, `loadAgentSessions`, `loadAgentMessages`）内部按 `name` 查 `agent.id` 后再发起请求

### AgentConfigDialog（`frontend/src/components/agents/AgentConfigDialog.tsx`）

- 工具勾选框 `key={t.id}`（之前是 `t.name`），`checked` 和 `onChange` 用 `t.id`
- 提交时 PUT `/api/agents/{id}`（之前是 `{name}`）

### 其它模块

- `SkillsModule.tsx`、`MCPsModule.tsx`、`ModelsModule.tsx`、`PromptsModule.tsx` 中列表项的 React key 用对应实体的 `id`（之前是 `name`）
- `AgentTab.tsx`、`AgentTabs.tsx` 中列表项的 key 用 `agent.id`
- `ChatWindow.tsx`、`TeamChatWindow.tsx` 打开 WebSocket 时用 `agent.id` / `team.id`

### builtin tool UUID 同步

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
};
```

---

## 13. Template Import/Export

### 13.1 Overview

Template import/export allows users to save agent/team configurations as portable JSON files and restore them as form pre-fills. Templates use **human-readable names** (no UUIDs), making them portable across instances.

### 13.2 Template JSON Format

**Agent template:**
```json
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

**Team template:**
```json
{
  "type": "team",
  "name": "CodeTeam",
  "teamDescription": "A software engineering team...",
  "members": [ /* AgentTemplate[] */ ],
  "contacts": { "Architect": { "Developer": "role desc" } }
}
```

- `model` and `workingDir` fields are intentionally excluded (not portable)
- `hookConfig` and `toolPolicy` model references (e.g., `submodelId`, `subAgentModel`) use model **names**
- Type detection: explicit `type` field or `members` presence → team

### 13.3 Export

- **Trigger**: Download button (右上角) in agent/team edit dialog header
- **Logic**: `agentToTemplate()` in `lib/utils.ts` maps UUIDs → names using current store data
- **Output**: Browser download of `{name}_template.json`

### 13.4 Import (From Template)

- **Entry**: TypeSelection now has 3 options: Single Agent / Agent Team / From Template
- **Flow**: 
  1. Click "From Template" → opens `TemplatePicker` (file tree modal, reuses `getFileTree` API)
  2. User navigates directories, selects a `.json` file
  3. File content is fetched via `readFile`, parsed, and type-detected
  4. `resolveTemplate()` maps names → UUIDs using current store data
  5. Unmatched names produce warning toasts but don't block
  6. Form opens with fields pre-filled; user reviews/modifies before creating

### 13.5 Files

| File | Role |
|------|------|
| `types/index.ts` | `AgentTemplate`, `TeamTemplate`, `Template`, `TemplateResolveResult` types |
| `lib/utils.ts` | `agentToTemplate()`, `resolveTemplate()`, `detectTemplateType()`, `downloadJson()` |
| `components/TemplatePicker.tsx` | File tree modal for selecting `.json` template files |
| `components/agents/AgentConfigDialog.tsx` | Export button (edit mode header) + "From Template" option in TypeSelection + import flow |
```
