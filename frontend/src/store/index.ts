import { create } from "zustand";
import type {
  Agent,
  SingleAgent,
  Team,
  Model,
  Message,
  TeamChatMessage,
  Tool,
  Skill,
  MCPServer,
  Prompt,
  SettingsTab,
  SessionInfo,
  HookListResponse,
  ToolPolicy,
  CreateAgentPayload,
  CreateTeamPayload,
  UpdateAgentPayload,
  UpdateTeamPayload,
  TimerConfig,
} from "../types";
import { isTeam, isSingleAgent } from "../types";
import { api } from "../lib/api";

export interface Toast {
  id: string;
  message: string;
  type: "info" | "warning";
}

export interface AppState {
  agents: Agent[];
  // Per the unified-id design, the primary identifier for the active
  // agent is its id (UUID), not its display name. All lookups and
  // routing use id.
  activeAgentId: string | null;
  activeTeamMemberName: string | null;
  setActiveAgentId: (id: string | null) => void;
  selectTeamMember: (teamId: string, memberName: string | null) => void;
  updateAgent: (id: string, updates: UpdateAgentPayload) => Promise<void>;
  updateTeam: (id: string, updates: UpdateTeamPayload) => Promise<void>;
  removeAgent: (id: string, deleteFiles?: boolean) => Promise<void>;
  addMessage: (agentId: string, message: Message) => void;
  patchMessage: (agentId: string, messageId: string, patch: Partial<Message>) => void;

  // Hook descriptors from GET /api/hooks. Populated by loadAll.
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
    agentId?: string;
  };
  openConfigDialog: (
    mode: "create" | "edit",
    type: "agent" | "team" | "",
    agentId?: string
  ) => void;
  closeConfigDialog: () => void;

  workingDirPath: string;
  setWorkingDirPath: (path: string) => void;
  baseDirPath: string;
  setBaseDirPath: (path: string) => void;
  basedirExpandedPaths: Set<string>;
  toggleBasedirExpand: (path: string) => void;
  workingDirExpandedPaths: Set<string>;
  toggleWorkingDirExpand: (path: string) => void;

  previewFile: {
    path: string;
    name: string;
    content: string | null;
    mimeType: string;
    error?: string;
  } | null;
  openFilePreview: (file: {
    path: string;
    name: string;
    content: string | null;
    mimeType: string;
    error?: string;
  }) => void;
  closeFilePreview: () => void;

  models: Model[];
  selectedModelId: string | null;
  setSelectedModelId: (id: string | null) => void;
  addModel: (model: Model) => Promise<void>;
  updateModel: (id: string, updates: Partial<Model>) => Promise<void>;
  deleteModel: (id: string) => Promise<void>;

  tools: Tool[];
  fetchTools: () => Promise<void>;
  mcpServers: MCPServer[];
  selectedMcpId: string | null;
  setSelectedMcpId: (id: string | null) => void;
  addMcpServer: (server: MCPServer) => Promise<void>;
  updateMcpServer: (id: string, updates: Partial<MCPServer>) => Promise<void>;
  deleteMcpServer: (id: string) => Promise<void>;
  discoverMcpTools: (id: string) => Promise<void>;
  importMcpServers: (path: string) => Promise<void>;

  skills: Skill[];
  selectedSkillId: string | null;
  setSelectedSkillId: (id: string | null) => void;
  importSkills: (path: string) => Promise<void>;
  deleteSkill: (id: string) => Promise<void>;
  refreshSkill: (id: string) => Promise<void>;

  prompts: Prompt[];
  selectedPromptId: string | null;
  setSelectedPromptId: (id: string | null) => void;
  addPrompt: (prompt: Prompt) => Promise<void>;
  updatePrompt: (id: string, updates: Partial<Prompt>) => Promise<void>;
  deletePrompt: (id: string) => Promise<void>;
  importPrompts: (path: string) => Promise<void>;

  expandedTeams: Set<string>;
  toggleTeamExpanded: (teamId: string) => void;

  agentStates: Record<string, "ready" | "waiting" | "running" | "error">;
  setAgentState: (id: string, state: "ready" | "waiting" | "running" | "error") => void;
  agentSessions: Record<string, SessionInfo[]>;
  loadAgentSessions: (id: string) => Promise<void>;
  switchSession: (id: string, sessionId: string) => Promise<void>;
  createNewSession: (id: string) => Promise<void>;
  loadAgentMessages: (id: string) => Promise<void>;
  startAgent: (id: string) => Promise<void>;
  stopAgent: (id: string) => Promise<void>;
  startTeam: (id: string) => Promise<void>;
  stopTeam: (id: string) => Promise<void>;
  removeTeam: (id: string) => Promise<void>;

  agentTimers: Record<string, TimerConfig[]>;
  loadTimers: (id: string) => Promise<void>;
  addTimer: (id: string, data: { name: string; seconds: number; hint: string; enabled: boolean }) => Promise<void>;
  updateTimer: (id: string, name: string, data: { seconds?: number; hint?: string; enabled?: boolean }) => Promise<void>;
  startTimer: (id: string, name: string) => Promise<void>;
  stopTimer: (id: string, name: string) => Promise<void>;
  deleteTimer: (id: string, name: string) => Promise<void>;

  teamMemberIds: Set<string>;

  // Team messages (per team, keyed by team id)
  teamMessages: Record<string, TeamChatMessage[]>;
  addTeamMessage: (teamId: string, msg: TeamChatMessage) => void;
  loadTeamMessages: (teamId: string) => Promise<void>;

  loadAll: () => Promise<void>;
  createAgentApi: (payload: CreateAgentPayload) => Promise<void>;
  createTeamApi: (payload: CreateTeamPayload) => Promise<void>;

  toasts: Toast[];
  addToast: (message: string, type?: "info" | "warning") => void;
  dismissToast: (id: string) => void;

  _loaded: boolean;
}

