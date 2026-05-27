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
} from "../types";

interface AppState {
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
  addModel: (model: Model) => void;
  updateModel: (id: string, updates: Partial<Model>) => void;

  tools: Tool[];
  mcpServers: MCPServer[];
  selectedMcpId: string | null;
  setSelectedMcpId: (id: string | null) => void;
  updateMcpConnection: (name: string, isConnected: boolean) => void;
  addMcpServer: (server: MCPServer) => void;
  importMcpServers: (servers: MCPServer[]) => void;

  skills: Skill[];
  selectedSkillId: string | null;
  setSelectedSkillId: (id: string | null) => void;
  importSkills: (skills: Skill[]) => void;

  prompts: Prompt[];
  selectedPromptId: string | null;
  setSelectedPromptId: (id: string | null) => void;
  importPrompts: (prompts: Prompt[]) => void;

  expandedTeams: Set<string>;
  toggleTeamExpanded: (teamId: string) => void;
}

const defaultModels: Model[] = [
  {
    id: "model-1",
    name: "Claude Sonnet 4",
    provider: "anthropic",
    modelName: "claude-sonnet-4-20250514",
    apiKey: "",
    baseUrl: "https://api.anthropic.com",
    maxContextTokens: 200000,
    maxCompletionTokens: 100000,
    temperature: 1,
    topP: 0.95,
    thinking: { type: "adaptive" },
  },
  {
    id: "model-2",
    name: "Claude Opus 4",
    provider: "anthropic",
    modelName: "claude-opus-4-20250514",
    apiKey: "",
    baseUrl: "https://api.anthropic.com",
    maxContextTokens: 200000,
    maxCompletionTokens: 100000,
    temperature: 1,
    topP: 0.95,
    thinking: { type: "adaptive" },
  },
  {
    id: "model-3",
    name: "GPT-4o",
    provider: "openai",
    modelName: "gpt-4o",
    apiKey: "",
    baseUrl: "https://api.openai.com/v1",
    maxContextTokens: 128000,
    maxCompletionTokens: 100000,
    temperature: 1,
    topP: 1,
    thinking: { type: "enabled" },
  },
  {
    id: "model-4",
    name: "text-embedding-3-large",
    provider: "openai",
    modelName: "text-embedding-3-large",
    apiKey: "",
    baseUrl: "https://api.openai.com/v1",
    maxContextTokens: 8192,
    maxCompletionTokens: 8192,
  },
];

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
    id: "mcp-tool-1",
    name: "firecrawl_scrape",
    description: "Extract clean markdown from any URL",
    inputSchema: {
      type: "object",
      properties: { url: { type: "string", description: "The URL to scrape" } },
      required: ["url"],
    },
    isMcp: true,
    mcpServerName: "firecrawl",
  },
  {
    id: "mcp-tool-2",
    name: "firecrawl_search",
    description: "Web search with full page content extraction",
    inputSchema: {
      type: "object",
      properties: { query: { type: "string", description: "The search query" } },
      required: ["query"],
    },
    isMcp: true,
    mcpServerName: "firecrawl",
  },
];

const defaultSkills: Skill[] = [
  {
    name: "code-expert",
    description: "Expert coding assistant with multi-language support",
    path: "/skills/code-expert",
    metadata: { license: "MIT", compatibility: "All platforms", version: "1.0.0", allowedTools: ["bash", "read", "write", "edit"] },
    body: "You are an expert code assistant with deep knowledge of multiple programming languages.",
    source: "default",
  },
  {
    name: "research-analyst",
    description: "Research and analysis skill for gathering and synthesizing information",
    path: "/skills/research-analyst",
    metadata: { license: "MIT", compatibility: "All platforms", version: "1.2.0", allowedTools: ["grep", "find"] },
    body: "You are a research analyst specializing in gathering and synthesizing information.",
    source: "default",
  },
  {
    name: "web-scraper",
    description: "Extract and structure data from websites",
    path: "/skills/web-scraper",
    metadata: { license: "Apache-2.0", compatibility: "All platforms", version: "2.1.0", allowedTools: ["firecrawl_scrape", "firecrawl_search"] },
    body: "You are a web scraping expert capable of extracting structured data from websites.",
    source: "default",
  },
];

