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

  // MCPs
  listMcps: () => request("/mcps"),
  createMcp: (data: unknown) => request("/mcps", { method: "POST", body: JSON.stringify(data) }),
  updateMcp: (name: string, data: unknown) => request(`/mcps/${name}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteMcp: (name: string) => request(`/mcps/${name}`, { method: "DELETE" }),
  activateMcp: (name: string) => request(`/mcps/${name}/activate`, { method: "POST" }),
  deactivateMcp: (name: string) => request(`/mcps/${name}/deactivate`, { method: "POST" }),
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

  // Agents
  listAgents: () => request("/agents"),
  getAgent: (name: string) => request(`/agents/${name}`),
  createAgent: (data: unknown) => request("/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgent: (name: string, data: unknown) => request(`/agents/${name}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteAgent: (name: string, deleteFiles?: boolean) =>
    request(`/agents/${name}${deleteFiles ? '?delete_files=true' : ''}`, { method: "DELETE" }),
  newSession: (name: string) => request(`/agents/${name}/new_session`, { method: "POST" }),

  // Teams
  listTeams: () => request("/teams"),
  getTeam: (name: string) => request(`/teams/${name}`),
  createTeam: (data: unknown) => request("/teams", { method: "POST", body: JSON.stringify(data) }),
  updateTeam: (name: string, data: unknown) => request(`/teams/${name}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteTeam: (name: string) => request(`/teams/${name}`, { method: "DELETE" }),
  startTeam: (name: string) => request(`/teams/${name}/start`, { method: "POST" }),
  stopTeam: (name: string) => request(`/teams/${name}/stop`, { method: "POST" }),

  // Files
  getFileTree: (path: string) => request(`/files/tree?path=${encodeURIComponent(path)}`),
  readFile: (path: string) => request(`/files/read?path=${encodeURIComponent(path)}`),
  writeFile: (path: string, content: string) => request("/files/write", { method: "POST", body: JSON.stringify({ path, content }) }),
  listDirs: (path: string) => request(`/files/dirs?path=${encodeURIComponent(path)}`),

  // UI State
  getState: () => request("/state"),
  saveState: (data: unknown) => request("/state", { method: "POST", body: JSON.stringify(data) }),
};

// WebSocket
export function createChatWs(agentName: string): WebSocket {
  const wsBase = API_BASE.replace(/^http/, "ws");
  return new WebSocket(`${wsBase}/ws/chat/${agentName}`);
}
