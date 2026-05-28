from typing import Literal
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    id: str
    name: str
    provider: Literal["anthropic", "openai"]
    modelName: str
    apiKey: str = ""
    baseUrl: str
    maxContextTokens: int
    maxCompletionTokens: int
    temperature: float = 1.0
    topP: float = 1.0
    thinking: dict | None = None


class ToolConfig(BaseModel):
    id: str
    name: str
    description: str
    inputSchema: dict
    isMcp: bool = False
    mcpServerName: str | None = None


class SkillConfig(BaseModel):
    name: str
    description: str
    path: str
    body: str = ""
    metadata: dict = Field(default_factory=dict)
    source: Literal["default", "imported"] = "default"


class MCPServerConfig(BaseModel):
    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    isConnected: bool = False
    tools: list[ToolConfig] = Field(default_factory=list)
    source: Literal["default", "imported"] = "default"


class PromptConfig(BaseModel):
    id: str
    name: str
    description: str = ""
    content: str
    source: Literal["built-in", "folder", "imported"] = "built-in"


class MessageItem(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: int


class AgentSummary(BaseModel):
    id: str
    name: str
    type: Literal["single", "team"] = "single"
    modelId: str
    state: str = "Ready"
    toolCount: int = 0
    skillCount: int = 0
    hookEnabled: bool = False


class AgentConfig(BaseModel):
    id: str
    name: str
    type: Literal["single", "team"] = "single"
    basePath: str = ""
    workingDir: str = ""
    modelId: str
    systemPrompt: str = ""
    toolNames: list[str] = Field(default_factory=list)
    skillNames: list[str] = Field(default_factory=list)
    hookEnabled: bool = False
    teamDescription: str = ""
    teamMembers: list["AgentConfig"] = Field(default_factory=list)
    contacts: dict[str, dict[str, str]] = Field(default_factory=dict)
    teamPrompt: str = ""
    messages: list[MessageItem] = Field(default_factory=list)
    policy: dict = Field(default_factory=dict)


class TeamSummary(BaseModel):
    id: str
    name: str
    agentCount: int
    teamDescription: str = ""


class TeamConfig(BaseModel):
    id: str
    name: str
    teamDescription: str = ""
    agentNames: list[str] = Field(default_factory=list)
    contacts: dict[str, list[str]] = Field(default_factory=dict)


class FileNode(BaseModel):
    name: str
    path: str
    type: Literal["file", "directory"]
    children: list["FileNode"] = Field(default_factory=list)
    size: int | None = None
    extension: str | None = None
    modifiedAt: int | None = None


class UIState(BaseModel):
    currentTab: Literal["agent", "team"] = "agent"
    currentAgentId: str | None = None
    currentTeamId: str | None = None
    settingsOpen: bool = False
    settingsTab: str = "models"
    workingDirPath: str = ""


class ChatMessage(BaseModel):
    type: Literal["user_message", "system_event"]
    content: str


class ModelTestRequest(BaseModel):
    prompt: str = "Hello, respond with a short greeting."
