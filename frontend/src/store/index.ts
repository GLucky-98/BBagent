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
  GlobalSessionIndex,
  SessionDetail,
  TeamConversation,
  TeamConversationResult,
} from "../types";
import { isTeam, isSingleAgent } from "../types";
import { api } from "../lib/api";

export interface Toast {
  id: string;
  message: string;
  type: "info" | "warning";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function agentIsBusy(state: "ready" | "waiting" | "running" | "error" | undefined): boolean {
  return state === "running";
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
  agentInputs: Record<string, string>;
  setAgentInput: (agentId: string, value: string) => void;
  clearAgentInput: (agentId: string) => void;

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

  refreshFileTreeKey: number;
  refreshFileTree: () => void;

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

  agentContextTokens: Record<string, number>;
  setAgentContextTokens: (id: string, tokens: number) => void;

  // Shared WebSocket (owned by useGlobalAgentState hook)
  chatWs: WebSocket | null;
  // ChatWindow registers its message handler here; hook delegates non-agent_state chunks
  onWsChunk: ((chunk: Record<string, unknown>) => void) | null;
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
  teamConversations: Record<string, TeamConversation[]>;
  activeTeamConversationIds: Record<string, string>;
  teamConversationPanelOpen: boolean;
  teamInputs: Record<string, string>;
  setTeamInput: (teamId: string, value: string) => void;
  clearTeamInput: (teamId: string) => void;
  addTeamMessage: (teamId: string, msg: TeamChatMessage) => void;
  loadTeamMessages: (teamId: string) => Promise<void>;
  loadTeamConversations: (teamId: string) => Promise<void>;
  createTeamConversation: (teamId: string) => Promise<void>;
  loadTeamConversation: (teamId: string, conversationId: string) => Promise<void>;
  deleteTeamConversation: (teamId: string, conversationId: string) => Promise<void>;

  loadAll: () => Promise<void>;
  createAgentApi: (payload: CreateAgentPayload) => Promise<void>;
  createTeamApi: (payload: CreateTeamPayload) => Promise<void>;

  toasts: Toast[];
  addToast: (message: string, type?: "info" | "warning") => void;
  dismissToast: (id: string) => void;

  // Global Session Manager
  globalSessions: GlobalSessionIndex[];
  sessionDetails: Record<string, SessionDetail>;
  sessionPanelOpen: boolean;
  teamGraphOpen: boolean;
  loadGlobalSessions: () => Promise<void>;
  loadSessionDetail: (sessionId: string) => Promise<void>;
  forkSession: (sessionId: string, turnIndex: number, targetAgentId?: string) => Promise<void>;
  deleteGlobalSession: (sessionId: string) => Promise<void>;
  toggleSessionPanel: () => void;
  toggleTeamGraph: () => void;
  closeTeamGraph: () => void;
  toggleTeamConversationPanel: () => void;
  closeTeamConversationPanel: () => void;

  // Team message scroll target — ListView click → TeamChatWindow scroll
  teamScrollTarget: { timestamp: number; fromAgent: string; toAgent: string } | null;
  scrollToTeamMessage: (target: { timestamp: number; fromAgent: string; toAgent: string }) => void;
  clearTeamScrollTarget: () => void;

  _loaded: boolean;
}

// Builtin tool UUIDs must match backend's BUILTIN_TOOL_IDS
// (bbagent/built_in_tool/__init__.py). Used as the React key / id when the
// API listTools() response is not yet available.
const BUILTIN_TOOL_IDS: Record<string, string> = {
  bash: "5a40e5e1-6931-4126-b142-581379f4f2eb",
  read: "4c48a29c-a52a-4ec7-b7d7-d265316091c7",
  write: "20c41591-9b4e-4ff0-9182-f11db46fef41",
  edit: "2d35e797-d8f7-41cf-aa12-e439ec74230b",
  grep: "4dc7319f-7ff7-484b-aa19-c39fa5efa772",
  find: "023a166d-246b-4aeb-be56-3119210b9bba",
  ls: "20ae9084-3a2c-413b-bdbb-86f04fb9fdd3",
  web_search: "b8fdcf95-a63b-5292-ba3f-b2b98b68c4e8",
  fetch_url: "ce38b1cb-5dad-521f-bef8-0f7ffd442e7b",
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
  {
    id: BUILTIN_TOOL_IDS.web_search,
    name: "web_search",
    source: "built_in",
    description: "Search the web and return result titles, URLs, and snippets",
  },
  {
    id: BUILTIN_TOOL_IDS.fetch_url,
    name: "fetch_url",
    source: "built_in",
    description: "Fetch a web URL and return readable text content",
  },
];

const normalizeTeamMessages = (messages: Record<string, unknown>[] = []): TeamChatMessage[] =>
  messages.map((m) => ({
    fromAgent: m.from_agent as string,
    toAgent: m.to_agent as string,
    content: typeof m.content === "string" ? m.content : JSON.stringify(m.content),
    type: m.type as "direct" | "broadcast" | "user",
    timestamp: m.timestamp as number,
  }));

type AppStateSetter = (partial: Partial<AppState> | ((state: AppState) => Partial<AppState>)) => void;

const applyConversationMessages = (
  teamId: string,
  result: TeamConversationResult,
  setState: AppStateSetter
) => {
  setState((state: AppState) => {
    const conversation = result.conversation;
    const memberSessions = conversation.memberSessions || {};
    const team = state.agents.find((a) => a.id === teamId && isTeam(a)) as Team | undefined;
    const memberIdsByName = new Map((team?.members || []).map((member) => [member.name, member.id]));
    const memberIdsWithChangedSessions = new Set<string>();
    const updatedMessages = result.messages ? normalizeTeamMessages(result.messages) : state.teamMessages[teamId] || [];
    const existingConversations = state.teamConversations[teamId] || [];
    const hasConversation = existingConversations.some((item) => item.id === conversation.id);
    const nextConversations = (hasConversation ? existingConversations : [conversation, ...existingConversations]).map((item) => ({
      ...item,
      active: item.id === conversation.id,
      ...(item.id === conversation.id ? conversation : {}),
    }));
    const nextAgentInputs = { ...state.agentInputs };

    return {
      teamMessages: {
        ...state.teamMessages,
        [teamId]: updatedMessages,
      },
      activeTeamConversationIds: {
        ...state.activeTeamConversationIds,
        [teamId]: conversation.id,
      },
      teamConversations: {
        ...state.teamConversations,
        [teamId]: nextConversations,
      },
      agents: state.agents.map((agent) => {
        if (agent.id === teamId && isTeam(agent)) {
          return {
            ...agent,
            members: agent.members.map((member) => ({
              ...member,
              currentSessionId: memberSessions[member.name] || member.currentSessionId,
            })),
          };
        }
        const memberName = [...memberIdsByName.entries()].find(([, id]) => id === agent.id)?.[0];
        if (memberName && isSingleAgent(agent)) {
          const nextSessionId = memberSessions[memberName] || agent.currentSessionId;
          if (nextSessionId !== agent.currentSessionId) {
            memberIdsWithChangedSessions.add(agent.id);
            delete nextAgentInputs[agent.id];
          }
          return {
            ...agent,
            currentSessionId: nextSessionId,
            messages: result.messages ? [] : agent.messages,
          };
        }
        return agent;
      }),
      agentInputs: memberIdsWithChangedSessions.size > 0 ? nextAgentInputs : state.agentInputs,
    };
  });
};

export const useAppStore = create<AppState>((set, get) => ({
  agents: [],
  activeAgentId: null,
  activeTeamMemberName: null,
  teamMemberIds: new Set<string>(),

  // Team messages
  teamMessages: {},
  teamConversations: {},
  activeTeamConversationIds: {},
  teamConversationPanelOpen: false,
  teamInputs: {},
  setTeamInput: (teamId, value) => {
    if (!teamId) return;
    set((state) => ({
      teamInputs: { ...state.teamInputs, [teamId]: value },
    }));
  },
  clearTeamInput: (teamId) => {
    if (!teamId) return;
    set((state) => {
      const next = { ...state.teamInputs };
      delete next[teamId];
      return { teamInputs: next };
    });
  },
  addTeamMessage: (teamId, msg) =>
    set((state) => ({
      teamMessages: {
        ...state.teamMessages,
        [teamId]: [...(state.teamMessages[teamId] || []), msg],
      },
      teamConversations: {
        ...state.teamConversations,
        [teamId]: (state.teamConversations[teamId] || []).map((conversation) =>
          conversation.active || conversation.id === state.activeTeamConversationIds[teamId]
            ? {
                ...conversation,
                messageCount: (conversation.messageCount || 0) + 1,
                updatedAt: msg.timestamp,
              }
            : conversation
        ),
      },
    })),
  loadTeamMessages: async (teamId) => {
    try {
      const messages = await api.getTeamMessages(teamId);
      set((state) => {
        const existing = state.teamMessages[teamId] || [];
        const httpMsgs = normalizeTeamMessages(messages || []);
        // 合并策略：HTTP 消息为基准，保留在此期间通过 WS 实时到达的更新消息
        // （timestamp > HTTP 最新消息的时间戳，说明是 HTTP 请求期间 WS 推送的）
        const latestHttpTs = httpMsgs.length > 0 ? httpMsgs[httpMsgs.length - 1].timestamp : 0;
        const wsOnly = existing.filter((m) => m.timestamp > latestHttpTs);
        return {
          teamMessages: {
            ...state.teamMessages,
            [teamId]: [...httpMsgs, ...wsOnly],
          },
        };
      });
    } catch (e) {
      console.error("Failed to load team messages:", e);
    }
  },
  loadTeamConversations: async (teamId) => {
    try {
      const conversations = (await api.listTeamConversations(teamId)) as TeamConversation[];
      const active = conversations.find((conversation) => conversation.active);
      set((state) => ({
        teamConversations: { ...state.teamConversations, [teamId]: conversations || [] },
        activeTeamConversationIds: active
          ? { ...state.activeTeamConversationIds, [teamId]: active.id }
          : state.activeTeamConversationIds,
      }));
    } catch (e) {
      console.error("Failed to load team conversations:", e);
    }
  },
  createTeamConversation: async (teamId) => {
    const team = get().agents.find((a) => a.id === teamId);
    const name = team ? `Conversation ${new Date().toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" })}` : undefined;
    try {
      const result = (await api.createTeamConversation(teamId, name)) as TeamConversationResult;
      get().clearTeamInput(teamId);
      applyConversationMessages(teamId, { ...result, messages: [] }, set);
      await Promise.all([
        get().loadTeamConversations(teamId),
        get().loadTeamMessages(teamId),
        get().loadGlobalSessions(),
        ...((team && isTeam(team) ? team.members : []).flatMap((member) => [
          get().loadAgentSessions(member.id),
          get().loadAgentMessages(member.id),
        ])),
      ]);
      for (const warning of result.warnings || []) get().addToast(warning, "warning");
      get().addToast("Team conversation created", "info");
    } catch (e: unknown) {
      get().addToast(`Create conversation failed: ${errorMessage(e)}`, "warning");
    }
  },
  loadTeamConversation: async (teamId, conversationId) => {
    const team = get().agents.find((a) => a.id === teamId);
    try {
      const result = (await api.loadTeamConversation(teamId, conversationId)) as TeamConversationResult;
      get().clearTeamInput(teamId);
      applyConversationMessages(teamId, result, set);
      await Promise.all([
        get().loadTeamConversations(teamId),
        get().loadGlobalSessions(),
        ...((team && isTeam(team) ? team.members : []).flatMap((member) => [
          get().loadAgentSessions(member.id),
          get().loadAgentMessages(member.id),
        ])),
      ]);
      for (const warning of result.warnings || []) get().addToast(warning, "warning");
      get().addToast("Team conversation loaded", "info");
    } catch (e: unknown) {
      get().addToast(`Load conversation failed: ${errorMessage(e)}`, "warning");
    }
  },
  deleteTeamConversation: async (teamId, conversationId) => {
    const team = get().agents.find((a) => a.id === teamId);
    try {
      const result = await api.deleteTeamConversation(teamId, conversationId);
      if (result.active) {
        const activeResult = result.active as TeamConversationResult;
        get().clearTeamInput(teamId);
        applyConversationMessages(teamId, activeResult.messages ? activeResult : { ...activeResult, messages: [] }, set);
        for (const warning of activeResult.warnings || []) get().addToast(warning, "warning");
      }
      await Promise.all([
        get().loadTeamConversations(teamId),
        get().loadTeamMessages(teamId),
        get().loadGlobalSessions(),
        ...((team && isTeam(team) ? team.members : []).flatMap((member) => [
          get().loadAgentSessions(member.id),
          get().loadAgentMessages(member.id),
        ])),
      ]);
      get().addToast("Team conversation deleted", "info");
    } catch (e: unknown) {
      get().addToast(`Delete conversation failed: ${errorMessage(e)}`, "warning");
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
      teamGraphOpen: false,
      teamConversationPanelOpen: false,
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
    const memberAgents: SingleAgent[] = ((result.members || []) as Record<string, unknown>[]).map((m) => ({
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
      currentSessionId: (m.currentSessionId as string) || "",
    }));
    const resultMemberIds = new Set(memberAgents.map((m) => m.id));

    set((state) => {
      const existingTeam = state.agents.find((a) => a.id === id && isTeam(a)) as Team | undefined;
      const previousMemberIds = new Set((existingTeam?.members || []).map((m) => m.id));
      const memberById = new Map(memberAgents.map((member) => [member.id, member]));
      const nextTeamMemberIds = new Set(state.teamMemberIds);
      for (const memberId of previousMemberIds) nextTeamMemberIds.delete(memberId);
      for (const memberId of resultMemberIds) nextTeamMemberIds.add(memberId);

      const nextAgentStates = { ...state.agentStates };
      nextAgentStates[id] = result.state || nextAgentStates[id] || "ready";
      for (const member of memberAgents) {
        nextAgentStates[member.id] = member.state || "ready";
      }

      const seenMembers = new Set<string>();
      const agents = state.agents.map((a) => {
        if (a.id === id && isTeam(a)) {
          return {
            ...a,
            ...result,
            type: "team" as const,
            members: memberAgents,
            contacts: result.contacts || {},
            messages: a.messages,
          };
        }
        const updatedMember = memberById.get(a.id);
        if (updatedMember) {
          seenMembers.add(a.id);
          return { ...a, ...updatedMember, messages: a.messages };
        }
        return a;
      });

      for (const member of memberAgents) {
        if (!seenMembers.has(member.id) && !agents.some((a) => a.id === member.id)) {
          agents.push(member);
        }
      }

      return {
        agents,
        teamMemberIds: nextTeamMemberIds,
        agentStates: nextAgentStates,
        workingDirPath: state.activeAgentId === id && result.workingDir ? result.workingDir : state.workingDirPath,
      };
    });
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
        agentInputs: Object.fromEntries(Object.entries(state.agentInputs).filter(([agentId]) => agentId !== id)),
      }));
      get().addToast(`Agent '${name}' deleted`, "info");
    } catch (e: unknown) {
      get().addToast(`Failed to delete agent '${name}': ${errorMessage(e)}`, "warning");
    }
  },
  addMessage: (agentId, message) =>
    set((state) => ({ agents: state.agents.map((a) => (a.id === agentId ? { ...a, messages: [...a.messages, message] } : a)) })),
  patchMessage: (agentId, messageId, patch) =>
    set((state) => ({
      agents: state.agents.map((a) => {
        if (a.id !== agentId) return a;
        const idx = a.messages.findIndex((m) => m.id === messageId);
        if (idx === -1) return a;
        const newMsgs = a.messages.slice();
        newMsgs[idx] = { ...newMsgs[idx], ...patch };
        return { ...a, messages: newMsgs };
      }),
    })),
  agentInputs: {},
  setAgentInput: (agentId, value) => {
    if (!agentId) return;
    set((state) => ({
      agentInputs: { ...state.agentInputs, [agentId]: value },
    }));
  },
  clearAgentInput: (agentId) => {
    if (!agentId) return;
    set((state) => {
      const next = { ...state.agentInputs };
      delete next[agentId];
      return { agentInputs: next };
    });
  },

