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
  AgentPolicy,
  SessionInfo,
} from "../types";
import { api } from "../lib/api";

export interface AppState {
  agents: Agent[];
  activeAgentName: string | null;
  activeTeamMemberName: string | null;
  setActiveAgentName: (name: string | null) => void;
  selectTeamMember: (teamName: string, memberName: string | null) => void;
  addAgent: (agent: Agent) => void;
  addTeam: (team: Agent) => void;
  updateAgent: (name: string, updates: Partial<Agent>) => void;
  updateTeam: (name: string, updates: Partial<Agent>) => void;
  removeAgent: (name: string, deleteFiles?: boolean) => Promise<void>;
  addMessage: (agentName: string, message: Message) => void;

  isSettingsOpen: boolean;
  settingsActiveTab: SettingsTab;
  openSettings: (tab?: SettingsTab) => void;
  closeSettings: () => void;

  configDialog: {
    open: boolean;
    mode: "create" | "edit";
    type: "agent" | "team" | "";
    agentName?: string;
  };
  openConfigDialog: (
    mode: "create" | "edit",
    type: "agent" | "team" | "",
    agentName?: string
  ) => void;
  closeConfigDialog: () => void;

  workingDirPath: string;
  setWorkingDirPath: (path: string) => void;
  baseDirPath: string;
  setBaseDirPath: (path: string) => void;
  basedirExpandedPaths: Set<string>;
  toggleBasedirExpand: (path: string) => void;

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

  tools: Tool[];
  mcpServers: MCPServer[];
  selectedMcpId: string | null;
  setSelectedMcpId: (id: string | null) => void;
  addMcpServer: (server: MCPServer) => Promise<void>;
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
  toggleTeamExpanded: (teamName: string) => void;

  agentStates: Record<string, "ready" | "waiting" | "running" | "error">;
  isAgentStreaming: Record<string, boolean>;
  setAgentState: (name: string, state: "ready" | "waiting" | "running" | "error") => void;
  setIsStreaming: (name: string, streaming: boolean) => void;
  agentSessions: Record<string, SessionInfo[]>;
  loadAgentSessions: (name: string) => Promise<void>;
  switchSession: (name: string, sessionId: string) => Promise<void>;
  createNewSession: (name: string) => Promise<void>;
  loadAgentMessages: (name: string) => Promise<void>;
  startAgent: (name: string) => Promise<void>;
  stopAgent: (name: string) => Promise<void>;

  loadAll: () => Promise<void>;
  createAgentApi: (agent: Agent) => Promise<void>;
  createTeamApi: (team: Agent) => Promise<void>;
}

const defaultTools: Tool[] = [
  {
    id: "tool-1",
    name: "bash",
    description: "Execute shell commands in a terminal environment",
    inputSchema: {
      type: "object",
      properties: {
        command: { type: "string", description: "The shell command to execute" },
        timeout: { type: "number", description: "Timeout in seconds" },
      },
      required: ["command"],
    },
    isMcp: false,
  },
  {
    id: "tool-2",
    name: "read",
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
    isMcp: false,
  },
  {
    id: "tool-3",
    name: "write",
    description: "Write content to a file in the filesystem",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file to write" },
        content: { type: "string", description: "Content to write to the file" },
      },
      required: ["path", "content"],
    },
    isMcp: false,
  },
  {
    id: "tool-4",
    name: "edit",
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
    isMcp: false,
  },
  {
    id: "tool-5",
    name: "grep",
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
    isMcp: false,
  },
  {
    id: "tool-6",
    name: "find",
    description: "Find files matching criteria",
    inputSchema: {
      type: "object",
      properties: {
        pattern: { type: "string", description: "Glob pattern to match" },
        path: { type: "string", description: "Directory to search in" },
      },
      required: ["pattern", "path"],
    },
    isMcp: false,
  },
  {
    id: "tool-7",
    name: "ls",
    description: "List directory contents",
    inputSchema: {
      type: "object",
      properties: { path: { type: "string", description: "Directory to list" } },
      required: ["path"],
    },
    isMcp: false,
  },
  {
    id: "tool-8",
    name: "ask_human",
    description: "Ask the human user a question when you need clarification, additional information, or a decision",
    inputSchema: {
      type: "object",
      properties: {
        question: { type: "string", description: "The question to ask the human user" },
      },
      required: ["question"],
    },
    isMcp: false,
  },
];

