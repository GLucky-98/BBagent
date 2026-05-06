import { create } from "zustand";
import type {
  Agent,
  Model,
  NavItem,
  Message,
  Tool,
  Skill,
  MCPServer,
  Prompt,
} from "../types";

interface AppState {
  currentNav: NavItem;
  setCurrentNav: (nav: NavItem) => void;

  agents: Agent[];
  selectedAgentId: string | null;
  setSelectedAgentId: (id: string | null) => void;
  addAgent: (agent: Agent) => void;
  addTeam: (team: Agent) => void;
  updateAgent: (id: string, updates: Partial<Agent>) => void;
  addMessage: (agentId: string, message: Message) => void;

  models: Model[];
  selectedModelId: string | null;
  setSelectedModelId: (id: string | null) => void;
  addModel: (model: Model) => void;

  tools: Tool[];
  selectedToolId: string | null;
  setSelectedToolId: (id: string | null) => void;

  mcpServers: MCPServer[];
  selectedMcpId: string | null;
  setSelectedMcpId: (id: string | null) => void;
  updateMcpConnection: (id: string, isConnected: boolean) => void;

  skills: Skill[];
  selectedSkillId: string | null;
  setSelectedSkillId: (id: string | null) => void;

  prompts: Prompt[];
  selectedPromptId: string | null;
  setSelectedPromptId: (id: string | null) => void;

  isCreateDialogOpen: boolean;
  createType: "single" | "team" | null;
  setIsCreateDialogOpen: (open: boolean) => void;
  setCreateType: (type: "single" | "team" | null) => void;

  expandedTeams: Set<string>;
  toggleTeamExpanded: (teamId: string) => void;
}

const defaultModels: Model[] = [
  {
    id: "model-1",
    name: "Claude Sonnet 4",
    type: "chat",
    provider: "anthropic",
    baseUrl: "https://api.anthropic.com",
    apiKey: "",
    modelName: "claude-sonnet-4-20250514",
  },
  {
    id: "model-2",
    name: "Claude Opus 4",
    type: "chat",
    provider: "anthropic",
    baseUrl: "https://api.anthropic.com",
    apiKey: "",
    modelName: "claude-opus-4-20250514",
  },
  {
    id: "model-3",
    name: "GPT-4o",
    type: "chat",
    provider: "openai",
    baseUrl: "https://api.openai.com/v1",
    apiKey: "",
    modelName: "gpt-4o",
  },
  {
    id: "model-4",
    name: "text-embedding-3-large",
    type: "embedding",
    provider: "openai",
    baseUrl: "https://api.openai.com/v1",
    apiKey: "",
    modelName: "text-embedding-3-large",
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
        output_mode: { type: "string", description: "Output format: content, files_with_matches, count" },
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
      properties: {
        path: { type: "string", description: "Directory to list" },
      },
      required: ["path"],
    },
    isMcp: false,
  },
  {
    id: "mcp-tool-1",
    name: "firecrawl_scrape",
    description: "Extract clean markdown from any URL, including JavaScript-rendered SPAs",
    inputSchema: {
      type: "object",
      properties: {
        url: { type: "string", description: "The URL to scrape" },
      },
      required: ["url"],
    },
    isMcp: true,
  },
  {
    id: "mcp-tool-2",
    name: "firecrawl_search",
    description: "Web search with full page content extraction",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "The search query" },
        num: { type: "number", description: "Maximum number of results" },
      },
      required: ["query"],
    },
    isMcp: true,
  },
];