const defaultMcpServers: MCPServer[] = [
  {
    name: "firecrawl",
    command: "npx",
    args: ["-y", "@firecrawl/mcp"],
    env: { FIRECRAWL_API_KEY: "" },
    isConnected: false,
    tools: [],
    source: "default",
  },
  {
    name: "filesystem",
    command: "python",
    args: ["-m", "mcp_server_filesystem"],
    env: {},
    isConnected: true,
    tools: [],
    source: "default",
  },
];

const defaultPrompts: Prompt[] = [
  {
    id: "prompt-1",
    name: "code-review",
    description: "Review code for quality, bugs, and best practices",
    content: "You are an expert code reviewer. Analyze the provided code and give constructive feedback on code quality, bugs, best practices, performance, and security.",
    source: "built-in",
  },
  {
    id: "prompt-2",
    name: "research-summary",
    description: "Summarize research findings into actionable insights",
    content: "You are a research analyst. Given a set of research findings, create a comprehensive summary with key findings, supporting evidence, contradictions, implications, and next steps.",
    source: "built-in",
  },
  {
    id: "prompt-3",
    name: "task-decomposition",
    description: "Break down complex tasks into manageable steps",
    content: "You are a task planning expert. Break down complex goals into clear, actionable steps with dependencies, sub-tasks, time estimates, and risks.",
    source: "built-in",
  },
  {
    id: "prompt-4",
    name: "debugging-assistant",
    description: "Help identify and fix software bugs",
    content: "You are a debugging expert. Help reproduce bugs, propose causes, guide investigation, verify fixes, and document solutions.",
    source: "built-in",
  },
];

const defaultAgents: Agent[] = [];

export const useAppStore = create<AppState>((set, get) => ({
  agents: defaultAgents,
  activeAgentId: null,
  activeTeamMemberId: null,

  setActiveAgentId: (id) => {
    const agent = id ? get().agents.find((a) => a.id === id) : null;
    set({ activeAgentId: id, activeTeamMemberId: null, workingDirPath: agent?.basePath ?? "", previewFile: null });
  },

  selectTeamMember: (teamId, memberId) => {
    if (memberId) {
      const team = get().agents.find((a) => a.id === teamId);
      const member = team?.teamMembers?.find((m) => m.id === memberId);
      set({ activeAgentId: teamId, activeTeamMemberId: memberId, workingDirPath: member?.basePath ?? "", previewFile: null });
    } else {
      const team = get().agents.find((a) => a.id === teamId);
      set({ activeAgentId: teamId, activeTeamMemberId: null, workingDirPath: team?.basePath ?? "", previewFile: null });
    }
  },

  addAgent: (agent) => set((state) => ({ agents: [...state.agents, agent], activeAgentId: agent.id, workingDirPath: agent.basePath })),
  addTeam: (team) => set((state) => ({ agents: [...state.agents, team], activeAgentId: team.id, workingDirPath: team.basePath })),
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

  models: defaultModels,
  selectedModelId: null,
  setSelectedModelId: (id) => set({ selectedModelId: id }),
  addModel: (model) => set((state) => ({ models: [...state.models, model] })),
  updateModel: (id, updates) =>
    set((state) => ({ models: state.models.map((m) => (m.id === id ? { ...m, ...updates } : m)) })),

  tools: defaultTools,

  mcpServers: defaultMcpServers,
  selectedMcpId: null,
  setSelectedMcpId: (id) => set({ selectedMcpId: id }),
  updateMcpConnection: (name, isConnected) =>
    set((state) => ({ mcpServers: state.mcpServers.map((m) => (m.name === name ? { ...m, isConnected } : m)) })),
  addMcpServer: (server) => set((state) => ({ mcpServers: [...state.mcpServers, server] })),
  importMcpServers: (servers) => set((state) => ({ mcpServers: [...state.mcpServers, ...servers] })),

  skills: defaultSkills,
  selectedSkillId: null,
  setSelectedSkillId: (id) => set({ selectedSkillId: id }),
  importSkills: (skills) => set((state) => ({ skills: [...state.skills, ...skills] })),

  prompts: defaultPrompts,
  selectedPromptId: null,
  setSelectedPromptId: (id) => set({ selectedPromptId: id }),
  importPrompts: (prompts) => set((state) => ({ prompts: [...state.prompts, ...prompts] })),

  expandedTeams: new Set<string>(),
  toggleTeamExpanded: (teamId) =>
    set((state) => {
      const newSet = new Set(state.expandedTeams);
      newSet.has(teamId) ? newSet.delete(teamId) : newSet.add(teamId);
      return { expandedTeams: newSet };
    }),
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
