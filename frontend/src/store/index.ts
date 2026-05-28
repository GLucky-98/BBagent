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
} from "../types";
import { api } from "../lib/api";

export interface AppState {
  agents: Agent[];
  activeAgentId: string | null;
  activeTeamMemberId: string | null;
  setActiveAgentId: (id: string | null) => void;
  selectTeamMember: (teamId: string, memberId: string | null) => void;
  addAgent: (agent: Agent) => void;
  addTeam: (team: Agent) => void;
  updateAgent: (id: string, updates: Partial<Agent>) => void;
  updateTeam: (id: string, updates: Partial<Agent>) => void;
  addMessage: (agentId: string, message: Message) => void;

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

  previewFile: {
    path: string;
    name: string;
    content: string | null;
    mimeType: string;
  } | null;
  openFilePreview: (file: {
    path: string;
    name: string;
    content: string | null;
    mimeType: string;
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
  updateMcpConnection: (name: string, isConnected: boolean) => void;
  addMcpServer: (server: MCPServer) => Promise<void>;
  importMcpServers: (servers: MCPServer[]) => void;

  skills: Skill[];
  selectedSkillId: string | null;
  setSelectedSkillId: (id: string | null) => void;
  importSkills: (skills: Skill[]) => void;

  prompts: Prompt[];
  selectedPromptId: string | null;
  setSelectedPromptId: (id: string | null) => void;
  addPrompt: (prompt: Prompt) => Promise<void>;
  importPrompts: (prompts: Prompt[]) => void;

  expandedTeams: Set<string>;
  toggleTeamExpanded: (teamId: string) => void;

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
];

export const useAppStore = create<AppState>((set, get) => ({
  agents: [],
  activeAgentId: null,
  activeTeamMemberId: null,

  setActiveAgentId: (id) => {
    const agent = id ? get().agents.find((a) => a.id === id) : null;
    set({
      activeAgentId: id,
      activeTeamMemberId: null,
      workingDirPath: agent?.policy?.cwd || "",
      baseDirPath: agent?.basePath || "",
      previewFile: null,
    });
  },

  selectTeamMember: (teamId, memberId) => {
    if (memberId) {
      const team = get().agents.find((a) => a.id === teamId);
      const member = team?.teamMembers?.find((m) => m.id === memberId);
      set({ activeAgentId: teamId, activeTeamMemberId: memberId, workingDirPath: member?.policy?.cwd || "", baseDirPath: member?.basePath || "", previewFile: null });
    } else {
      const team = get().agents.find((a) => a.id === teamId);
      set({ activeAgentId: teamId, activeTeamMemberId: null, workingDirPath: team?.policy?.cwd || "", baseDirPath: team?.basePath || "", previewFile: null });
    }
  },

  addAgent: (agent) => set((state) => ({ agents: [...state.agents, agent], activeAgentId: agent.id, workingDirPath: agent.policy?.cwd || "", baseDirPath: agent.basePath })),
  addTeam: (team) => set((state) => ({ agents: [...state.agents, team], activeAgentId: team.id, workingDirPath: team.policy?.cwd || "", baseDirPath: team.basePath })),
  updateAgent: (id, updates) => set((state) => ({ agents: state.agents.map((a) => (a.id === id ? { ...a, ...updates } : a)) })),
  updateTeam: (id, updates) => set((state) => ({ agents: state.agents.map((a) => (a.id === id ? { ...a, ...updates } : a)) })),
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
  updateMcpConnection: (name, isConnected) =>
    set((state) => ({ mcpServers: state.mcpServers.map((m) => (m.name === name ? { ...m, isConnected } : m)) })),
  addMcpServer: async (server) => {
    await api.createMcp(server);
    set((state) => ({ mcpServers: [...state.mcpServers, server] }));
  },
  importMcpServers: (servers) => set((state) => ({ mcpServers: [...state.mcpServers, ...servers] })),

  skills: [],
  selectedSkillId: null,
  setSelectedSkillId: (id) => set({ selectedSkillId: id }),
  importSkills: (skills) => set((state) => ({ skills: [...state.skills, ...skills] })),

  prompts: [],
  selectedPromptId: null,
  setSelectedPromptId: (id) => set({ selectedPromptId: id }),
  addPrompt: async (prompt) => {
    await api.createPrompt(prompt);
    set((state) => ({ prompts: [...state.prompts, prompt] }));
  },
  importPrompts: (prompts) => set((state) => ({ prompts: [...state.prompts, ...prompts] })),

  expandedTeams: new Set<string>(),
  toggleTeamExpanded: (teamId) =>
    set((state) => {
      const newSet = new Set(state.expandedTeams);
      newSet.has(teamId) ? newSet.delete(teamId) : newSet.add(teamId);
      return { expandedTeams: newSet };
    }),

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
      set({
        models: models || [],
        mcpServers: mcps || [],
        prompts: prompts || [],
        skills: skills || [],
        agents: (agents || []).concat(teams || []),
        workingDirPath: state?.workingDirPath || "",
        baseDirPath: state?.baseDirPath || "",
      });
    } catch (e) {
      console.error("Failed to load state from backend:", e);
    }
  },

  createAgentApi: async (agent: Agent) => {
    await api.createAgent(agent);
    set((state) => ({ agents: [...state.agents, agent], activeAgentId: agent.id }));
  },

  createTeamApi: async (team: Agent) => {
    await api.createTeam(team);
    set((state) => ({ agents: [...state.agents, team], activeAgentId: team.id }));
  },
}));

export const useSelectedAgent = () => {
  const agents = useAppStore((s) => s.agents);
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const activeTeamMemberId = useAppStore((s) => s.activeTeamMemberId);
  if (!activeAgentId) return null;
  const agent = agents.find((a) => a.id === activeAgentId);
  if (!agent) return null;
  if (agent.type === "team" && activeTeamMemberId) {
    return agent.teamMembers?.find((m) => m.id === activeTeamMemberId) ?? null;
  }
  return agent;
};

export const useAgentModel = () => {
  const selectedAgent = useSelectedAgent();
  const models = useAppStore((s) => s.models);
  if (!selectedAgent) return null;
  return models.find((m) => m.id === selectedAgent.modelId) ?? null;
};
