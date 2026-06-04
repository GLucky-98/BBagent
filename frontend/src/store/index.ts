import { create } from "zustand";
import type {
  Agent,
  Model,
  Message,
  Tool,
  Skill,
  MCPServer,
  Prompt,
  SettingsTab,
  SessionInfo,
  HookListResponse,
} from "../types";
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
  updateAgent: (id: string, updates: Partial<Agent>) => Promise<void>;
  updateTeam: (id: string, updates: Partial<Agent>) => Promise<void>;
  removeAgent: (id: string, deleteFiles?: boolean) => Promise<void>;
  addMessage: (agentId: string, message: Message) => void;

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

  prompts: Prompt[];
  selectedPromptId: string | null;
  setSelectedPromptId: (id: string | null) => void;
  addPrompt: (prompt: Prompt) => Promise<void>;
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

  loadAll: () => Promise<void>;
  createAgentApi: (agent: Agent) => Promise<void>;
  createTeamApi: (team: Agent) => Promise<void>;

  toasts: Toast[];
  addToast: (message: string, type?: "info" | "warning") => void;
  dismissToast: (id: string) => void;
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
    inputSchema: {
      type: "object",
      properties: {
        command: { type: "string", description: "The shell command to execute" },
        timeout: { type: "number", description: "Timeout in seconds" },
      },
      required: ["command"],
    },
  },
  {
    id: BUILTIN_TOOL_IDS.read,
    name: "read",
    source: "built_in",
    description: "Read contents of a file from the filesystem",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file to read" },
        limit: { type: "number", description: "Maximum number of lines to read" },
        offset: { type: "number", description: "Line offset to start reading from" },
      },
      required: ["path"],
    },
  },
  {
    id: BUILTIN_TOOL_IDS.write,
    name: "write",
    source: "built_in",
    description: "Write content to a file in the filesystem",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file to write" },
        content: { type: "string", description: "Content to write to the file" },
      },
      required: ["path", "content"],
    },
  },
  {
    id: BUILTIN_TOOL_IDS.edit,
    name: "edit",
    source: "built_in",
    description: "Make targeted edits to a file",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file to edit" },
        old_str: { type: "string", description: "String to search for" },
        new_str: { type: "string", description: "Replacement string" },
      },
      required: ["path", "old_str", "new_str"],
    },
  },
  {
    id: BUILTIN_TOOL_IDS.grep,
    name: "grep",
    source: "built_in",
    description: "Search for patterns in files",
    inputSchema: {
      type: "object",
      properties: {
        pattern: { type: "string", description: "Regex pattern to search for" },
        path: { type: "string", description: "Directory to search in" },
        output_mode: { type: "string", description: "Output format" },
      },
      required: ["pattern", "path"],
    },
  },
  {
    id: BUILTIN_TOOL_IDS.find,
    name: "find",
    source: "built_in",
    description: "Find files matching criteria",
    inputSchema: {
      type: "object",
      properties: {
        pattern: { type: "string", description: "Glob pattern to match" },
        path: { type: "string", description: "Directory to search in" },
      },
      required: ["pattern", "path"],
    },
  },
  {
    id: BUILTIN_TOOL_IDS.ls,
    name: "ls",
    source: "built_in",
    description: "List directory contents",
    inputSchema: {
      type: "object",
      properties: { path: { type: "string", description: "Directory to list" } },
      required: ["path"],
    },
  },
];

