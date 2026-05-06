export interface Model {
  id: string;
  name: string;
  type: "chat" | "embedding";
  provider: "anthropic" | "openai";
  baseUrl: string;
  apiKey: string;
  modelName: string;
}

export interface Tool {
  id: string;
  name: string;
  description: string;
  inputSchema: {
    type: string;
    properties?: Record<string, {
      type: string;
      description?: string;
      default?: unknown;
    }>;
    required?: string[];
  };
  isMcp: boolean;
}

export interface Skill {
  id: string;
  name: string;
  description: string;
  path: string;
  metadata: {
    license?: string;
    compatibility?: string;
    version?: string;
    allowedTools?: string[];
    metadata?: Record<string, unknown>;
  };
  body: string;
}

export interface MCPServer {
  id: string;
  name: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  isConnected: boolean;
  tools: Tool[];
}

export interface Prompt {
  id: string;
  name: string;
  description: string;
  content: string;
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
  primaryModel: Model;
  secondaryModel?: Model;
  systemPrompt: string;
  tools: Tool[];
  skills: Skill[];
  contextHook?: string;
  teamMembers?: Agent[];
  teamPrompt?: string;
  visibleMembers?: string[];
  messages: Message[];
}

export type NavItem =
  | "agents"
  | "models"
  | "tools"
  | "skills"
  | "mcps"
  | "prompts";

export interface CreateAgentForm {
  name: string;
  basePath: string;
  primaryModelId: string;
  secondaryModelId?: string;
  systemPrompt: string;
  toolIds: string[];
  skillIds: string[];
  contextHook?: string;
}

export interface CreateTeamForm {
  name: string;
  memberIds: string[];
  teamPrompt: string;
  visibleMembers: Record<string, string[]>;
}
