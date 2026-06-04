const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

async function request(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  // Models
  listModels: () => request("/models"),
  createModel: (data: unknown) => request("/models", { method: "POST", body: JSON.stringify(data) }),
  updateModel: (id: string, data: unknown) => request(`/models/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteModel: (id: string) => request(`/models/${id}`, { method: "DELETE" }),
  testModel: (id: string, prompt: string) => request(`/models/${id}/test`, { method: "POST", body: JSON.stringify({ prompt }) }),

  // Tools
  listTools: () => request("/tools"),

  // Hooks
  listHooks: () => request("/hooks"),

  // MCPs — per unified-id, paths use id (UUID).
  listMcps: () => request("/mcps"),
  createMcp: (data: unknown) => request("/mcps", { method: "POST", body: JSON.stringify(data) }),
  updateMcp: (id: string, data: unknown) => request(`/mcps/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteMcp: (id: string) => request(`/mcps/${id}`, { method: "DELETE" }),
  discoverMcp: (id: string) => request(`/mcps/${id}/discover`, { method: "POST" }),
  importMcps: (path: string) => request("/mcps/import", { method: "POST", body: JSON.stringify({ path }) }),

  // Prompts
  listPrompts: () => request("/prompts"),
  createPrompt: (data: unknown) => request("/prompts", { method: "POST", body: JSON.stringify(data) }),
  updatePrompt: (id: string, data: unknown) => request(`/prompts/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deletePrompt: (id: string) => request(`/prompts/${id}`, { method: "DELETE" }),
  importPrompts: (path: string) => request("/prompts/import", { method: "POST", body: JSON.stringify({ path }) }),

  // Skills
  listSkills: () => request("/skills"),
  importSkills: (path: string) => request("/skills/import", { method: "POST", body: JSON.stringify({ path }) }),

  // Agents — per unified-id, all paths use agent.id (UUID).
  // `getAgent` accepts id or name (server resolves both).
  listAgents: () => request("/agents"),
  getAgent: (id: string) => request(`/agents/${id}`),
  createAgent: (data: unknown) => request("/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgent: (id: string, data: unknown) => request(`/agents/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteAgent: (id: string, deleteFiles?: boolean) =>
    request(`/agents/${id}${deleteFiles ? '?delete_files=true' : ''}`, { method: "DELETE" }),
  startAgent: (id: string) => request(`/agents/${id}/start`, { method: "POST" }),
  stopAgent: (id: string) => request(`/agents/${id}/stop`, { method: "POST" }),
  getAgentState: (id: string) => request(`/agents/${id}/state`),
  listSessions: (id: string) => request(`/agents/${id}/sessions`),
  switchSession: (id: string, sessionId: string) =>
    request(`/agents/${id}/sessions/${sessionId}/switch`, { method: "POST" }),
  newSession: (id: string) => request(`/agents/${id}/sessions/new`, { method: "POST" }),
  getAgentMessages: (id: string) => request(`/agents/${id}/messages`),

  // Teams — paths use team.id.
  listTeams: () => request("/teams"),
  getTeam: (id: string) => request(`/teams/${id}`),
  createTeam: (data: unknown) => request("/teams", { method: "POST", body: JSON.stringify(data) }),
  updateTeam: (id: string, data: unknown) => request(`/teams/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteTeam: (id: string) => request(`/teams/${id}`, { method: "DELETE" }),
  startTeam: (id: string) => request(`/teams/${id}/start`, { method: "POST" }),
  stopTeam: (id: string) => request(`/teams/${id}/stop`, { method: "POST" }),

  // Files
  getFileTree: (path: string) => request(`/files/tree?path=${encodeURIComponent(path)}`),
  readFile: (path: string) => request(`/files/read?path=${encodeURIComponent(path)}`),
  writeFile: (path: string, content: string) => request("/files/write", { method: "POST", body: JSON.stringify({ path, content }) }),
  listDirs: (path: string) => request(`/files/dirs?path=${encodeURIComponent(path)}`),
  openPath: (path: string) => request("/files/open", { method: "POST", body: JSON.stringify({ path }) }),

  // UI State
  getState: () => request("/state"),
  saveState: (data: unknown) => request("/state", { method: "POST", body: JSON.stringify(data) }),
};

export function createChatWs(): WebSocket {
  const wsBase = API_BASE.replace(/^http/, "ws");
  return new WebSocket(`${wsBase}/ws/chat`);
}

export function createTeamChatWs(teamId: string): WebSocket {
  const wsBase = API_BASE.replace(/^http/, "ws");
  return new WebSocket(`${wsBase}/ws/team/${teamId}`);
}