export const useAppStore = create<AppState>((set, get) => ({
  agents: [],
  activeAgentName: null,
  activeTeamMemberName: null,

  setActiveAgentName: (name) => {
    const agent = name ? get().agents.find((a) => a.name === name) : null;
    set({
      activeAgentName: name,
      activeTeamMemberName: null,
      workingDirPath: agent?.policy?.cwd || "",
      baseDirPath: agent?.basePath || "",
      previewFile: null,
    });
  },

  selectTeamMember: (teamName, memberName) => {
    if (memberName) {
      const team = get().agents.find((a) => a.name === teamName);
      const member = team?.teamMembers?.find((m) => m.name === memberName);
      set({ activeAgentName: teamName, activeTeamMemberName: memberName, workingDirPath: member?.policy?.cwd || "", baseDirPath: member?.basePath || "", previewFile: null });
    } else {
      const team = get().agents.find((a) => a.name === teamName);
      set({ activeAgentName: teamName, activeTeamMemberName: null, workingDirPath: team?.policy?.cwd || "", baseDirPath: team?.basePath || "", previewFile: null });
    }
  },

  addAgent: (agent) => set((state) => {
    if (state.agents.some((a) => a.name === agent.name)) return state;
    return { agents: [...state.agents, agent], activeAgentName: agent.name, workingDirPath: agent.policy?.cwd || "", baseDirPath: agent.basePath };
  }),
  addTeam: (team) => set((state) => {
    if (state.agents.some((a) => a.name === team.name)) return state;
    return { agents: [...state.agents, team], activeAgentName: team.name, workingDirPath: team.policy?.cwd || "", baseDirPath: team.basePath };
  }),
  updateAgent: (name, updates) => set((state) => ({ agents: state.agents.map((a) => (a.name === name ? { ...a, ...updates } : a)) })),
  updateTeam: (name, updates) => set((state) => ({ agents: state.agents.map((a) => (a.name === name ? { ...a, ...updates } : a)) })),
  removeAgent: async (name, deleteFiles) => {
    const agent = get().agents.find((a) => a.name === name);
    if (!agent) return;
    await api.deleteAgent(agent.name, deleteFiles);
    set((state) => ({
      agents: state.agents.filter((a) => a.name !== name),
      activeAgentName: state.activeAgentName === name ? null : state.activeAgentName,
      previewFile: state.activeAgentName === name ? null : state.previewFile,
    }));
  },
  addMessage: (agentName, message) =>
    set((state) => ({ agents: state.agents.map((a) => (a.name === agentName ? { ...a, messages: [...a.messages, message] } : a)) })),

  isSettingsOpen: false,
  settingsActiveTab: "models",
  openSettings: (tab = "models") => set({ isSettingsOpen: true, settingsActiveTab: tab }),
  closeSettings: () => set({ isSettingsOpen: false }),

  configDialog: { open: false, mode: "create", type: "" },
  openConfigDialog: (mode, type, agentName) => set({ configDialog: { open: true, mode, type, agentName } }),
  closeConfigDialog: () => set({ configDialog: { open: false, mode: "create", type: "", agentName: undefined } }),

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
    await api.updateModel(id, updates);
    set((state) => ({ models: state.models.map((m) => (m.id === id ? { ...m, ...updates } : m)) }));
  },

  tools: defaultTools,

  mcpServers: [],
  selectedMcpId: null,
  setSelectedMcpId: (id) => set({ selectedMcpId: id }),
  addMcpServer: async (server) => {
    await api.createMcp(server);
    set((state) => ({ mcpServers: [...state.mcpServers, server] }));
  },
  importMcpServers: async (path: string) => {
    const result = await api.importMcps(path);
    if (result.imported > 0) {
      const mcps = await api.listMcps();
      set({ mcpServers: mcps || [] });
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
  toggleTeamExpanded: (teamName) =>
    set((state) => {
      const newSet = new Set(state.expandedTeams);
      newSet.has(teamName) ? newSet.delete(teamName) : newSet.add(teamName);
      return { expandedTeams: newSet };
    }),

  agentStates: {},
  isAgentStreaming: {},

  setAgentState: (name, state) =>
    set((s) => ({
      agentStates: { ...s.agentStates, [name]: state },
      agents: s.agents.map((a) => (a.name === name ? { ...a, state } : a)),
    })),

  setIsStreaming: (name, streaming) =>
    set((s) => ({
      isAgentStreaming: { ...s.isAgentStreaming, [name]: streaming },
    })),

  agentSessions: {},

  loadAgentSessions: async (name: string) => {
    try {
      const sessions = await api.listSessions(name);
      set((s) => ({ agentSessions: { ...s.agentSessions, [name]: sessions } }));
    } catch (e) {
      console.error("Failed to load sessions:", e);
    }
  },

  switchSession: async (name: string, sessionId: string) => {
    await api.switchSession(name, sessionId);
    const sessions = get().agentSessions[name] || [];
    set((s) => ({
      agentSessions: {
        ...s.agentSessions,
        [name]: sessions.map((sess) => ({
          ...sess,
          isActive: sess.id === sessionId,
        })),
      },
    }));
    await get().loadAgentMessages(name);
  },

  createNewSession: async (name: string) => {
    const result = await api.newSession(name);
    await get().loadAgentSessions(name);
    set((s) => ({
      agents: s.agents.map((a) =>
        a.name === name ? { ...a, messages: [], currentSessionId: result.session_id } : a
      ),
    }));
  },

  loadAgentMessages: async (name: string) => {
    try {
      const messages = await api.getAgentMessages(name);
      set((s) => ({
        agents: s.agents.map((a) =>
          a.name === name ? { ...a, messages: messages.map((m: Message, i: number) => ({ ...m, id: m.messageId || `hist-${i}` })) } : a
        ),
      }));
    } catch (e) {
      console.error("Failed to load messages:", e);
    }
  },

  startAgent: async (name: string) => {
    const result = await api.startAgent(name);
    get().setAgentState(name, result.state as "ready" | "waiting" | "running" | "error");
  },

  stopAgent: async (name: string) => {
    const result = await api.stopAgent(name);
    get().setAgentState(name, result.state as "ready" | "waiting" | "running" | "error");
    get().setIsStreaming(name, false);
  },

  loadAll: async () => {
    try {
      const [models, mcps, prompts, skills, agents, teams, state] = await Promise.all([
        api.listModels(),
        api.listMcps(),
        api.listPrompts(),
        api.listSkills(),
        api.listAgents(),
        api.listTeams(),
        api.getState().catch(() => null),
      ]);

      const allAgents = (agents || []).concat(teams || []);
      const seen = new Set<string>();
      const deduped = allAgents.filter((a: Agent) => {
        if (seen.has(a.name)) return false;
        seen.add(a.name);
        return true;
      });
      const agentStates: Record<string, "ready" | "waiting" | "running" | "error"> = {};
      const agentSessionsMap: Record<string, SessionInfo[]> = {};

      for (const agent of deduped) {
        agentStates[agent.name] = agent.state || "ready";
        agentSessionsMap[agent.name] = agent.sessions || [];
      }

      set({
        models: models || [],
        mcpServers: mcps || [],
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
      if (state.agents.some((a) => a.name === created.name)) return state;
      return {
        agents: [...state.agents, created],
        activeAgentName: created.name,
        agentStates: { ...state.agentStates, [created.name]: created.state || "waiting" },
      };
    });
  },

  createTeamApi: async (team: Agent) => {
    const created = await api.createTeam(team);
    set((state) => {
      if (state.agents.some((a) => a.name === created.name)) return state;
      return { agents: [...state.agents, created], activeAgentName: created.id };
    });
  },
}));

export const useSelectedAgent = () => {
  const agents = useAppStore((s) => s.agents);
  const activeAgentName = useAppStore((s) => s.activeAgentName);
  const activeTeamMemberName = useAppStore((s) => s.activeTeamMemberName);
  if (!activeAgentName) return null;
  const agent = agents.find((a) => a.name === activeAgentName);
  if (!agent) return null;
  if (agent.type === "team" && activeTeamMemberName) {
    return agent.teamMembers?.find((m) => m.name === activeTeamMemberName) ?? null;
  }
  return agent;
};

export const useAgentModel = () => {
  const selectedAgent = useSelectedAgent();
  const models = useAppStore((s) => s.models);
  if (!selectedAgent) return null;
  return models.find((m) => m.id === selectedAgent.modelId) ?? null;
};
