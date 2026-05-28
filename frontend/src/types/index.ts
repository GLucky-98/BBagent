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
  thinking?: {
    type: "enabled" | "disabled" | "adaptive";
    budgetTokens?: number;
  };
}

export interface Tool {
  id: string;
  name: string;
  description: string;
  inputSchema: {
    type: string;
    properties?: Record<
      string,
      { type: string; description?: string; default?: unknown }
    >;
    required?: string[];
  };
  isMcp: boolean;
  mcpServerName?: string;
}

export interface Skill {
  name: string;
  description: string;
  path: string;
  body: string;
  metadata: {
    license?: string;
    compatibility?: string;
    version?: string;
    allowedTools?: string[];
    metadata?: Record<string, unknown>;
  };
  source: "default" | "imported";
}

export interface MCPServer {
  name: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  isConnected: boolean;
  tools: Tool[];
  source: "default" | "imported";
}

export interface Prompt {
  id: string;
  name: string;
  description: string;
  content: string;
  source: "built-in" | "folder" | "imported";
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
}

export interface Agent {
  id: string;
  name: string;
  type: "single" | "team";
  basePath: string;
  workingDir: string;
  modelId: string;
  systemPrompt: string;
  toolNames: string[];
  skillNames: string[];
  hookEnabled: boolean;
  teamDescription?: string;
  teamMembers?: Agent[];
  contacts?: Record<string, Record<string, string>>;
  teamPrompt?: string;
  messages: Message[];
  policy: AgentPolicy;
}

export interface AgentPolicy {
  cwd: string;
  allowedDirs: string;
  bashAllowNetwork: boolean;
  bashMaxOutputLines: number;
  blockedPaths: string;
  blockedExtensions: string;
  maxReadSize: number;
  maxReadLines: number;
  maxWriteSize: number;
  writeCreateDirectories: boolean;
  bashAllowedCommands: string;
  bashBlockedCommands: string;
  bashDefaultTimeout: number;
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

export type SettingsTab = "models" | "skills" | "mcps" | "prompts";