export const useAppStore = create<AppState>((set, get) => ({
  agents: [],
  activeAgentId: null,
  activeTeamMemberName: null,

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

  selectTeamMember: (teamId, memberName) => {
    if (memberName) {
      const team = get().agents.find((a) => a.id === teamId);
      const member = team?.members?.find((m) => m.name === memberName);
      set({ activeAgentId: teamId, activeTeamMemberName: memberName, workingDirPath: member?.workingDir || "", baseDirPath: member?.basePath || "", previewFile: null });
    } else {
      const team = get().agents.find((a) => a.id === teamId);
      set({ activeAgentId: teamId, activeTeamMemberName: null, workingDirPath: team?.workingDir || "", baseDirPath: team?.basePath || "", previewFile: null });
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
    await api.deleteAgent(id, deleteFiles);
    set((state) => ({
      agents: state.agents.filter((a) => a.id !== id),
      activeAgentId: state.activeAgentId === id ? null : state.activeAgentId,
      previewFile: state.activeAgentId === id ? null : state.previewFile,
    }));
  },
  addMessage: (agentId, message) =>
    set((state) => ({ agents: state.agents.map((a) => (a.id === agentId ? { ...a, messages: [...a.messages, message] } : a)) })),

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
    await api.createMcp(server);
    const [mcps, tools] = await Promise.all([api.listMcps(), api.listTools()]);
    set({ mcpServers: mcps || [], tools: tools || [] });
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
    if (result.imported > 0) {
      const [mcps, tools] = await Promise.all([api.listMcps(), api.listTools()]);
      set({ mcpServers: mcps || [], tools: tools || [] });
    }
  },

  skills: [],
  selectedSkillId: null,
  setSelectedSkillId: (id) => set({ selectedSkillId: id }),
  importSkills: async (path: string) => {
    const result = await api.importSkills(path);
    if (result.imported > 0) {
      const skills = await api.listSkills();
      set({ skills: skills || [] });
    }
  },

  prompts: [],
  selectedPromptId: null,
  setSelectedPromptId: (id) => set({ selectedPromptId: id }),
  addPrompt: async (prompt) => {
    await api.createPrompt(prompt);
    set((state) => ({ prompts: [...state.prompts, prompt] }));
  },
  importPrompts: async (path: string) => {
    const result = await api.importPrompts(path);
    if (result.imported > 0) {
      const prompts = await api.listPrompts();
      set({ prompts: prompts || [] });
    }
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
    set((s) => ({
      agentStates: { ...s.agentStates, [id]: state },
      agents: s.agents.map((a) => (a.id === id ? { ...a, state } : a)),
    })),

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
          a.id === id ? { ...a, messages: messages.map((m: Message, i: number) => ({ ...m, id: m.messageId || `hist-${i}` })) } : a
        ),
      }));
    } catch (e) {
      console.error("Failed to load messages:", e);
    }
  },

  startAgent: async (id: string) => {
    const result = await api.startAgent(id);
    get().setAgentState(id, result.state as "ready" | "waiting" | "running" | "error");
  },

  stopAgent: async (id: string) => {
    const result = await api.stopAgent(id);
    get().setAgentState(id, result.state as "ready" | "waiting" | "running" | "error");
  },

  loadAll: async () => {
    try {
      const [models, mcps, tools, hooks, prompts, skills, agents, teams, state] = await Promise.all([
        api.listModels(),
        api.listMcps(),
        api.listTools(),
        api.listHooks().catch(() => null),
        api.listPrompts(),
        api.listSkills(),
        api.listAgents(),
        api.listTeams(),
        api.getState().catch(() => null),
      ]);

      const allAgents = (agents || []).concat(teams || []);
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

      set({
        models: models || [],
        tools: tools || [],
        mcpServers: mcps || [],
        hooksDescriptor: hooks || null,
        prompts: prompts || [],
        skills: skills || [],
        agents: deduped,
        workingDirPath: state?.workingDirPath || "",
        baseDirPath: state?.baseDirPath || "",
        agentStates,
        agentSessions: agentSessionsMap,
      });
    } catch (e) {
      console.error("Failed to load state from backend:", e);
    }
  },

  createAgentApi: async (agent: Agent) => {
    const created = await api.createAgent(agent);
    set((state) => {
      if (state.agents.some((a) => a.id === created.id)) return state;
      return {
        agents: [...state.agents, created],
        activeAgentId: created.id,
        agentStates: { ...state.agentStates, [created.id]: created.state || "waiting" },
      };
    });
  },

  createTeamApi: async (team: Agent) => {
    const result = await api.createTeam(team);
    // Normalize the TeamConfig response into an Agent shape that the store expects
    const teamAsAgent: Agent = {
      ...team,
      id: result.id || "",
      name: result.name,
      teamDescription: result.teamDescription,
      basePath: result.baseDir || team.basePath,
      members: result.members,
      contacts: result.contacts,
    };
    set((state) => {
      if (state.agents.some((a) => a.id === teamAsAgent.id)) return state;
      return { agents: [...state.agents, teamAsAgent], activeAgentId: teamAsAgent.id };
    });
  },

  toasts: [],
  addToast: (message, type = "info") => {
    const id = crypto.randomUUID();
    set((state) => ({ toasts: [...state.toasts, { id, message, type }] }));
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
    }, 6000);
  },
  dismissToast: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },
}));

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

export const useAgentModel = () => {
  const selectedAgent = useSelectedAgent();
  const models = useAppStore((s) => s.models);
  if (!selectedAgent) return null;
  return models.find((m) => m.id === selectedAgent.modelId) ?? null;
};
