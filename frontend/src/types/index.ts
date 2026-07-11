export interface Model {
  id: string;
  name: string;
  provider: "anthropic" | "openai";
  modelName: string;
  apiKey: string;
  baseUrl: string;
  maxContextTokens: number;
  maxCompletionTokens: number;
  maxConcurrent?: number;
  temperature?: number;
  topP?: number;
  thinking?: boolean;
}

// Tool represents both built-in tools and MCP tools (unified-id design):
// - id: unique template_id (UUID). Frontend uses as React key and storage value for agent.toolIds
// - name: builtin is short name (e.g. 'bash'), MCP tool is rawName
// - source: tool source ("built_in" | "mcp" | "hook" | "team")
// - mcpServerId: only set for MCP tools, references MCPServerConfig.id
// - mcpServerName: only for UI grouping, references MCPServerConfig.name (not used for routing)
export interface Tool {
  id: string;
  name: string;
  source: "built_in" | "hook" | "mcp" | "team";
  description: string;
  mcpServerId?: string;
  mcpServerName?: string;  // UI grouping only
}

export interface Skill {
  id: string;
  name: string;
  description: string;
  path: string;
}

export interface MCPServer {
  id: string;
  name: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  tools: Tool[];
}

export interface Prompt {
  id: string;
  name: string;
  content: string;
  group: string;
}

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

export interface UploadedFileInfo {
  id: string;
  originalName: string;
  storedName: string;
  path: string;
  contentType: string;
  size: number;
}

export type AttachmentInfo = UploadedFileInfo;

// Team chat message, corresponds to backend TeamMessage
export interface TeamChatMessage {
  fromAgent: string;
  toAgent: string;
  content: string;
  type: "direct" | "broadcast" | "user";
  timestamp: number;
}

export interface TeamConversation {
  id: string;
  name: string;
  createdAt: number;
  updatedAt: number;
  memberSessions: Record<string, string>;
  missingSessions?: Record<string, string>;
  messageCount: number;
  active?: boolean;
}

export interface TeamConversationResult {
  conversation: TeamConversation;
  messages?: Record<string, unknown>[];
  memberSessionStatus?: Record<string, Record<string, unknown>>;
  warnings?: string[];
}

export interface SessionInfo {
  id: string;
  timestamp: string;
  turnCount: number;
  isActive: boolean;
}

// ToolPolicy: shared config for all built-in tools. cwd is NOT here —
// backend derives it from the top-level workingDir. All field names are
// camelCase to match the API contract.
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

// === Agent runtime types (discriminated union) ===

// shared runtime fields
interface AgentBase {
  id: string;
  name: string;
  state: "ready" | "waiting" | "running" | "error";
  messages: Message[];
  sessions: SessionInfo[];
  currentSessionId: string;
}

// Single Agent runtime type
export interface SingleAgent extends AgentBase {
  type: "single";
  baseDir: string;
  workingDir: string;
  modelId: string;
  systemPrompt: string;
  toolIds: string[];
  skillIds: string[];
  hookNames: string[];
  hookConfig: Record<string, unknown>;
  toolPolicy: ToolPolicy;
}

// Team runtime type
export interface Team extends AgentBase {
  type: "team";
  baseDir: string;
  workingDir: string;
  teamDescription: string;
  members: SingleAgent[];
  contacts: Record<string, Record<string, string>>;
}

// discriminated union
export type Agent = SingleAgent | Team;

// type guards
export function isSingleAgent(agent: Agent): agent is SingleAgent {
  return agent.type === "single";
}

export function isTeam(agent: Agent): agent is Team {
  return agent.type === "team";
}

// === API Payload types ===

// request body to create a Single Agent
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

// request body to create a Team (includes member config list)
export interface CreateTeamPayload {
  name: string;
  teamDescription: string;
  workingDir: string;
  members: CreateAgentPayload[];
  contacts: Record<string, Record<string, string>>;
}

// update payload (all fields optional)
export type UpdateAgentPayload = Partial<CreateAgentPayload>;
export type UpdateTeamPayload = Partial<CreateTeamPayload> & {
  deleteRemovedMemberIds?: string[];
};

// === Hook descriptor (returned by GET /api/hooks) ===

export type HookFieldType = "string" | "text" | "number" | "float" | "boolean" | "modelId";

export interface HookFieldSchema {
  key: string;
  type: HookFieldType;
  label: string;
  default: unknown;
  description: string;
}

export interface HookSection {
  title: string;
  fields: HookFieldSchema[];
}

export interface HookDescriptor {
  name: string;
  displayName: string;
  description: string;
  defaultEnabled: boolean;
  fieldSections: HookSection[];
}

export interface HookListResponse {
  hooks: HookDescriptor[];
  sharedSections: HookSection[];
}

export interface FileNode {
  name: string;
  path: string;
  type: "file" | "directory";
  children?: FileNode[];
  size?: number;
  extension?: string;
  modifiedAt?: number;
}

export interface TimerConfig {
  name: string;
  type: "interval" | "at";
  seconds: number;
  time: string;
  hint: string;
  enabled: boolean;
  running?: boolean;
}

export type SettingsTab = "models" | "skills" | "mcps" | "prompts";

// === Global Session Manager types ===

// global session index (corresponds to SessionIndex returned by GET /api/sessions)
export interface GlobalSessionIndex {
  session_id: string;
  agent_id: string;
  agent_name: string;
  timestamp: string;
  turn_count: number;
  is_active: boolean;
  parent_session_id: string;
  fork_turn_index: number;
}

// session detail (corresponds to GET /api/sessions/{id})
export interface SessionDetail {
  sessionId: string;
  agentId: string;
  agentName: string;
  timestamp: string;
  turnCount: number;
  parentSessionId: string;
  forkTurnIndex: number;
  turns: TurnInfo[];
}

// Turn info
export interface TurnInfo {
  index: number;
  userMessage: string;
  tokenCount: number;
  everUsedTools: string[];
  startTimestamp: number;
  endTimestamp: number;
  messageCount: number;
}

// === Template types for import/export ===

// Human-readable agent template (no UUIDs — just names)
export interface AgentTemplate {
  type: "agent";
  name: string;
  systemPrompt: string;
  tools: string[];
  skills: string[];
  hooks: string[];
  hookConfig: Record<string, unknown>;
  toolPolicy: Record<string, unknown>;
}

// Human-readable team template (no UUIDs — just names)
export interface TeamTemplate {
  type: "team";
  name: string;
  teamDescription: string;
  members: AgentTemplate[];
  contacts: Record<string, Record<string, string>>;
}

export type Template = AgentTemplate | TeamTemplate;

// Resolved result — names mapped to IDs, with warnings for unmatched names
export interface TemplateResolveResult {
  type: "agent" | "team";
  warnings: string[];
  // Agent form data
  name: string;
  systemPrompt: string;
  toolIds: string[];
  skillIds: string[];
  hookNames: string[];
  hookConfig: Record<string, unknown>;
  toolPolicy: Record<string, unknown>;
  // Team-only fields
  teamDescription?: string;
  members?: TemplateResolveResult[];
  contacts?: Record<string, Record<string, string>>;
}