  isSettingsOpen: false,
  settingsActiveTab: "models",
  openSettings: (tab = "models") => set({ isSettingsOpen: true, settingsActiveTab: tab }),
  closeSettings: () => set({ isSettingsOpen: false }),

  configDialog: { open: false, mode: "create", type: "" },
  openConfigDialog: (mode, type, agentId) => set({ configDialog: { open: true, mode, type, agentId } }),
  closeConfigDialog: () => set({ configDialog: { open: false, mode: "create", type: "", agentId: undefined } }),

  refreshFileTreeKey: 0,
  refreshFileTree: () => set((state) => ({ refreshFileTreeKey: state.refreshFileTreeKey + 1 })),

  workingDirPath: "",
  setWorkingDirPath: (path) => set({ workingDirPath: path }),

  baseDirPath: "",
  setBaseDirPath: (path) => set({ baseDirPath: path }),

  basedirExpandedPaths: new Set<string>(),
  toggleBasedirExpand: (path) =>
    set((state) => {
      const newSet = new Set(state.basedirExpandedPaths);
      if (newSet.has(path)) {
        newSet.delete(path);
      } else {
        newSet.add(path);
      }
      return { basedirExpandedPaths: newSet };
    }),

  workingDirExpandedPaths: new Set<string>(),
  toggleWorkingDirExpand: (path) =>
    set((state) => {
      const newSet = new Set(state.workingDirExpandedPaths);
      if (newSet.has(path)) {
        newSet.delete(path);
      } else {
        newSet.add(path);
      }
      return { workingDirExpandedPaths: newSet };
    }),