// Builtin tool UUIDs must match backend's BUILTIN_TOOL_IDS
// (BBagent/built_in_tool/__init__.py). Used as the React key / id when the
// API listTools() response is not yet available.
const BUILTIN_TOOL_IDS: Record<string, string> = {
  bash: "5a40e5e1-6931-4126-b142-581379f4f2eb",
  read: "4c48a29c-a52a-4ec7-b7d7-d265316091c7",
  write: "20c41591-9b4e-4ff0-9182-f11db46fef41",
  edit: "2d35e797-d8f7-41cf-aa12-e439ec74230b",
  grep: "4dc7319f-7ff7-484b-aa19-c39fa5efa772",
  find: "023a166d-246b-4aeb-be56-3119210b9bba",
  ls: "20ae9084-3a2c-413b-bdbb-86f04fb9fdd3",
};

const defaultTools: Tool[] = [
  {
    id: BUILTIN_TOOL_IDS.bash,
    name: "bash",
    source: "built_in",
    description: "Execute shell commands in a terminal environment",
  },
  {
    id: BUILTIN_TOOL_IDS.read,
    name: "read",
    source: "built_in",
    description: "Read contents of a file from the filesystem",
  },
  {
    id: BUILTIN_TOOL_IDS.write,
    name: "write",
    source: "built_in",
    description: "Write content to a file in the filesystem",
  },
  {
    id: BUILTIN_TOOL_IDS.edit,
    name: "edit",
    source: "built_in",
    description: "Make targeted edits to a file",
  },
  {
    id: BUILTIN_TOOL_IDS.grep,
    name: "grep",
    source: "built_in",
    description: "Search for patterns in files",
  },
  {
    id: BUILTIN_TOOL_IDS.find,
    name: "find",
    source: "built_in",
    description: "Find files matching criteria",
  },
  {
    id: BUILTIN_TOOL_IDS.ls,
    name: "ls",
    source: "built_in",
    description: "List directory contents",
  },
];

