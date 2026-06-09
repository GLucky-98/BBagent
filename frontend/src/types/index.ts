export interface Model {
  id: string;
  name: string;
  provider: "anthropic" | "openai";
  modelName: string;
  apiKey: string;
  baseUrl: string;
  maxContextTokens: number;
  maxCompletionTokens: number;
  temperature?: number;
  topP?: number;
  thinking?: boolean;
}

// Tool 同时表示内置工具和 MCP 工具（unified-id 设计）：
// - id: 唯一 template_id（UUID）。前端用作 React key 和 agent.toolIds 的存储值
// - name: builtin 为短名（如 'bash'），MCP 工具为 rawName
// - source: 工具来源 ("built_in" | "mcp" | "hook" | "team")
// - mcpServerId: 仅 MCP 工具设置，引用 MCPServerConfig.id
// - mcpServerName: 仅 UI 分组用，引用 MCPServerConfig.name（不用于路由）
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
  chunkType?: "text" | "thinking" | "tool_use" | "tool_result" | "error" | "input_event";
  toolName?: string;
  toolInput?: Record<string, unknown>;
}

// Team 聊天消息，对应后端 TeamMessage
export interface TeamChatMessage {
  fromAgent: string;
  toAgent: string;
  content: string;
  type: "direct" | "broadcast" | "user";
  timestamp: number;
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
  subAgentModel?: string;           // modelId for sub-agent
  subAgentBlockedTools?: string[];  // tool names blocked for sub-agent
}

// === Agent runtime types (discriminated union) ===

// 共有运行时字段
interface AgentBase {
  id: string;
  name: string;
  state: "ready" | "waiting" | "running" | "error";
  messages: Message[];
  sessions: SessionInfo[];
  currentSessionId: string;
}

// Single Agent 运行时类型
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

// 类型守卫
export function isSingleAgent(agent: Agent): agent is SingleAgent {
  return agent.type === "single";
}

export function isTeam(agent: Agent): agent is Team {
  return agent.type === "team";
}

// === API Payload types ===

// 创建 Single Agent 的请求体
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

// 更新 payload（所有字段可选）
export type UpdateAgentPayload = Partial<CreateAgentPayload>;
export type UpdateTeamPayload = Partial<CreateTeamPayload>;

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
  seconds: number;
  hint: string;
  enabled: boolean;
  running?: boolean;
}

export type SettingsTab = "models" | "skills" | "mcps" | "prompts";

// === Global Session Manager types ===

// 全局 session 索引（对应 GET /api/sessions 返回的 SessionIndex）
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

// Session 详情（对应 GET /api/sessions/{id}）
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

// Turn 信息
export interface TurnInfo {
  index: number;
  userMessage: string;
  tokenCount: number;
  everUsedTools: string[];
  startTimestamp: number;
  endTimestamp: number;
  messageCount: number;
}