  previewFile: null,
  openFilePreview: (file) => set({ previewFile: file, sessionPanelOpen: false, teamConversationPanelOpen: false, teamGraphOpen: false }),
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
    } catch (e: unknown) {
      get().addToast(`Failed to create MCP server '${server.name}': ${errorMessage(e)}`, "warning");
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
      if (newSet.has(teamId)) {
        newSet.delete(teamId);
      } else {
        newSet.add(teamId);
      }
      return { expandedTeams: newSet };
    }),

  agentStates: {},
  agentContextTokens: {},
  chatWs: null,
  onWsChunk: null,

  setAgentState: (id, state) =>
    set((s) => ({
      agentStates: { ...s.agentStates, [id]: state },
    })),

  setAgentContextTokens: (id, tokens) =>
    set((s) => ({
      agentContextTokens: { ...s.agentContextTokens, [id]: tokens },
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
    const currentState = get().agentStates[id] || get().agents.find((a) => a.id === id)?.state;
    if (agentIsBusy(currentState)) {
      get().addToast("Cannot switch sessions while agent is running", "warning");
      return;
    }
    try {
      await api.switchSession(id, sessionId);
      get().clearAgentInput(id);
      const sessions = get().agentSessions[id] || [];
      set((s) => ({
        agents: s.agents.map((a) =>
          a.id === id
            ? {
                ...a,
                currentSessionId: sessionId,
                sessions: a.sessions.map((sess) => ({
                  ...sess,
                  isActive: sess.id === sessionId,
                })),
              }
            : a
        ),
        agentSessions: {
          ...s.agentSessions,
          [id]: sessions.map((sess) => ({
            ...sess,
            isActive: sess.id === sessionId,
          })),
        },
        globalSessions: s.globalSessions.map((sess) => (
          sess.agent_id === id
            ? { ...sess, is_active: sess.session_id === sessionId }
            : sess
        )),
      }));
      await get().loadAgentMessages(id);
    } catch (e: unknown) {
      get().addToast(`Switch session failed: ${errorMessage(e)}`, "warning");
    }
  },

  createNewSession: async (id: string) => {
    const currentState = get().agentStates[id] || get().agents.find((a) => a.id === id)?.state;
    if (agentIsBusy(currentState)) {
      get().addToast("Cannot create a new session while agent is running", "warning");
      return;
    }
    try {
      const result = await api.newSession(id);
      get().clearAgentInput(id);
      await get().loadAgentSessions(id);
      await get().loadGlobalSessions();
      set((s) => ({
        agents: s.agents.map((a) =>
          a.id === id ? { ...a, messages: [], currentSessionId: result.session_id } : a
        ),
      }));
    } catch (e: unknown) {
      get().addToast(`Create session failed: ${errorMessage(e)}`, "warning");
    }
  },

  loadAgentMessages: async (id: string) => {
    try {
      const messages = await api.getAgentMessages(id);
      set((s) => ({
        agents: s.agents.map((a) =>
          a.id === id ? { ...a, messages: messages.map((m: Record<string, unknown>, i: number) => {
            // content 可能是 string 或 list[dict]（后端 TextBlock 列表），统一转为 string
            let contentStr: string;
            const raw = m.content;
            if (typeof raw === "string") {
              contentStr = raw;
            } else if (Array.isArray(raw)) {
              contentStr = raw
                .map((b: Record<string, unknown>) => (b.type === "text" ? (b.text as string || "") : JSON.stringify(b)))
                .filter(Boolean)
                .join("\n");
            } else if (raw != null) {
              contentStr = JSON.stringify(raw);
            } else {
              contentStr = "";
            }
            return {
              id: `hist-${i}`,
              role: m.role as string,
              content: contentStr,
              timestamp: m.timestamp as number,
              sourceAgent: (m.source_agent || m.sourceAgent) as string | undefined,
              chunkType: m.chunkType as string | undefined,
              toolName: m.toolName as string | undefined,
              toolInput: m.toolInput as Record<string, unknown> | undefined,
            };
          }) } : a
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
      await api.startAgent(id);
      get().addToast(`Agent '${name}' started`, "info");
    } catch (e: unknown) {
      get().addToast(`Failed to start agent '${name}': ${errorMessage(e)}`, "warning");
    }
  },

  stopAgent: async (id: string) => {
    const agent = get().agents.find((a) => a.id === id);
    const name = agent?.name || id;
    try {
      await api.stopAgent(id);
      get().addToast(`Agent '${name}' stopped`, "info");
    } catch (e: unknown) {
      get().addToast(`Failed to stop agent '${name}': ${errorMessage(e)}`, "warning");
    }
  },

  startTeam: async (id: string) => {
    const agent = get().agents.find((a) => a.id === id);
    const name = agent?.name || id;
    try {
      await api.startTeam(id);
      get().addToast(`Team '${name}' started`, "info");
    } catch (e: unknown) {
      get().addToast(`Failed to start team '${name}': ${errorMessage(e)}`, "warning");
    }
  },

  stopTeam: async (id: string) => {
    const agent = get().agents.find((a) => a.id === id);
    const name = agent?.name || id;
    try {
      await api.stopTeam(id);
      get().addToast(`Team '${name}' stopped`, "info");
    } catch (e: unknown) {
      get().addToast(`Failed to stop team '${name}': ${errorMessage(e)}`, "warning");
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
        teamInputs: Object.fromEntries(Object.entries(state.teamInputs).filter(([teamId]) => teamId !== id)),
      }));
      get().addToast(`Team '${name}' deleted`, "info");
    } catch (e: unknown) {
      get().addToast(`Failed to delete team '${name}': ${errorMessage(e)}`, "warning");
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
    } catch (e: unknown) {
      get().addToast(`Failed to add timer: ${errorMessage(e)}`, "warning");
    }
  },

  updateTimer: async (id, name, data) => {
    try {
      const timers = await api.updateTimer(id, name, data);
      set((s) => ({ agentTimers: { ...s.agentTimers, [id]: timers || [] } }));
    } catch (e: unknown) {
      get().addToast(`Failed to update timer: ${errorMessage(e)}`, "warning");
    }
  },

  startTimer: async (id, name) => {
    try {
      await api.startTimer(id, name);
      await get().loadTimers(id);
    } catch (e: unknown) {
      get().addToast(`Failed to start timer: ${errorMessage(e)}`, "warning");
    }
  },

  stopTimer: async (id, name) => {
    try {
      await api.stopTimer(id, name);
      await get().loadTimers(id);
    } catch (e: unknown) {
      get().addToast(`Failed to stop timer: ${errorMessage(e)}`, "warning");
    }
  },

  deleteTimer: async (id, name) => {
    try {
      const timers = await api.deleteTimer(id, name);
      set((s) => ({ agentTimers: { ...s.agentTimers, [id]: timers || [] } }));
    } catch (e: unknown) {
      get().addToast(`Failed to delete timer: ${errorMessage(e)}`, "warning");
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
      const agentContextTokensMap: Record<string, number> = {};

      for (const agent of deduped) {
        agentStates[agent.id] = agent.state || "ready";
        agentSessionsMap[agent.id] = agent.sessions || [];
      }
      // Extract contextTokens from raw API data (not part of Agent type)
      for (const a of (agents || []) as Record<string, unknown>[]) {
        if (a.id && typeof a.contextTokens === "number") {
          agentContextTokensMap[a.id as string] = a.contextTokens as number;
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
        agentContextTokens: agentContextTokensMap,
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

      // Auto-select first visible agent if none is active
      if (!get().activeAgentId && deduped.length > 0) {
        const firstVisible = deduped.find((a: Agent) => !teamMemberIds.has(a.id));
        if (firstVisible) {
          get().setActiveAgentId(firstVisible.id);
        }
      }

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
      const newAgentStates = { ...state.agentStates };
      for (const m of memberAgents) {
        newAgentStates[m.id] = m.state || "ready";
      }
      newAgentStates[team.id] = team.state || "ready";
      return {
        agents: [...state.agents, ...memberAgents, team],
        teamMemberIds: newMemberIds,
        activeAgentId: team.id,
        workingDirPath: team.workingDir,
        baseDirPath: team.baseDir,
        agentStates: newAgentStates,
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

  // Global Session Manager
  globalSessions: [],
  sessionDetails: {},
  sessionPanelOpen: false,
  teamGraphOpen: true,

  loadGlobalSessions: async () => {
    try {
      const sessions = await api.listGlobalSessions();
      set({ globalSessions: sessions || [] });
    } catch (e) {
      console.error("Failed to load global sessions:", e);
    }
  },

  loadSessionDetail: async (sessionId: string) => {
    try {
      const detail = await api.getSessionDetail(sessionId);
      set((s) => ({
        sessionDetails: { ...s.sessionDetails, [sessionId]: detail },
      }));
    } catch (e) {
      console.error("Failed to load session detail:", e);
    }
  },

  forkSession: async (sessionId: string, turnIndex: number, targetAgentId?: string) => {
    try {
      const result = await api.forkSession(sessionId, turnIndex, targetAgentId);
      get().addToast(`Forked to new session: ${result.sessionId?.substring(0, 16)}...`, "info");
      // 后端已切换 agent 到新 session，前端刷新消息和 session 列表
      const activeId = get().activeAgentId;
      if (activeId) {
        await get().loadAgentMessages(activeId);
        await get().loadAgentSessions(activeId);
      }
      get().refreshFileTree();
      await get().loadGlobalSessions();
    } catch (e: unknown) {
      get().addToast(`Fork failed: ${errorMessage(e)}`, "warning");
    }
  },

  deleteGlobalSession: async (sessionId: string) => {
    try {
      await api.deleteGlobalSession(sessionId);
      set((s) => {
        const rest = { ...s.sessionDetails };
        delete rest[sessionId];
        return {
          globalSessions: s.globalSessions.filter((gs) => gs.session_id !== sessionId),
          sessionDetails: rest,
        };
      });
      get().addToast("Session deleted", "info");
    } catch (e: unknown) {
      get().addToast(`Delete failed: ${errorMessage(e)}`, "warning");
    }
  },

  toggleSessionPanel: () => {
    set((s) => {
      const next = !s.sessionPanelOpen;
      // 打开 session 面板时关闭文件预览，反之亦然
      return {
        sessionPanelOpen: next,
        previewFile: next ? null : s.previewFile,
        teamConversationPanelOpen: next ? false : s.teamConversationPanelOpen,
        teamGraphOpen: next ? false : s.teamGraphOpen,
      };
    });
  },

  toggleTeamGraph: () => {
    set((s) => {
      const next = !s.teamGraphOpen;
      return {
        teamGraphOpen: next,
        previewFile: next ? null : s.previewFile,
        sessionPanelOpen: next ? false : s.sessionPanelOpen,
        teamConversationPanelOpen: next ? false : s.teamConversationPanelOpen,
      };
    });
  },

  closeTeamGraph: () => {
    set({ teamGraphOpen: false });
  },

  toggleTeamConversationPanel: () => {
    set((s) => {
      const next = !s.teamConversationPanelOpen;
      return {
        teamConversationPanelOpen: next,
        previewFile: next ? null : s.previewFile,
        sessionPanelOpen: next ? false : s.sessionPanelOpen,
        teamGraphOpen: next ? false : s.teamGraphOpen,
      };
    });
  },

  closeTeamConversationPanel: () => {
    set({ teamConversationPanelOpen: false });
  },

  teamScrollTarget: null,
  scrollToTeamMessage: (target) => set({ teamScrollTarget: target }),
  clearTeamScrollTarget: () => set({ teamScrollTarget: null }),

  _loaded: false,
}));

export const useSelectedAgent = () => {
  return useAppStore((s) => {
    if (!s.activeAgentId) return null;
    const agent = s.agents.find((a) => a.id === s.activeAgentId);
    if (!agent) return null;
    if (isTeam(agent) && s.activeTeamMemberName) {
      return agent.members.find((m) => m.name === s.activeTeamMemberName) ?? null;
    }
    return agent;
  });
};

export const useAgentModel = () => {
  const selectedAgent = useSelectedAgent();
  const models = useAppStore((s) => s.models);
  if (!selectedAgent || !isSingleAgent(selectedAgent)) return null;
  return models.find((m) => m.id === selectedAgent.modelId) ?? null;
};