const defaultSkills: Skill[] = [
  {
    id: "skill-1",
    name: "code-expert",
    description: "Expert coding assistant with multi-language support",
    path: "/skills/code-expert",
    metadata: {
      license: "MIT",
      compatibility: "All platforms",
      version: "1.0.0",
      allowedTools: ["bash", "read", "write", "edit"],
    },
    body: "You are an expert code assistant with deep knowledge of multiple programming languages including Python, JavaScript, TypeScript, Rust, Go, and more. You help users write clean, efficient, and maintainable code.\n\nYour expertise includes:\n- Writing new code from scratch\n- Debugging and fixing issues\n- Code review and best practices\n- Performance optimization\n- Writing tests",
  },
  {
    id: "skill-2",
    name: "research-analyst",
    description: "Research and analysis skill for gathering and synthesizing information",
    path: "/skills/research-analyst",
    metadata: {
      license: "MIT",
      compatibility: "All platforms",
      version: "1.2.0",
      allowedTools: ["grep", "find"],
    },
    body: "You are a research analyst specializing in gathering, organizing, and synthesizing information from various sources. You excel at:\n\n- Finding relevant information efficiently\n- Synthesizing findings into coherent summaries\n- Identifying key insights and patterns\n- Cross-referencing multiple sources\n- Presenting findings in clear, actionable formats",
  },
  {
    id: "skill-3",
    name: "web-scraper",
    description: "Extract and structure data from websites",
    path: "/skills/web-scraper",
    metadata: {
      license: "Apache-2.0",
      compatibility: "All platforms",
      version: "2.1.0",
      allowedTools: ["firecrawl_scrape", "firecrawl_search"],
    },
    body: "You are a web scraping expert capable of extracting structured data from websites. You can handle:\n\n- Single page extraction\n- Multi-page crawling\n- JavaScript-rendered content\n- Structured data extraction\n- Handling anti-scraping measures",
  },
];

const defaultMcpServers: MCPServer[] = [
  {
    id: "mcp-1",
    name: "firecrawl",
    command: "npx",
    args: ["-y", "@firecrawl/mcp"],
    env: { FIRECRAWL_API_KEY: "" },
    isConnected: false,
    tools: defaultTools.filter((t) => t.isMcp),
  },
  {
    id: "mcp-2",
    name: "filesystem",
    command: "python",
    args: ["-m", "mcp_server_filesystem"],
    env: {},
    isConnected: true,
    tools: defaultTools.filter((t) => !t.isMcp),
  },
];

const defaultPrompts: Prompt[] = [
  {
    id: "prompt-1",
    name: "code-review",
    description: "Review code for quality, bugs, and best practices",
    content: `You are an expert code reviewer. Analyze the provided code and give constructive feedback on:

1. **Code Quality**: Is the code clean, readable, and well-organized?
2. **Bugs**: Are there any obvious bugs, edge cases, or potential runtime errors?
3. **Best Practices**: Does the code follow language-specific best practices?
4. **Performance**: Are there any obvious performance issues?
5. **Security**: Are there any potential security vulnerabilities?

Provide your review in a structured format with specific suggestions for improvement.`,
  },
  {
    id: "prompt-2",
    name: "research-summary",
    description: "Summarize research findings into actionable insights",
    content: `You are a research analyst. Given a set of research findings or documents, create a comprehensive summary that:

1. **Key Findings**: List the most important discoveries
2. **Supporting Evidence**: Note the strength of evidence for each finding
3. **Contradictions**: Highlight any conflicting information
4. **Implications**: Discuss what the findings mean in practice
5. **Next Steps**: Suggest actionable next steps based on the research

Format your response clearly with headers and bullet points for easy reading.`,
  },
  {
    id: "prompt-3",
    name: "task-decomposition",
    description: "Break down complex tasks into manageable steps",
    content: `You are a task planning expert. Given a complex goal or task, break it down into clear, actionable steps:

1. **Goal Understanding**: Confirm understanding of the end objective
2. **Dependencies**: Identify what needs to be done first
3. **Sub-tasks**: Break down into discrete, completable units
4. **Time Estimate**: Provide rough time estimates for each step
5. **Risks**: Note potential blockers or failure points

Present the plan as a numbered sequence with clear descriptions of each step.`,
  },
  {
    id: "prompt-4",
    name: "debugging-assistant",
    description: "Help identify and fix software bugs",
    content: `You are a debugging expert. When helping fix bugs:

1. **Reproduce**: Help the user create a minimal reproduction case
2. **Hypothesize**: Propose possible causes based on error messages and symptoms
3. **Investigate**: Guide the user through diagnostic steps
4. **Verify**: Confirm the fix works and doesn't break other functionality
5. **Document**: Summarize what was wrong and how it was fixed

Ask clarifying questions to narrow down the issue before proposing solutions.`,
  },
];