export const useAppStore = create<AppState>((set, get) => ({
  agents: [],
  activeAgentId: null,
  activeTeamMemberName: null,
  teamMemberIds: new Set<string>(),

  // Team messages
  teamMessages: {},
  addTeamMessage: (teamId, msg) =>
    set((state) => ({
      teamMessages: {
        ...state.teamMessages,
        [teamId]: [...(state.teamMessages[teamId] || []), msg],
      },
    })),
  loadTeamMessages: async (teamId) => {
    try {
      const messages = await api.getTeamMessages(teamId);
      set((state) => ({
        teamMessages: {
          ...state.teamMessages,
          [teamId]: (messages || []).map((m: Record<string, unknown>) => ({
            fromAgent: m.from_agent as string,
            toAgent: m.to_agent as string,
            content: typeof m.content === "string" ? m.content : JSON.stringify(m.content),
            type: m.type as "direct" | "broadcast" | "user",
            timestamp: m.timestamp as number,
          })),
        },
      }));
    } catch (e) {
      console.error("Failed to load team messages:", e);
    }
  },

  setActiveAgentId: (id) => {
    const agent = id ? get().agents.find((a) => a.id === id) : null;
    set({
      activeAgentId: id,
      activeTeamMemberName: null,
      workingDirPath: agent?.workingDir || "",
      baseDirPath: agent?.baseDir || "",
      previewFile: null,
    });
  },

  selectTeamMember: (teamId, memberName) => {
    const agent = get().agents.find((a) => a.id === teamId);
    if (memberName && agent && isTeam(agent)) {
      const member = agent.members.find((m) => m.name === memberName);
      // Switch activeAgentId to the mate's real UUID so ChatWindow treats it like a single agent
      set({
        activeAgentId: member?.id ?? teamId,
        activeTeamMemberName: memberName,
        workingDirPath: member?.workingDir || "",
        baseDirPath: member?.baseDir || "",
        previewFile: null,
      });
    } else {
      set({
        activeAgentId: teamId,
        activeTeamMemberName: null,
        workingDirPath: agent?.workingDir || "",
        baseDirPath: agent?.baseDir || "",
        previewFile: null,
      });
    }
  },

  updateAgent: async (id, updates) => {
    const result = await api.updateAgent(id, updates);
    set((state) => ({
      agents: state.agents.map((a) => (a.id === id ? { ...a, ...result, messages: a.messages } : a)),
      workingDirPath: state.activeAgentId === id && result.workingDir ? result.workingDir : state.workingDirPath,
    }));
  },
  updateTeam: async (id, updates) => {
    const result = await api.updateTeam(id, updates);
    set((state) => ({
      agents: state.agents.map((a) => (a.id === id ? { ...a, ...result, messages: a.messages } : a)),
      workingDirPath: state.activeAgentId === id && result.workingDir ? result.workingDir : state.workingDirPath,
    }));
  },
  removeAgent: async (id, deleteFiles) => {
    const agent = get().agents.find((a) => a.id === id);
    const name = agent?.name || id;
    try {
      await api.deleteAgent(id, deleteFiles);
      set((state) => ({
        agents: state.agents.filter((a) => a.id !== id),
        activeAgentId: state.activeAgentId === id ? null : state.activeAgentId,
        previewFile: state.activeAgentId === id ? null : state.previewFile,
      }));
      get().addToast(`Agent '${name}' deleted`, "info");
    } catch (e: any) {
      get().addToast(`Failed to delete agent '${name}': ${e.message || e}`, "warning");
    }
  },
  addMessage: (agentId, message) =>
    set((state) => ({ agents: state.agents.map((a) => (a.id === agentId ? { ...a, messages: [...a.messages, message] } : a)) })),
  patchMessage: (agentId, messageId, patch) =>
    set((state) => ({
      agents: state.agents.map((a) =>
        a.id === agentId
          ? { ...a, messages: a.messages.map((m) => (m.id === messageId ? { ...m, ...patch } : m)) }
          : a
      ),
    })),

  isSettingsOpen: false,
  settingsActiveTab: "models",
  openSettings: (tab = "models") => set({ isSettingsOpen: true, settingsActiveTab: tab }),
  closeSettings: () => set({ isSettingsOpen: false }),

  configDialog: { open: false, mode: "create", type: "" },
  openConfigDialog: (mode, type, agentId) => set({ configDialog: { open: true, mode, type, agentId } }),
  closeConfigDialog: () => set({ configDialog: { open: false, mode: "create", type: "", agentId: undefined } }),

  workingDirPath: "",
  setWorkingDirPath: (path) => set({ workingDirPath: path }),

  baseDirPath: "",
  setBaseDirPath: (path) => set({ baseDirPath: path }),

  basedirExpandedPaths: new Set<string>(),
  toggleBasedirExpand: (path) =>
    set((state) => {
      const newSet = new Set(state.basedirExpandedPaths);
      newSet.has(path) ? newSet.delete(path) : newSet.add(path);
      return { basedirExpandedPaths: newSet };
    }),

  workingDirExpandedPaths: new Set<string>(),
  toggleWorkingDirExpand: (path) =>
    set((state) => {
      const newSet = new Set(state.workingDirExpandedPaths);
      newSet.has(path) ? newSet.delete(path) : newSet.add(path);
      return { workingDirExpandedPaths: newSet };
    }),

  previewFile: null,
  openFilePreview: (file) => set({ previewFile: file }),
  closeFilePreview: () => set({ previewFile: null }),

  models: [],
  selectedModelId: null,
  setSelectedModelId: (id) => set({ selectedModelId: id }),
  addModel: async (model) => {
    await api.createModel(model);
    set((state) => ({ models: [...state.models, model] }));
  },
  updateModel: async (id, updates) => {
    const result = await api.updateModel(id, updates);
    set((state) => ({ models: state.models.map((m) => (m.id === id ? { ...m, ...updates } : m)) }));
    if (result.affectedAgents && result.affectedAgents.length > 0) {
      const agents = get().agents;
      const names = result.affectedAgents
        .map((aid: string) => agents.find((a) => a.id === aid)?.name)
        .filter(Boolean)
        .join(", ");
      get().addToast(`Model config updated. Auto-applied to agents: ${names}`, "info");
    }
  },
  deleteModel: async (id) => {
    const result = await api.deleteModel(id);
    set((state) => ({
      models: state.models.filter((m) => m.id !== id),
      selectedModelId: state.selectedModelId === id ? null : state.selectedModelId,
    }));
    if (result.affectedAgents && result.affectedAgents.length > 0) {
      const agents = get().agents;
      const names = result.affectedAgents
        .map((aid: string) => agents.find((a) => a.id === aid)?.name)
        .filter(Boolean)
        .join(", ");
      get().addToast(`Model deleted. Please reassign a model for: ${names}`, "warning");
    }
  },

  tools: defaultTools,

  fetchTools: async () => {
    try {
      const tools = await api.listTools();
      set({ tools: tools || [] });
    } catch (e) {
      console.warn("Failed to fetch tools:", e);
    }
  },

  hooksDescriptor: null,
  fetchHooksDescriptor: async () => {
    try {
      const hooks = await api.listHooks();
      set({ hooksDescriptor: hooks });
    } catch (e) {
      console.warn("Failed to fetch hooks descriptor:", e);
    }
  },

  mcpServers: [],
  selectedMcpId: null,
  setSelectedMcpId: (id) => set({ selectedMcpId: id }),
  addMcpServer: async (server) => {
    try {
      await api.createMcp(server);
      const [mcps, tools] = await Promise.all([api.listMcps(), api.listTools()]);
      set({ mcpServers: mcps || [], tools: tools || [] });
      get().addToast(`MCP server '${server.name}' created`, "info");
    } catch (e: any) {
      get().addToast(`Failed to create MCP server '${server.name}': ${e.message || e}`, "warning");
    }
  },
  updateMcpServer: async (id, updates) => {
    const result = await api.updateMcp(id, updates);
    const [mcps, tools] = await Promise.all([api.listMcps(), api.listTools()]);
    set({ mcpServers: mcps || [], tools: tools || [] });
    if (result.hint) {
      get().addToast(result.hint, "warning");
    }
  },
  deleteMcpServer: async (id) => {
    const result = await api.deleteMcp(id);
    const [mcps, tools] = await Promise.all([api.listMcps(), api.listTools()]);
    set({ mcpServers: mcps || [], tools: tools || [] });
    if (result.hint) {
      get().addToast(result.hint, "warning");
    }
  },
  discoverMcpTools: async (id) => {
    const result = await api.discoverMcp(id);
    const [mcps, tools] = await Promise.all([api.listMcps(), api.listTools()]);
    set({ mcpServers: mcps || [], tools: tools || [] });
    const count = result.tools?.length ?? 0;
    get().addToast(`Discovered ${count} tool(s)`, "info");
  },
  importMcpServers: async (path: string) => {
    const result = await api.importMcps(path);
    const [mcps, tools] = await Promise.all([api.listMcps(), api.listTools()]);
    set({ mcpServers: mcps || [], tools: tools || [] });
    const parts: string[] = [];
    if (result.imported > 0) parts.push(`${result.imported} imported`);
    if (result.skipped > 0) parts.push(`${result.skipped} skipped (duplicate)`);
    if (result.errors > 0) parts.push(`${result.errors} failed`);
    get().addToast(`MCP import: ${parts.join(", ") || "no changes"}`, result.errors > 0 ? "warning" : "info");
  },

  skills: [],
  selectedSkillId: null,
  setSelectedSkillId: (id) => set({ selectedSkillId: id }),
  importSkills: async (path: string) => {
    const result = await api.importSkills(path);
    const skills = await api.listSkills();
    set({ skills: skills || [] });
    const parts: string[] = [];
    if (result.imported > 0) parts.push(`${result.imported} imported`);
    if (result.skipped > 0) parts.push(`${result.skipped} skipped (duplicate)`);
    get().addToast(`Skill import: ${parts.join(", ") || "no changes"}`, "info");
  },
  deleteSkill: async (id: string) => {
    await api.deleteSkill(id);
    set((state) => ({
      skills: state.skills.filter((s) => s.id !== id),
      selectedSkillId: state.selectedSkillId === id ? null : state.selectedSkillId,
    }));
  },
  refreshSkill: async (id: string) => {
    const updated = await api.refreshSkill(id);
    set((state) => ({
      skills: state.skills.map((s) => (s.id === id ? updated : s)),
    }));
  },

  prompts: [],
  selectedPromptId: null,
  setSelectedPromptId: (id) => set({ selectedPromptId: id }),
  addPrompt: async (prompt) => {
    await api.createPrompt(prompt);
    set((state) => ({ prompts: [...state.prompts, prompt] }));
  },
  updatePrompt: async (id, updates) => {
    const result = await api.updatePrompt(id, updates);
    set((state) => ({
      prompts: state.prompts.map((p) => (p.id === id ? { ...p, ...result } : p)),
    }));
  },
  deletePrompt: async (id) => {
    await api.deletePrompt(id);
    set((state) => ({
      prompts: state.prompts.filter((p) => p.id !== id),
      selectedPromptId: state.selectedPromptId === id ? null : state.selectedPromptId,
    }));
  },
  importPrompts: async (path: string) => {
    const result = await api.importPrompts(path);
    if (result.imported > 0 || result.skipped > 0 || result.errors > 0) {
      const prompts = await api.listPrompts();
      set({ prompts: prompts || [] });
    }
    const parts: string[] = [];
    if (result.imported > 0) parts.push(`${result.imported} imported`);
    if (result.skipped > 0) parts.push(`${result.skipped} skipped (duplicate)`);
    if (result.errors > 0) parts.push(`${result.errors} failed`);
    get().addToast(`Prompt import: ${parts.join(", ") || "no changes"}`, result.errors > 0 ? "warning" : "info");
  },

  expandedTeams: new Set<string>(),
  toggleTeamExpanded: (teamId: string) =>
    set((state) => {
      const newSet = new Set(state.expandedTeams);
      newSet.has(teamId) ? newSet.delete(teamId) : newSet.add(teamId);
      return { expandedTeams: newSet };
    }),

  agentStates: {},

  setAgentState: (id, state) =>
    set((s) => {
      const newAgentStates = { ...s.agentStates, [id]: state };
      // If this agent is a team member, recompute its team's state
      if (s.teamMemberIds.has(id)) {
        for (const agent of s.agents) {
          if (!isTeam(agent)) continue;
          const team = agent as Team;
          if (!team.members.some((m) => m.id === id)) continue;
          const memberStates = team.members
            .map((m) => newAgentStates[m.id])
            .filter(Boolean) as Array<"ready" | "waiting" | "running" | "error">;
          if (memberStates.length === 0) continue;
          const hasError = memberStates.some((st) => st === "error");
          const hasRunning = memberStates.some((st) => st === "running");
          const hasWaiting = memberStates.some((st) => st === "waiting");
          if (hasError) newAgentStates[agent.id] = "error";
          else if (hasRunning) newAgentStates[agent.id] = "running";
          else if (hasWaiting) newAgentStates[agent.id] = "waiting";
          else newAgentStates[agent.id] = "ready";
          break;
        }
      }
      return {
        agentStates: newAgentStates,
        agents: s.agents.map((a) => (a.id === id ? { ...a, state } : a)),
      };
    }),

  agentSessions: {},

  loadAgentSessions: async (id: string) => {
    try {
      const sessions = await api.listSessions(id);
      set((s) => ({ agentSessions: { ...s.agentSessions, [id]: sessions } }));
    } catch (e) {
      console.error("Failed to load sessions:", e);
    }
  },

  switchSession: async (id: string, sessionId: string) => {
    await api.switchSession(id, sessionId);
    const sessions = get().agentSessions[id] || [];
    set((s) => ({
      agentSessions: {
        ...s.agentSessions,
        [id]: sessions.map((sess) => ({
          ...sess,
          isActive: sess.id === sessionId,
        })),
      },
    }));
    await get().loadAgentMessages(id);
  },

  createNewSession: async (id: string) => {
    const result = await api.newSession(id);
    await get().loadAgentSessions(id);
    set((s) => ({
      agents: s.agents.map((a) =>
        a.id === id ? { ...a, messages: [], currentSessionId: result.session_id } : a
      ),
    }));
  },

  loadAgentMessages: async (id: string) => {
    try {
      const messages = await api.getAgentMessages(id);
      set((s) => ({
        agents: s.agents.map((a) =>
          a.id === id ? { ...a, messages: messages.map((m: Record<string, unknown>, i: number) => ({
            id: `hist-${i}`,
            role: m.role as string,
            content: m.content as string,
            timestamp: m.timestamp as number,
            sourceAgent: (m.source_agent || m.sourceAgent) as string | undefined,
            chunkType: m.chunkType as string | undefined,
            toolName: m.toolName as string | undefined,
            toolInput: m.toolInput as Record<string, unknown> | undefined,
          })) } : a
        ),
      }));
    } catch (e) {
      console.error("Failed to load messages:", e);
    }
  },

  startAgent: async (id: string) => {
    const agent = get().agents.find((a) => a.id === id);
    const name = agent?.name || id;
    try {
      const result = await api.startAgent(id);
      get().setAgentState(id, result.state as "ready" | "waiting" | "running" | "error");
      get().addToast(`Agent '${name}' started`, "info");
    } catch (e: any) {
      get().addToast(`Failed to start agent '${name}': ${e.message || e}`, "warning");
    }
  },

  stopAgent: async (id: string) => {
    const agent = get().agents.find((a) => a.id === id);
    const name = agent?.name || id;
    try {
      const result = await api.stopAgent(id);
      get().setAgentState(id, result.state as "ready" | "waiting" | "running" | "error");
      get().addToast(`Agent '${name}' stopped`, "info");
    } catch (e: any) {
      get().addToast(`Failed to stop agent '${name}': ${e.message || e}`, "warning");
    }
  },

  startTeam: async (id: string) => {
    const agent = get().agents.find((a) => a.id === id);
    const name = agent?.name || id;
    try {
      const result = await api.startTeam(id);
      const state = result.state as "ready" | "waiting" | "running" | "error";
      get().setAgentState(id, state);
      // 同步更新所有 member agent 的状态（team WS 不再订阅 agent dispatcher）
      if (isTeam(agent)) {
        for (const m of agent.members) {
          get().setAgentState(m.id, state);
        }
      }
      get().addToast(`Team '${name}' started`, "info");
    } catch (e: any) {
      get().addToast(`Failed to start team '${name}': ${e.message || e}`, "warning");
    }
  },

  stopTeam: async (id: string) => {
    const agent = get().agents.find((a) => a.id === id);
    const name = agent?.name || id;
    try {
      const result = await api.stopTeam(id);
      const state = result.state as "ready" | "waiting" | "running" | "error";
      get().setAgentState(id, state);
      // 同步更新所有 member agent 的状态（team WS 不再订阅 agent dispatcher）
      if (isTeam(agent)) {
        for (const m of agent.members) {
          get().setAgentState(m.id, state);
        }
      }
      get().addToast(`Team '${name}' stopped`, "info");
    } catch (e: any) {
      get().addToast(`Failed to stop team '${name}': ${e.message || e}`, "warning");
    }
  },

  removeTeam: async (id: string) => {
    const agent = get().agents.find((a) => a.id === id);
    const name = agent?.name || id;
    try {
      await api.deleteTeam(id);
      set((state) => ({
        agents: state.agents.filter((a) => a.id !== id),
        activeAgentId: state.activeAgentId === id ? null : state.activeAgentId,
        previewFile: state.activeAgentId === id ? null : state.previewFile,
      }));
      get().addToast(`Team '${name}' deleted`, "info");
    } catch (e: any) {
      get().addToast(`Failed to delete team '${name}': ${e.message || e}`, "warning");
    }
  },

  agentTimers: {},

  loadTimers: async (id: string) => {
    try {
      const timers = await api.listTimers(id);
      set((s) => ({ agentTimers: { ...s.agentTimers, [id]: timers || [] } }));
    } catch (e) {
      console.error("Failed to load timers:", e);
    }
  },

  addTimer: async (id, data) => {
    try {
      const timers = await api.addTimer(id, data);
      set((s) => ({ agentTimers: { ...s.agentTimers, [id]: timers || [] } }));
    } catch (e: any) {
      get().addToast(`Failed to add timer: ${e.message || e}`, "warning");
    }
  },

  updateTimer: async (id, name, data) => {
    try {
      const timers = await api.updateTimer(id, name, data);
      set((s) => ({ agentTimers: { ...s.agentTimers, [id]: timers || [] } }));
    } catch (e: any) {
      get().addToast(`Failed to update timer: ${e.message || e}`, "warning");
    }
  },

  startTimer: async (id, name) => {
    try {
      await api.startTimer(id, name);
      await get().loadTimers(id);
    } catch (e: any) {
      get().addToast(`Failed to start timer: ${e.message || e}`, "warning");
    }
  },

  stopTimer: async (id, name) => {
    try {
      await api.stopTimer(id, name);
      await get().loadTimers(id);
    } catch (e: any) {
      get().addToast(`Failed to stop timer: ${e.message || e}`, "warning");
    }
  },

  deleteTimer: async (id, name) => {
    try {
      const timers = await api.deleteTimer(id, name);
      set((s) => ({ agentTimers: { ...s.agentTimers, [id]: timers || [] } }));
    } catch (e: any) {
      get().addToast(`Failed to delete timer: ${e.message || e}`, "warning");
    }
  },

  loadAll: async () => {
    // Guard against React StrictMode double-invoking useEffect
    if (get()._loaded) return;
    get()._loaded = true;

    // Track which requests failed for partial-error reporting
    const failedKeys: string[] = [];
    const safe = <T>(key: string, p: Promise<T>): Promise<T | null> =>
      p.catch(() => { failedKeys.push(key); return null; });

    try {
      const [models, mcps, tools, hooks, prompts, skills, agents, teams, state] = await Promise.all([
        safe("models", api.listModels()),
        safe("mcps", api.listMcps()),
        safe("tools", api.listTools()),
        safe("hooks", api.listHooks()),
        safe("prompts", api.listPrompts()),
        safe("skills", api.listSkills()),
        safe("agents", api.listAgents()),
        safe("teams", api.listTeams()),
        safe("state", api.getState()),
      ]);

      // Normalize API responses into SingleAgent | Team
      const normalizedAgents: Agent[] = (agents || []).map((a: Record<string, unknown>): SingleAgent => ({
        id: a.id as string,
        name: a.name as string,
        type: "single",
        baseDir: (a.baseDir as string) || "",
        workingDir: (a.workingDir as string) || "",
        modelId: (a.modelId as string) || "",
        systemPrompt: (a.systemPrompt as string) || "",
        toolIds: (a.toolIds as string[]) || [],
        skillIds: (a.skillIds as string[]) || [],
        hookNames: (a.hookNames as string[]) || [],
        hookConfig: (a.hookConfig as Record<string, unknown>) || {},
        toolPolicy: (a.toolPolicy as ToolPolicy) || {},
        messages: [],
        state: (a.state as "ready" | "waiting" | "running" | "error") || "ready",
        sessions: (a.sessions as SessionInfo[]) || [],
        currentSessionId: (a.currentSessionId as string) || "",
      }));

      const normalizedTeams: Agent[] = (teams || []).map((t: Record<string, unknown>): Team => ({
        id: t.id as string,
        name: t.name as string,
        type: "team",
        baseDir: (t.baseDir as string) || "",
        workingDir: (t.workingDir as string) || "",
        teamDescription: (t.teamDescription as string) || "",
        members: [],
        contacts: (t.contacts as Record<string, Record<string, string>>) || {},
        messages: [],
        state: (t.state as "ready" | "waiting" | "running" | "error") || "ready",
        sessions: [],
        currentSessionId: "",
      }));

      // Populate team members from normalized agents using memberIds from raw team data
      const agentById = new Map<string, SingleAgent>();
      for (const a of normalizedAgents as SingleAgent[]) {
        agentById.set(a.id, a);
      }
      for (const t of (teams || []) as Record<string, unknown>[]) {
        const teamId = t.id as string;
        const team = normalizedTeams.find((nt) => nt.id === teamId) as Team | undefined;
        if (!team) continue;
        const mids = (t.memberIds as string[]) || [];
        const members: SingleAgent[] = [];
        for (const mid of mids) {
          const agent = agentById.get(mid);
          if (agent) members.push(agent);
        }
        team.members = members;
      }

      // Collect all team member IDs (for tab filtering — they don't appear as standalone tabs)
      const teamMemberIds = new Set<string>();
      for (const t of (teams || []) as Record<string, unknown>[]) {
        const mids = (t.memberIds as string[]) || [];
        for (const mid of mids) teamMemberIds.add(mid);
      }

      // Keep teammates in agents so they have their own messages/state/WS subscription.
      // AgentTabs filters them out via teamMemberIds.
      const allAgents = [...normalizedAgents, ...normalizedTeams];
      const seen = new Set<string>();
      const deduped = allAgents.filter((a: Agent) => {
        if (seen.has(a.id)) return false;
        seen.add(a.id);
        return true;
      });
      const agentStates: Record<string, "ready" | "waiting" | "running" | "error"> = {};
      const agentSessionsMap: Record<string, SessionInfo[]> = {};

      for (const agent of deduped) {
        agentStates[agent.id] = agent.state || "ready";
        agentSessionsMap[agent.id] = agent.sessions || [];
      }

      // Compute team states from their members
      for (const agent of deduped) {
        if (!isTeam(agent)) continue;
        const team = agent as Team;
        const memberStates = team.members
          .map((m) => agentStates[m.id])
          .filter(Boolean) as Array<"ready" | "waiting" | "running" | "error">;
        if (memberStates.length === 0) continue;
        const hasError = memberStates.some((s) => s === "error");
        const hasRunning = memberStates.some((s) => s === "running");
        const hasWaiting = memberStates.some((s) => s === "waiting");
        if (hasError) {
          agentStates[agent.id] = "error";
        } else if (hasRunning) {
          agentStates[agent.id] = "running";
        } else if (hasWaiting) {
          agentStates[agent.id] = "waiting";
        } else {
          agentStates[agent.id] = "ready";
        }
      }

      set({
        models: models || [],
        tools: tools || [],
        mcpServers: mcps || [],
        hooksDescriptor: hooks || null,
        prompts: prompts || [],
        skills: skills || [],
        agents: deduped,
        teamMemberIds,
        workingDirPath: state?.workingDirPath || "",
        baseDirPath: state?.baseDirPath || "",
        agentStates,
        agentSessions: agentSessionsMap,
      });

      // Startup summary toast
      const parts: string[] = [];
      const teamCount = normalizedTeams.length;
      const agentCount = normalizedAgents.filter((a) => !teamMemberIds.has(a.id)).length;
      if ((models?.length ?? 0) > 0) parts.push(`${models!.length} model(s)`);
      if (agentCount > 0) parts.push(`${agentCount} agent(s)`);
      if (teamCount > 0) parts.push(`${teamCount} team(s)`);
      if ((mcps?.length ?? 0) > 0) parts.push(`${mcps!.length} MCP server(s)`);
      if ((skills?.length ?? 0) > 0) parts.push(`${skills!.length} skill(s)`);
      if ((prompts?.length ?? 0) > 0) parts.push(`${prompts!.length} prompt(s)`);
      get().addToast(`Loaded: ${parts.join(", ") || "no resources"}`, "info");

      if (failedKeys.length > 0) {
        get().addToast(`Some resources failed to load: ${failedKeys.join(", ")}`, "warning");
      }
    } catch (e) {
      console.error("Failed to load state from backend:", e);
      get().addToast("Failed to connect to backend. Please check if the server is running.", "warning");
    }
  },

  createAgentApi: async (payload: CreateAgentPayload) => {
    const created = await api.createAgent(payload);
    const agent: SingleAgent = {
      id: created.id || "",
      name: created.name,
      type: "single",
      baseDir: created.baseDir || "",
      workingDir: created.workingDir || "",
      modelId: created.modelId || "",
      systemPrompt: created.systemPrompt || "",
      toolIds: created.toolIds || [],
      skillIds: created.skillIds || [],
      hookNames: created.hookNames || [],
      hookConfig: created.hookConfig || {},
      toolPolicy: created.toolPolicy || {},
      messages: [],
      state: created.state || "ready",
      sessions: [],
      currentSessionId: created.currentSessionId || "",
    };
    set((state) => {
      if (state.agents.some((a) => a.id === agent.id)) return state;
      return {
        agents: [...state.agents, agent],
        activeAgentId: agent.id,
        workingDirPath: agent.workingDir,
        baseDirPath: agent.baseDir,
        agentStates: { ...state.agentStates, [agent.id]: agent.state },
      };
    });
  },

  createTeamApi: async (payload: CreateTeamPayload) => {
    const result = await api.createTeam(payload);
    // Build single-agent entries for each member from the response
    const memberAgents: SingleAgent[] = (result.members || []).map((m: Record<string, unknown>) => ({
      id: m.id as string,
      name: m.name as string,
      type: "single" as const,
      baseDir: (m.baseDir as string) || "",
      workingDir: (m.workingDir as string) || (result.workingDir as string) || "",
      modelId: (m.modelId as string) || "",
      systemPrompt: (m.systemPrompt as string) || "",
      toolIds: (m.toolIds as string[]) || [],
      skillIds: (m.skillIds as string[]) || [],
      hookNames: (m.hookNames as string[]) || [],
      hookConfig: (m.hookConfig as Record<string, unknown>) || {},
      toolPolicy: (m.toolPolicy as ToolPolicy) || {},
      messages: [],
      state: (m.state as "ready" | "waiting" | "running" | "error") || "ready",
      sessions: [],
      currentSessionId: "",
    }));
    const memberIds = new Set(memberAgents.map((m) => m.id));
    const team: Team = {
      id: result.id || "",
      name: result.name,
      type: "team",
      baseDir: result.baseDir || "",
      workingDir: result.workingDir || "",
      teamDescription: result.teamDescription || "",
      members: memberAgents,
      contacts: result.contacts || {},
      messages: [],
      state: (result.state as "ready" | "waiting" | "running" | "error") || "ready",
      sessions: [],
      currentSessionId: "",
    };
    set((state) => {
      if (state.agents.some((a) => a.id === team.id)) return state;
      const newMemberIds = new Set(state.teamMemberIds);
      for (const mid of memberIds) newMemberIds.add(mid);
      return {
        agents: [...state.agents, ...memberAgents, team],
        teamMemberIds: newMemberIds,
        activeAgentId: team.id,
        workingDirPath: team.workingDir,
        baseDirPath: team.baseDir,
      };
    });
  },

  toasts: [],
  addToast: (message, type = "info") => {
    const id = crypto.randomUUID();
    set((state) => ({ toasts: [...state.toasts, { id, message, type }] }));
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
    }, 3000);
  },
  dismissToast: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },

  _loaded: false,
}));

export const useSelectedAgent = () => {
  const agents = useAppStore((s) => s.agents);
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const activeTeamMemberName = useAppStore((s) => s.activeTeamMemberName);
  if (!activeAgentId) return null;
  const agent = agents.find((a) => a.id === activeAgentId);
  if (!agent) return null;
  if (isTeam(agent) && activeTeamMemberName) {
    return agent.members.find((m) => m.name === activeTeamMemberName) ?? null;
  }
  return agent;
};

export const useAgentModel = () => {
  const selectedAgent = useSelectedAgent();
  const models = useAppStore((s) => s.models);
  if (!selectedAgent || !isSingleAgent(selectedAgent)) return null;
  return models.find((m) => m.id === selectedAgent.modelId) ?? null;
};
