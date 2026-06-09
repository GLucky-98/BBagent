import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const MIME_MAP: Record<string, string> = {
  ".ts": "text/typescript",
  ".tsx": "text/typescript",
  ".js": "text/javascript",
  ".jsx": "text/javascript",
  ".py": "text/x-python",
  ".json": "application/json",
  ".yaml": "text/yaml",
  ".yml": "text/yaml",
  ".md": "text/markdown",
  ".css": "text/css",
  ".html": "text/html",
  ".txt": "text/plain",
  ".env": "text/plain",
  ".gitignore": "text/plain",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".pdf": "application/pdf",
};

export function getMimeType(fileName: string): string {
  const ext = fileName.substring(fileName.lastIndexOf(".")).toLowerCase();
  return MIME_MAP[ext] ?? "text/plain";
}

// === Template helpers ===

import type {
  SingleAgent,
  Model,
  Tool,
  Skill,
  AgentTemplate,
  Template,
  TemplateResolveResult,
} from "../types";

/**
 * Export a SingleAgent to a human-readable AgentTemplate (no UUIDs).
 */
export function agentToTemplate(
  agent: SingleAgent,
  models: Model[],
  tools: Tool[],
  skills: Skill[],
): AgentTemplate {
  const modelName = models.find((m) => m.id === agent.modelId)?.name ?? agent.modelId;

  const toolNames = (agent.toolIds ?? [])
    .map((tid) => tools.find((t) => t.id === tid)?.name ?? tid);

  const skillNames = (agent.skillIds ?? [])
    .map((sid) => skills.find((s) => s.id === sid)?.name ?? sid);

  // Resolve model references in hookConfig
  const hookConfig: Record<string, unknown> = {};
  if (agent.hookConfig) {
    for (const [key, val] of Object.entries(agent.hookConfig)) {
      if (key === "submodelId" && typeof val === "string" && val) {
        hookConfig[key] = models.find((m) => m.id === val)?.name ?? val;
      } else {
        hookConfig[key] = val;
      }
    }
  }

  // Resolve model references in toolPolicy
  const toolPolicy: Record<string, unknown> = {};
  if (agent.toolPolicy) {
    for (const [key, val] of Object.entries(agent.toolPolicy)) {
      if (key === "subAgentModel" && typeof val === "string" && val) {
        toolPolicy[key] = models.find((m) => m.id === val)?.name ?? val;
      } else if (key === "subAgentBlockedTools" && Array.isArray(val)) {
        toolPolicy[key] = val.map((tn: string) =>
          tools.find((t) => t.id === tn)?.name ?? tn
        );
      } else {
        toolPolicy[key] = val;
      }
    }
  }

  return {
    type: "agent",
    name: agent.name,
    systemPrompt: agent.systemPrompt ?? "",
    tools: toolNames,
    skills: skillNames,
    hooks: agent.hookNames ?? [],
    hookConfig,
    toolPolicy,
    // Note: modelName is intentionally not included — templates don't carry model info
    _modelName: modelName,
  } as AgentTemplate & { _modelName: string };
}

/**
 * Resolve a Template (names → IDs) using the current store data.
 * Returns a TemplateResolveResult with warnings for unmatched names.
 */
export function resolveTemplate(
  template: Template,
  models: Model[],
  tools: Tool[],
  skills: Skill[],
): TemplateResolveResult {
  const warnings: string[] = [];

  function resolveAgent(tpl: AgentTemplate): TemplateResolveResult {
    const toolIds: string[] = [];
    for (const tname of tpl.tools) {
      const tool = tools.find((t) => t.name === tname);
      if (tool) {
        toolIds.push(tool.id);
      } else {
        warnings.push(`Tool "${tname}" not found`);
      }
    }

    const skillIds: string[] = [];
    for (const sname of tpl.skills) {
      const skill = skills.find((s) => s.name === sname);
      if (skill) {
        skillIds.push(skill.id);
      } else {
        warnings.push(`Skill "${sname}" not found`);
      }
    }

    // Resolve model references in hookConfig
    const hookConfig: Record<string, unknown> = {};
    if (tpl.hookConfig) {
      for (const [key, val] of Object.entries(tpl.hookConfig)) {
        if (key === "submodelId" && typeof val === "string" && val) {
          const model = models.find((m) => m.name === val);
          hookConfig[key] = model ? model.id : val;
          if (!model) warnings.push(`Hook submodel "${val}" not found`);
        } else {
          hookConfig[key] = val;
        }
      }
    }

    // Resolve model references in toolPolicy
    const toolPolicy: Record<string, unknown> = {};
    if (tpl.toolPolicy) {
      for (const [key, val] of Object.entries(tpl.toolPolicy)) {
        if (key === "subAgentModel" && typeof val === "string" && val) {
          const model = models.find((m) => m.name === val);
          toolPolicy[key] = model ? model.id : val;
          if (!model) warnings.push(`Sub-agent model "${val}" not found`);
        } else if (key === "subAgentBlockedTools" && Array.isArray(val)) {
          const resolved: string[] = [];
          for (const tn of val) {
            const tool = tools.find((t) => t.name === tn);
            if (tool) {
              resolved.push(tool.id);
            } else {
              warnings.push(`Blocked tool "${tn}" not found`);
            }
          }
          toolPolicy[key] = resolved;
        } else {
          toolPolicy[key] = val;
        }
      }
    }

    return {
      type: "agent",
      warnings: [],
      name: tpl.name,
      systemPrompt: tpl.systemPrompt,
      toolIds,
      skillIds,
      hookNames: tpl.hooks,
      hookConfig,
      toolPolicy,
    };
  }

  if (template.type === "agent") {
    const res = resolveAgent(template);
    res.warnings = warnings;
    return res;
  }

  // Team
  const memberResults = template.members.map((m) => resolveAgent(m));
  const allWarnings = [...warnings];
  for (const mr of memberResults) {
    allWarnings.push(...mr.warnings);
  }

  return {
    type: "team",
    warnings: allWarnings,
    name: template.name,
    systemPrompt: "",
    toolIds: [],
    skillIds: [],
    hookNames: [],
    hookConfig: {},
    toolPolicy: {},
    teamDescription: template.teamDescription,
    members: memberResults,
    contacts: template.contacts,
  };
}

/**
 * Detect template type from raw JSON object.
 * Returns "agent", "team", or null (invalid).
 */
export function detectTemplateType(obj: unknown): "agent" | "team" | null {
  if (!obj || typeof obj !== "object") return null;
  const o = obj as Record<string, unknown>;
  if (o.type === "agent" && typeof o.name === "string") return "agent";
  if (o.type === "team" && typeof o.name === "string" && Array.isArray(o.members)) return "team";
  // Guess by field presence
  if (Array.isArray(o.members)) return "team";
  if (typeof o.name === "string" && typeof o.systemPrompt === "string") return "agent";
  return null;
}

/**
 * Trigger browser download of a JSON file.
 */
export function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