const defaultAgents: Agent[] = [
  {
    id: "agent-1",
    name: "Code Assistant",
    type: "single",
    basePath: "/agents/code-assistant",
    primaryModel: defaultModels[0],
    secondaryModel: defaultModels[2],
    systemPrompt:
      "You are an expert code assistant. Help users write, debug, and understand code.",
    tools: [],
    skills: [],
    contextHook: "",
    messages: [
      {
        id: "msg-1",
        role: "user",
        content: "Hello! Can you help me write a Python function?",
        timestamp: Date.now() - 300000,
      },
      {
        id: "msg-2",
        role: "assistant",
        content: "Of course! I'd be happy to help you write a Python function. What would you like the function to do?",
        timestamp: Date.now() - 290000,
      },
    ],
  },
  {
    id: "agent-2",
    name: "Research Agent",
    type: "single",
    basePath: "/agents/research",
    primaryModel: defaultModels[1],
    systemPrompt:
      "You are a research assistant. Help users find and summarize information.",
    tools: [],
    skills: [],
    messages: [],
  },
  {
    id: "team-1",
    name: "Dev Team",
    type: "team",
    basePath: "/teams/dev",
    primaryModel: defaultModels[0],
    systemPrompt: "Coordinate a team of specialized agents to handle development tasks.",
    tools: [],
    skills: [],
    teamPrompt:
      "Coordinate the research, coding, and review agents to deliver high-quality code.",
    teamMembers: [
      {
        id: "agent-3",
        name: "Researcher",
        type: "single",
        basePath: "/teams/dev/researcher",
        primaryModel: defaultModels[1],
        systemPrompt: "Research and gather information for development tasks.",
        tools: [],
        skills: [],
        messages: [],
      },
      {
        id: "agent-4",
        name: "Coder",
        type: "single",
        basePath: "/teams/dev/coder",
        primaryModel: defaultModels[0],
        systemPrompt: "Write code based on research and requirements.",
        tools: [],
        skills: [],
        messages: [],
      },
      {
        id: "agent-5",
        name: "Reviewer",
        type: "single",
        basePath: "/teams/dev/reviewer",
        primaryModel: defaultModels[0],
        systemPrompt: "Review code for quality and best practices.",
        tools: [],
        skills: [],
        messages: [],
      },
    ],
    messages: [],
  },
];

export const useAppStore = create<AppState>((set) => ({
  currentNav: "agents",
  setCurrentNav: (nav) => set({ currentNav: nav }),

  agents: defaultAgents,
  selectedAgentId: null,
  setSelectedAgentId: (id) => set({ selectedAgentId: id }),
  addAgent: (agent) => set((state) => ({ agents: [...state.agents, agent] })),
  addTeam: (team) => set((state) => ({ agents: [...state.agents, team] })),
  updateAgent: (id, updates) =>
    set((state) => ({
      agents: state.agents.map((a) => (a.id === id ? { ...a, ...updates } : a)),
    })),
  addMessage: (agentId, message) =>
    set((state) => ({
      agents: state.agents.map((a) =>
        a.id === agentId ? { ...a, messages: [...a.messages, message] } : a
      ),
    })),

  models: defaultModels,
  selectedModelId: null,
  setSelectedModelId: (id) => set({ selectedModelId: id }),
  addModel: (model) => set((state) => ({ models: [...state.models, model] })),

  tools: defaultTools,
  selectedToolId: null,
  setSelectedToolId: (id) => set({ selectedToolId: id }),

  mcpServers: defaultMcpServers,
  selectedMcpId: null,
  setSelectedMcpId: (id) => set({ selectedMcpId: id }),
  updateMcpConnection: (id, isConnected) =>
    set((state) => ({
      mcpServers: state.mcpServers.map((m) =>
        m.id === id ? { ...m, isConnected } : m
      ),
    })),

  skills: defaultSkills,
  selectedSkillId: null,
  setSelectedSkillId: (id) => set({ selectedSkillId: id }),

  prompts: defaultPrompts,
  selectedPromptId: null,
  setSelectedPromptId: (id) => set({ selectedPromptId: id }),

  isCreateDialogOpen: false,
  createType: null,
  setIsCreateDialogOpen: (open) => set({ isCreateDialogOpen: open }),
  setCreateType: (type) => set({ createType: type }),

  expandedTeams: new Set(),
  toggleTeamExpanded: (teamId) =>
    set((state) => {
      const newSet = new Set(state.expandedTeams);
      if (newSet.has(teamId)) {
        newSet.delete(teamId);
      } else {
        newSet.add(teamId);
      }
      return { expandedTeams: newSet };
    }),
}));

export const useSelectedAgent = () => {
  const agents = useAppStore((state) => state.agents);
  const selectedAgentId = useAppStore((state) => state.selectedAgentId);
  return agents.find((a) => a.id === selectedAgentId) || null;
};
