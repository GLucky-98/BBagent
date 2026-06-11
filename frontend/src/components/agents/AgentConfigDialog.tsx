import { useState, useEffect } from "react";
import { X, Bot, Users, FileText, Settings, Copy, Download, FileJson, AlertCircle } from "lucide-react";
import { useAppStore } from "../../store";
import { cn, agentToTemplate, resolveTemplate, detectTemplateType } from "../../lib/utils";
import { GroupedPromptPicker } from "../GroupedPromptPicker";
import { TemplatePicker } from "../TemplatePicker";
import { ConfirmDialog } from "../ConfirmDialog";
import type {
  SingleAgent,
  HookDescriptor,
  HookFieldSchema,
  HookSection,
  ToolPolicy,
  CreateAgentPayload,
  CreateTeamPayload,
  Template,
} from "../../types";
import { isTeam, isSingleAgent } from "../../types";
import { FolderPicker } from "../FolderPicker";
import { api } from "../../lib/api";

// === Field defaults ===

const DEFAULT_TOOL_POLICY: ToolPolicy = {
  maxReadSize: 30000,
  bashMaxOutputSize: 50000,
  bashDefaultTimeout: 60,
};

const DEFAULT_HOOK_NAMES: string[] = ["built_in.compress"];

// === HookConfigDialog: dynamic form driven by hooksDescriptor ===

interface HookConfigDialogProps {
  open: boolean;
  onClose: () => void;
  hookConfig: Record<string, unknown>;
  hooks: HookDescriptor[];
  sharedSections: HookSection[];
  onSave: (cfg: Record<string, unknown>) => void;
}

function HookConfigDialog({
  open,
  onClose,
  hookConfig,
  hooks,
  sharedSections,
  onSave,
}: HookConfigDialogProps) {
  const models = useAppStore((s) => s.models);
  const prompts = useAppStore((s) => s.prompts);
  const [draft, setDraft] = useState<Record<string, unknown>>(hookConfig);

  useEffect(() => {
    setDraft(hookConfig);
  }, [hookConfig, open]);

  if (!open) return null;

  const handleField = (key: string, value: unknown) =>
    setDraft((d) => ({ ...d, [key]: value }));

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-(--color-background) rounded-2xl shadow-[-8px_8px_24px_rgba(0,0,0,0.08)] overflow-hidden flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-(--color-border) shrink-0">
          <h3 className="text-base font-semibold">Hook Configuration</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-(--color-secondary)">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {sharedSections.map((sec) => (
            <HookSectionForm
              key={`shared-${sec.title}`}
              section={sec}
              draft={draft}
              models={models}
              prompts={prompts}
              onField={handleField}
            />
          ))}

          {hooks.map((hook) => (
            <div key={hook.name}>
              <div className="mb-3">
                <h4 className="text-sm font-semibold text-(--color-foreground)">{hook.displayName}</h4>
                <p className="text-xs text-(--color-muted-foreground) mt-0.5">{hook.description}</p>
              </div>
              {hook.fieldSections.map((sec) => (
                <HookSectionForm
                  key={`${hook.name}-${sec.title}`}
                  section={sec}
                  draft={draft}
                  models={models}
                  prompts={prompts}
                  onField={handleField}
                />
              ))}
            </div>
          ))}
        </div>

        <div className="flex justify-end gap-2 px-6 py-4 border-t border-(--color-border) shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-(--color-border) hover:bg-(--color-secondary) text-sm"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              onSave(draft);
              onClose();
            }}
            className="px-4 py-2 rounded-lg border border-(--color-primary) bg-(--color-primary) text-(--color-primary-foreground) text-sm hover:opacity-90"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

function HookSectionForm({
  section,
  draft,
  models,
  prompts,
  onField,
}: {
  section: HookSection;
  draft: Record<string, unknown>;
  models: { id: string; name: string; provider: string }[];
  prompts: { id: string; name: string; content: string; description?: string }[];
  onField: (key: string, value: unknown) => void;
}) {
  return (
    <div>
      <h4 className="text-sm font-medium text-(--color-foreground) mb-2">{section.title}</h4>
      <div className="space-y-3 pl-1">
        {section.fields.map((f) => (
          <HookFieldInput
            key={f.key}
            field={f}
            value={draft[f.key]}
            models={models}
            prompts={prompts}
            onChange={(v) => onField(f.key, v)}
          />
        ))}
      </div>
    </div>
  );
}

function HookFieldInput({
  field,
  value,
  models,
  prompts,
  onChange,
}: {
  field: HookFieldSchema;
  value: unknown;
  models: { id: string; name: string; provider: string }[];
  prompts: { id: string; name: string; content: string; description?: string }[];
  onChange: (v: unknown) => void;
}) {
  const [showPromptPicker, setShowPromptPicker] = useState(false);
  const placeholderText = field.default != null && field.default !== "" ? String(field.default) : undefined;

  const labelEl = (
    <label className="block text-xs font-medium mb-1">
      {field.label || field.key}
      {field.description && (
        <span className="block text-[10px] text-(--color-muted-foreground) font-normal mt-0.5">
          {field.description}
        </span>
      )}
    </label>
  );

  if (field.type === "modelId") {
    return (
      <div>
        {labelEl}
        <select
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-2 py-1.5 text-xs rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring)"
        >
          <option value="">(default — use agent's main model)</option>
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name} ({m.provider})
            </option>
          ))}
        </select>
      </div>
    );
  }

  if (field.type === "text") {
    return (
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs font-medium">
            {field.label || field.key}
            {field.description && (
              <span className="block text-[10px] text-(--color-muted-foreground) font-normal mt-0.5">
                {field.description}
              </span>
            )}
          </label>
          <button
            type="button"
            onClick={() => { setShowPromptPicker(!showPromptPicker); }}
            className="flex items-center gap-1 text-xs text-(--color-primary) hover:underline"
          >
            <FileText className="w-3 h-3" />
            {showPromptPicker ? "Hide Prompt Library" : "From Prompt Library"}
          </button>
        </div>
        {showPromptPicker && (
          <div className="mb-2">
            <GroupedPromptPicker
              prompts={prompts as any}
              onSelect={(p) => { onChange(p.content); setShowPromptPicker(false); }}
            />
          </div>
        )}
        <textarea
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholderText}
          rows={3}
          className="w-full px-2 py-1.5 text-xs rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring) resize-y font-mono"
        />
      </div>
    );
  }

  if (field.type === "string") {
    return (
      <div>
        {labelEl}
        <input
          type="text"
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholderText}
          className="w-full px-2 py-1.5 text-xs rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring)"
        />
      </div>
    );
  }

  if (field.type === "number" || field.type === "float") {
    const num = value as number | undefined;
    return (
      <div>
        {labelEl}
        <input
          type="number"
          step={field.type === "float" ? "0.01" : "1"}
          value={num ?? ""}
          placeholder={placeholderText}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
          className="w-full px-2 py-1.5 text-xs rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring)"
        />
      </div>
    );
  }

  if (field.type === "boolean") {
    return (
      <div>
        <label className="flex items-center gap-2 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => onChange(e.target.checked)}
            className="rounded"
          />
          <span>{field.label || field.key}</span>
        </label>
      </div>
    );
  }

  return null;
}

// === ToolPolicyDialog: simple shared form for all built-in tools ===

interface ToolPolicyDialogProps {
  open: boolean;
  onClose: () => void;
  toolPolicy: ToolPolicy;
  onSave: (tp: ToolPolicy) => void;
  models: { id: string; name: string; provider: string }[];
  builtinTools: { id: string; name: string }[];
  hasSubAgent: boolean;
}

function ToolPolicyDialog({ open, onClose, toolPolicy, onSave, models, builtinTools, hasSubAgent }: ToolPolicyDialogProps) {
  const [draft, setDraft] = useState<ToolPolicy>(toolPolicy);

  useEffect(() => {
    setDraft(toolPolicy);
  }, [toolPolicy, open]);

  if (!open) return null;

  const blockedTools = draft.subAgentBlockedTools ?? [];

  const toggleBlockedTool = (toolName: string) => {
    const current = blockedTools;
    const next = current.includes(toolName)
      ? current.filter((t) => t !== toolName)
      : [...current, toolName];
    setDraft({ ...draft, subAgentBlockedTools: next.length > 0 ? next : undefined });
  };

  // Filter out sub_agent from the list of tools that can be blocked
  const blockableTools = builtinTools.filter((t) => t.name !== "sub_agent");

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-(--color-background) rounded-2xl shadow-[-8px_8px_24px_rgba(0,0,0,0.08)] overflow-hidden flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-(--color-border) shrink-0">
          <h3 className="text-base font-semibold">Tool Policy</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-(--color-secondary)">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          <p className="text-xs text-(--color-muted-foreground)">
            Limits shared by all built-in tools. cwd is set via Working Directory at the top level.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <NumField label="Max Read Size (bytes)" value={draft.maxReadSize}
              onChange={(v) => setDraft({ ...draft, maxReadSize: v })} />
            <NumField label="Bash Max Output Size (bytes)" value={draft.bashMaxOutputSize}
              onChange={(v) => setDraft({ ...draft, bashMaxOutputSize: v })} />
            <NumField label="Bash Timeout (seconds)" value={draft.bashDefaultTimeout}
              onChange={(v) => setDraft({ ...draft, bashDefaultTimeout: v })} />
          </div>

          {hasSubAgent && (
            <>
              <div className="border-t border-(--color-border) pt-4">
                <h4 className="text-sm font-medium mb-3">Sub-Agent Configuration</h4>
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-medium mb-1">Sub-Agent Model</label>
                    <select
                      value={draft.subAgentModel ?? ""}
                      onChange={(e) => setDraft({ ...draft, subAgentModel: e.target.value || undefined })}
                      className="w-full px-2 py-1.5 text-xs rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring)"
                    >
                      <option value="">(use agent's main model)</option>
                      {models.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name} ({m.provider})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-medium mb-2">Blocked Tools for Sub-Agent</label>
                    <div className="grid grid-cols-2 gap-2">
                      {blockableTools.map((tool) => {
                        const isBlocked = blockedTools.includes(tool.name);
                        return (
                          <button
                            key={tool.id}
                            onClick={() => toggleBlockedTool(tool.name)}
                            className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-colors ${
                              isBlocked
                                ? "border-red-300 bg-red-50 text-red-700"
                                : "border-(--color-border) bg-white hover:bg-(--color-secondary)"
                            }`}
                          >
                            <span className={`w-4 h-4 flex items-center justify-center rounded ${
                              isBlocked ? "bg-red-500 text-white" : "border border-(--color-border)"
                            }`}>
                              {isBlocked && "✕"}
                            </span>
                            {tool.name}
                          </button>
                        );
                      })}
                    </div>
                    <p className="text-[10px] text-(--color-muted-foreground) mt-1">
                      Checked tools will be blocked for sub-agents
                    </p>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        <div className="flex justify-end gap-2 px-6 py-4 border-t border-(--color-border) shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-(--color-border) hover:bg-(--color-secondary) text-sm"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              onSave(draft);
              onClose();
            }}
            className="px-4 py-2 rounded-lg border border-(--color-primary) bg-(--color-primary) text-(--color-primary-foreground) text-sm hover:opacity-90"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

function NumField({ label, value, onChange }: { label: string; value: number | undefined; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="block text-xs font-medium mb-1">{label}</label>
      <input
        type="number"
        value={value ?? ""}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full px-2 py-1.5 text-xs rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring)"
      />
    </div>
  );
}

// === TypeSelection: pick between Single Agent and Team ===

function TypeSelection({ onSelect, onTemplate }: { onSelect: (t: "agent" | "team") => void; onTemplate: () => void }) {
  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold mb-1">Create New Agent</h2>
      <p className="text-sm text-(--color-muted-foreground) mb-6">Choose the type of agent to create</p>
      <div className="grid grid-cols-3 gap-4">
        <button onClick={() => onSelect("agent")}
          className="p-6 rounded-xl border-2 border-(--color-border) hover:border-(--color-primary) hover:bg-(--color-primary)/5 transition-all flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-(--color-primary)/10 flex items-center justify-center"><Bot size={24} className="text-(--color-primary)" /></div>
          <div className="text-center"><p className="font-medium">Single Agent</p><p className="text-xs text-(--color-muted-foreground) mt-1">Standalone agent</p></div>
        </button>
        <button onClick={() => onSelect("team")}
          className="p-6 rounded-xl border-2 border-(--color-border) hover:border-(--color-primary) hover:bg-(--color-primary)/5 transition-all flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-(--color-primary)/10 flex items-center justify-center"><Users size={24} className="text-(--color-primary)" /></div>
          <div className="text-center"><p className="font-medium">Agent Team</p><p className="text-xs text-(--color-muted-foreground) mt-1">Team of agents</p></div>
        </button>
        <button onClick={onTemplate}
          className="p-6 rounded-xl border-2 border-(--color-border) hover:border-(--color-primary) hover:bg-(--color-primary)/5 transition-all flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-(--color-primary)/10 flex items-center justify-center"><FileJson size={24} className="text-(--color-primary)" /></div>
          <div className="text-center"><p className="font-medium">From Template</p><p className="text-xs text-(--color-muted-foreground) mt-1">Import a JSON template</p></div>
        </button>
      </div>
    </div>
  );
}

// === SingleAgentForm: the per-agent configuration panel ===

export interface SingleAgentFormData {
  id?: string;
  name: string;
  modelId: string;
  systemPrompt: string;
  workingDir: string;
  toolIds: string[];
  skillIds: string[];
  hookNames: string[];
  toolPolicy: ToolPolicy;
  hookConfig: Record<string, unknown>;
}

function SingleAgentForm({
  initialData,
  onSave,
  saving,
  saveError,
  defaultWorkingDir,
  onExport,
}: {
  initialData?: Partial<SingleAgentFormData>;
  onSave: (data: SingleAgentFormData) => void | Promise<void>;
  saving?: boolean;
  saveError?: string | null;
  /** Pre-fill workingDir in create mode (e.g. from team's workingDir) */
  defaultWorkingDir?: string;
  onExport?: () => void;
}) {
  const models = useAppStore((s) => s.models);
  const tools = useAppStore((s) => s.tools);
  const skills = useAppStore((s) => s.skills);
  const prompts = useAppStore((s) => s.prompts);
  const hooksDescriptor = useAppStore((s) => s.hooksDescriptor);
  const agents = useAppStore((s) => s.agents);
  const [showPromptPicker, setShowPromptPicker] = useState(false);
  const [copyFromOpen, setCopyFromOpen] = useState(false);

  const [form, setForm] = useState({
    name: initialData?.name ?? "",
    modelId: initialData?.modelId ?? models[0]?.id ?? "",
    systemPrompt: initialData?.systemPrompt ?? "",
    workingDir: initialData?.workingDir ?? defaultWorkingDir ?? "",
    toolIds: initialData?.toolIds ?? [] as string[],
    skillIds: initialData?.skillIds ?? [] as string[],
    hookNames: initialData?.hookNames ?? DEFAULT_HOOK_NAMES,
  });
  const [toolPolicy, setToolPolicy] = useState<ToolPolicy>(
    initialData?.toolPolicy ?? DEFAULT_TOOL_POLICY
  );
  const [hookConfig, setHookConfig] = useState<Record<string, unknown>>(
    initialData?.hookConfig ?? {}
  );

  const [toolPolicyOpen, setToolPolicyOpen] = useState(false);
  const [hookConfigOpen, setHookConfigOpen] = useState(false);

  const builtInTools = tools.filter((t) => !t.mcpServerName);
  const mcpToolsByServer = tools.filter((t) => !!t.mcpServerName).reduce<Record<string, typeof tools>>((acc, t) => {
    const key = t.mcpServerName ?? "Other";
    (acc[key] ??= []).push(t);
    return acc;
  }, {});

  const handleToggleHook = (name: string) => {
    setForm((f) => ({
      ...f,
      hookNames: f.hookNames.includes(name)
        ? f.hookNames.filter((n) => n !== name)
        : [...f.hookNames, name],
    }));
  };

  const handleCopyFrom = (agentId: string) => {
    const agent = agents.find((a) => a.id === agentId);
    if (agent && isSingleAgent(agent)) {
      const data = agentToFormData(agent);
      setForm({
        name: data.name + " (copy)",
        modelId: data.modelId,
        systemPrompt: data.systemPrompt,
        workingDir: data.workingDir,
        toolIds: data.toolIds,
        skillIds: data.skillIds,
        hookNames: data.hookNames,
      });
      setToolPolicy(data.toolPolicy);
      setHookConfig(data.hookConfig);
      setCopyFromOpen(false);
    }
  };

  const singleAgents = agents.filter(isSingleAgent);

  return (
    <div className="flex flex-col p-8 h-[85vh] overflow-hidden">
      <div className="shrink-0 flex items-start justify-between mb-4 pr-10">
          <div>
            <h2 className="text-lg font-semibold mb-1">{initialData ? "Edit Agent" : "Configure Agent"}</h2>
            <p className="text-sm text-(--color-muted-foreground)">{initialData ? "Update agent configuration" : "Fill in the agent configuration details"}</p>
            {saveError && <p className="text-sm text-red-500 mt-1">{saveError}</p>}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {onExport && initialData && (
              <button
                onClick={onExport}
                className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg border border-(--color-border) hover:bg-(--color-secondary) text-sm transition-colors"
                title="Export as template"
              >
                <Download size={16} />
                Export
              </button>
            )}
            {!initialData && singleAgents.length > 0 && (
              <div className="relative">
                <button
                  onClick={() => setCopyFromOpen(!copyFromOpen)}
                  className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg border border-(--color-border) hover:bg-(--color-secondary) text-sm transition-colors"
                >
                  <Copy className="w-4 h-4" />
                  Copy From
                </button>
                {copyFromOpen && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setCopyFromOpen(false)} />
                    <div className="absolute right-0 top-full mt-1 z-20 w-56 bg-white rounded-lg border border-(--color-border) shadow-lg max-h-60 overflow-y-auto">
                      {singleAgents.map((a) => (
                        <button
                          key={a.id}
                          onClick={() => handleCopyFrom(a.id)}
                          className="w-full text-left px-3 py-2 text-sm hover:bg-(--color-secondary) truncate"
                        >
                          {a.name}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
            <button
              onClick={() => onSave({ ...form, toolPolicy, hookConfig })}
              disabled={!form.modelId || saving}
              className="px-8 py-2.5 rounded-lg border border-(--color-primary) bg-(--color-primary) text-(--color-primary-foreground) text-sm hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
            >
              {saving ? "Saving..." : initialData ? "Save Changes" : "Create Agent"}
            </button>
          </div>
      </div>

      <div className="grid grid-cols-2 gap-8 flex-1 min-h-0">
        {/* === LEFT COLUMN: Basic info + Skills === */}
        <div className="space-y-4 overflow-y-auto pr-4">
          <div>
            <label className="block text-sm font-medium mb-1.5">Name <span className="text-red-500">*</span></label>
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="My Agent (leave empty for auto-generated)"
              disabled={!!initialData}
              className="w-full px-3 py-2 rounded-lg border border-(--color-border) bg-white focus:outline-none focus:ring-2 focus:ring-(--color-ring) disabled:opacity-50 disabled:cursor-not-allowed" />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">Working Directory</label>
            <p className="text-xs text-(--color-muted-foreground) mb-1.5">
              Maps to <code className="font-mono">toolPolicy.cwd</code> on the backend. Leave empty to fall back to the agent's base dir.
            </p>
            <FolderPicker
              value={form.workingDir}
              onChange={(path) => setForm({ ...form, workingDir: path })}
              placeholder="/workspace/agent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">Model <span className="text-red-500">*</span></label>
            <select value={form.modelId} onChange={(e) => setForm({ ...form, modelId: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-(--color-border) bg-white focus:outline-none focus:ring-2 focus:ring-(--color-ring)">
              <option value="">Select a model</option>
              {models.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.provider})</option>)}
            </select>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-sm font-medium">System Prompt</label>
              <button onClick={() => { setShowPromptPicker(!showPromptPicker); }}
                className="flex items-center gap-1 text-xs text-(--color-primary) hover:underline">
                <FileText className="w-3 h-3" />
                {showPromptPicker ? "Hide Prompt Library" : "From Prompt Library"}
              </button>
            </div>
            {showPromptPicker && (
              <div className="mb-2">
                <GroupedPromptPicker
                  prompts={prompts}
                  onSelect={(p) => { setForm({ ...form, systemPrompt: p.content }); setShowPromptPicker(false); }}
                />
              </div>
            )}
            <textarea value={form.systemPrompt} onChange={(e) => setForm({ ...form, systemPrompt: e.target.value })}
              placeholder="You are a helpful assistant..." rows={4}
              className="w-full px-3 py-2 rounded-lg border border-(--color-border) bg-white focus:outline-none focus:ring-2 focus:ring-(--color-ring) resize-none" />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">Skills</label>
            <div className="border border-(--color-border) rounded-lg max-h-[150px] overflow-y-auto p-3 space-y-1">
              {skills.map((s) => (
                <label key={s.id || s.name} className="flex items-center justify-between text-sm cursor-pointer">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="truncate">{s.name}</span>
                  </div>
                  <input type="checkbox" checked={form.skillIds.includes(s.id || s.name)}
                    onChange={(e) => setForm({ ...form, skillIds: e.target.checked ? [...form.skillIds, s.id || s.name] : form.skillIds.filter((n) => n !== (s.id || s.name)) })}
                    className="rounded shrink-0 ml-2" />
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* === RIGHT COLUMN: Tools + Built-in Hooks === */}
        <div className="flex flex-col gap-4 overflow-y-auto pr-4">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-sm font-medium">Tools</label>
              <button
                onClick={() => setToolPolicyOpen(true)}
                className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground)"
                title="Tool policy"
              >
                <Settings className="w-4 h-4" />
              </button>
            </div>
            <div className="border border-(--color-border) rounded-lg divide-y divide-(--color-border) max-h-[250px] overflow-y-auto">
              <div className="px-3 py-2 bg-(--color-muted)/20 text-xs font-medium text-(--color-muted-foreground) flex items-center justify-between">
                <span>Built-in Tools</span>
                <input
                  type="checkbox"
                  checked={builtInTools.length > 0 && builtInTools.every((t) => form.toolIds.includes(t.id))}
                  ref={(el) => { if (el) el.indeterminate = builtInTools.some((t) => form.toolIds.includes(t.id)) && !builtInTools.every((t) => form.toolIds.includes(t.id)); }}
                  onChange={(e) => {
                    const allIds = builtInTools.map((t) => t.id);
                    if (e.target.checked) {
                      setForm({ ...form, toolIds: [...new Set([...form.toolIds, ...allIds])] });
                    } else {
                      setForm({ ...form, toolIds: form.toolIds.filter((id) => !allIds.includes(id)) });
                    }
                  }}
                  className="rounded"
                  title="Select all built-in tools"
                />
              </div>
              <div className="px-3 py-2 space-y-1">
                {builtInTools.map((t) => (
                  <label key={t.id} className="flex items-center justify-between text-sm cursor-pointer">
                    <span className="truncate">{t.name}</span>
                    <input type="checkbox" checked={form.toolIds.includes(t.id)}
                      onChange={(e) => setForm({ ...form, toolIds: e.target.checked ? [...form.toolIds, t.id] : form.toolIds.filter((n) => n !== t.id) })}
                      className="rounded shrink-0 ml-2" />
                  </label>
                ))}
              </div>
              {Object.entries(mcpToolsByServer).map(([serverName, serverTools]) => (
                <div key={serverName}>
                  <div className="px-3 py-2 bg-(--color-muted)/20 text-xs font-medium text-(--color-muted-foreground) flex items-center justify-between">
                    <span>MCP: {serverName}</span>
                    <input
                      type="checkbox"
                      checked={serverTools.every((t) => form.toolIds.includes(t.id))}
                      ref={(el) => { if (el) el.indeterminate = serverTools.some((t) => form.toolIds.includes(t.id)) && !serverTools.every((t) => form.toolIds.includes(t.id)); }}
                      onChange={(e) => {
                        const allIds = serverTools.map((t) => t.id);
                        if (e.target.checked) {
                          setForm({ ...form, toolIds: [...new Set([...form.toolIds, ...allIds])] });
                        } else {
                          setForm({ ...form, toolIds: form.toolIds.filter((id) => !allIds.includes(id)) });
                        }
                      }}
                      className="rounded"
                      title={`Select all tools from ${serverName}`}
                    />
                  </div>
                  <div className="px-3 py-2 space-y-1">
                    {serverTools.map((t) => (
                      <label key={t.id} className="flex items-center justify-between text-sm cursor-pointer">
                        <span className="truncate">{t.name}</span>
                        <input type="checkbox" checked={form.toolIds.includes(t.id)}
                          onChange={(e) => setForm({ ...form, toolIds: e.target.checked ? [...form.toolIds, t.id] : form.toolIds.filter((n) => n !== t.id) })}
                          className="rounded shrink-0 ml-2" />
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-sm font-medium">Built-in Hooks</label>
              <button
                onClick={() => hooksDescriptor && setHookConfigOpen(true)}
                disabled={!hooksDescriptor}
                className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground) disabled:opacity-50 disabled:cursor-not-allowed"
                title={hooksDescriptor ? "Hook configuration" : "Loading hooks..."}
              >
                <Settings className="w-4 h-4" />
              </button>
            </div>
            <div className="border border-(--color-border) rounded-lg divide-y divide-(--color-border)">
              {hooksDescriptor?.hooks.map((h) => (
                <label key={h.name} className="flex items-center justify-between px-3 py-2 text-sm cursor-pointer">
                  <div>
                    <span className="font-medium">{h.displayName}</span>
                    <p className="text-xs text-(--color-muted-foreground) mt-0.5">{h.description}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleToggleHook(h.name)}
                    className={cn(
                      "relative w-11 h-6 rounded-full transition-colors shadow-inner shrink-0",
                      form.hookNames.includes(h.name) ? "bg-emerald-500" : "bg-gray-300"
                    )}
                  >
                    <div className={cn(
                      "absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform",
                      form.hookNames.includes(h.name) ? "translate-x-[22px]" : "translate-x-0.5"
                    )} />
                  </button>
                </label>
              ))}
              {!hooksDescriptor && (
                <div className="px-3 py-2 text-xs text-(--color-muted-foreground)">Loading hooks...</div>
              )}
            </div>
          </div>
        </div>
      </div>

      <ToolPolicyDialog
        open={toolPolicyOpen}
        onClose={() => setToolPolicyOpen(false)}
        toolPolicy={toolPolicy}
        onSave={setToolPolicy}
        models={models}
        builtinTools={builtInTools}
        hasSubAgent={form.toolIds.some((id) => {
          const tool = tools.find((t) => t.id === id);
          return tool?.name === "sub_agent";
        })}
      />
      {hooksDescriptor && (
        <HookConfigDialog
          open={hookConfigOpen}
          onClose={() => setHookConfigOpen(false)}
          hookConfig={hookConfig}
          hooks={hooksDescriptor.hooks}
          sharedSections={hooksDescriptor.sharedSections}
          onSave={setHookConfig}
        />
      )}
    </div>
  );
}

// === TeamForm: the per-team configuration panel ===

interface TeamFormData {
  name: string;
  teamDescription: string;
  workingDir: string;
  members: SingleAgentFormData[];
  contacts: Record<string, Record<string, string>>;
  deleteRemovedMemberIds: string[];
}

function TeamForm({
  initialData,
  onSave,
  onExport,
}: {
  initialData?: { name: string; teamDescription: string; workingDir?: string; members: SingleAgentFormData[]; contacts: Record<string, Record<string, string>> };
  onSave: (data: TeamFormData) => void;
  onExport?: () => void;
}) {
  const models = useAppStore((s) => s.models);
  const tools = useAppStore((s) => s.tools);
  const skills = useAppStore((s) => s.skills);
  const prompts = useAppStore((s) => s.prompts);

  const [step, setStep] = useState<0 | 1 | 2>(0);
  const [teamName, setTeamName] = useState(initialData?.name ?? "");
  const [teamDesc, setTeamDesc] = useState(initialData?.teamDescription ?? "");
  const [teamWorkingDir, setTeamWorkingDir] = useState(initialData?.workingDir ?? "");
  const [members, setMembers] = useState<SingleAgentFormData[]>(initialData?.members ?? []);
  const [contacts, setContacts] = useState<Record<string, Record<string, string>>>(initialData?.contacts ?? {});
  const [editingMemberIdx, setEditingMemberIdx] = useState<number | null>(null);
  const [removeMemberIdx, setRemoveMemberIdx] = useState<number | null>(null);
  const [deleteRemovedMemberIds, setDeleteRemovedMemberIds] = useState<string[]>([]);

  const [showPromptPicker, setShowPromptPicker] = useState(false);

  const syncContacts = (memberList: SingleAgentFormData[], currentContacts: Record<string, Record<string, string>>) => {
    const result: Record<string, Record<string, string>> = {};
    for (const m of memberList) {
      result[m.name] = {};
      const existing = currentContacts[m.name] ?? {};
      for (const other of memberList) {
        if (other.name === m.name) continue; // 不创建 self-key
        // 只保留已有的 contacts 条目，不自动添加新条目
        if (other.name in existing) {
          result[m.name][other.name] = existing[other.name];
        }
      }
    }
    return result;
  };

  const [memberError, setMemberError] = useState("");

  const removeMember = (deleteFiles: boolean) => {
    if (removeMemberIdx === null) return;
    const member = members[removeMemberIdx];
    const updated = members.filter((_, j) => j !== removeMemberIdx);
    setMembers(updated);
    setContacts(syncContacts(updated, contacts));
    if (deleteFiles && member?.id) {
      setDeleteRemovedMemberIds((ids) => (ids.includes(member.id!) ? ids : [...ids, member.id!]));
    }
    setRemoveMemberIdx(null);
  };

  const removeMemberDialog = (
    <ConfirmDialog
      open={removeMemberIdx !== null}
      title="Remove Team Member"
      message={`Remove "${removeMemberIdx !== null ? members[removeMemberIdx]?.name : ""}" from this team? You can also delete this agent's files from disk.`}
      confirmLabel="Remove and Delete Files"
      secondaryLabel="Remove Only"
      cancelLabel="Cancel"
      variant="danger"
      onConfirm={() => removeMember(true)}
      onSecondary={() => removeMember(false)}
      onCancel={() => setRemoveMemberIdx(null)}
    />
  );

  const handleMemberSave = (data: SingleAgentFormData) => {
    const isEditing = editingMemberIdx != null && editingMemberIdx < members.length;
    const trimmed = data.name.trim();
    const duplicate = members.find(
      (m, i) => m.name.trim() === trimmed && (!isEditing || i !== editingMemberIdx)
    );
    if (duplicate) {
      setMemberError(`Member name "${trimmed}" already exists in this team`);
      return;
    }
    setMemberError("");
    const updated = isEditing
      ? members.map((m, i) => (i === editingMemberIdx ? { ...data, name: trimmed } : m))
      : [...members, { ...data, name: trimmed }];
    setMembers(updated);
    setContacts(syncContacts(updated, contacts));
    setEditingMemberIdx(null);
  };

  const membersWithInvalidModel = members.filter((m) =>
    !m.modelId || !models.some((mod) => mod.id === m.modelId)
  );
  const hasInvalidMemberModel = membersWithInvalidModel.length > 0;

  // Step 0: Team info
  if (step === 0) {
    return (
      <div className="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
        <div className="flex items-start justify-between pr-10">
          <div>
            <h2 className="text-lg font-semibold mb-1">Configure Team</h2>
            <p className="text-sm text-(--color-muted-foreground)">Set up team info and description</p>
          </div>
          {onExport && initialData && (
            <button
              onClick={onExport}
              className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg border border-(--color-border) hover:bg-(--color-secondary) text-sm transition-colors shrink-0"
              title="Export as template"
            >
              <Download size={16} />
              Export
            </button>
          )}
        </div>
        <div><label className="block text-sm font-medium mb-1.5">Team Name <span className="text-red-500">*</span></label>
          <input type="text" value={teamName} onChange={(e) => setTeamName(e.target.value)} placeholder="My Agent Team"
            disabled={!!initialData?.name}
            className="w-full px-3 py-2 rounded-lg border border-(--color-border) bg-white focus:outline-none focus:ring-2 focus:ring-(--color-ring) disabled:opacity-50 disabled:cursor-not-allowed" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Working Directory</label>
          <p className="text-xs text-(--color-muted-foreground) mb-1.5">Shared working directory for all team agents</p>
          <FolderPicker
            value={teamWorkingDir}
            onChange={(path) => setTeamWorkingDir(path)}
            placeholder="/workspace/team-project"
          />
          {teamWorkingDir && (
            <p className="text-[10px] text-(--color-muted-foreground) mt-1 truncate">All agents will use: <span className="font-mono">{teamWorkingDir}</span></p>
          )}
        </div>
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-sm font-medium">Team Description</label>
            <button onClick={() => { setShowPromptPicker(!showPromptPicker); }}
              className="flex items-center gap-1 text-xs text-(--color-primary) hover:underline">
              <FileText className="w-3 h-3" />
              {showPromptPicker ? "Hide Prompt Library" : "From Prompt Library"}
            </button>
          </div>
          {showPromptPicker && (
            <div className="mb-2">
              <GroupedPromptPicker
                prompts={prompts}
                onSelect={(p) => { setTeamDesc(p.content); setShowPromptPicker(false); }}
              />
            </div>
          )}
          <textarea value={teamDesc} onChange={(e) => setTeamDesc(e.target.value)} placeholder="A collaborative team for full-stack development..." rows={4}
            className="w-full px-3 py-2 rounded-lg border border-(--color-border) bg-white focus:outline-none focus:ring-2 focus:ring-(--color-ring) resize-none" />
        </div>
        <button onClick={() => setStep(1)} disabled={!teamName}
          className="w-full py-2.5 rounded-lg border border-(--color-border) bg-(--color-primary) text-(--color-primary-foreground) hover:opacity-90 disabled:opacity-50">Next: Add Agents</button>
      </div>
    );
  }

  // Member editor (Add/Edit) — fully reuses SingleAgentForm
  if (editingMemberIdx !== null) {
    const editingMember = editingMemberIdx < members.length ? members[editingMemberIdx] : null;
    const isEditing = editingMember !== null;
    return (
      <div className="relative">
        <button
          onClick={() => { setEditingMemberIdx(null); setMemberError(""); }}
          className="absolute top-4 left-4 z-20 text-sm text-(--color-muted-foreground) hover:text-(--color-foreground) flex items-center gap-1"
        >
          &larr; Back to members
        </button>
        <SingleAgentForm
          initialData={isEditing ? editingMember : undefined}
          defaultWorkingDir={teamWorkingDir}
          onSave={handleMemberSave}
          saveError={memberError || undefined}
        />
      </div>
    );
  }

  // Step 1: Member list
  if (step === 1) {
    return (
      <div className="p-6">
        <h2 className="text-lg font-semibold mb-1">Team Members</h2>
        <p className="text-sm text-(--color-muted-foreground) mb-4">Add and configure team agents</p>
        <div className="space-y-2 max-h-[350px] overflow-y-auto mb-4">
          {members.length === 0 && (
            <p className="text-sm text-(--color-muted-foreground) text-center py-8">No agents yet. Click &quot;Add Agent&quot; to get started.</p>
          )}
          {members.map((m, i) => {
            const model = models.find((mod) => mod.id === m.modelId);
            const modelStatus = !m.modelId
              ? "Model required"
              : model
                ? model.name
                : "Model unavailable";
            const modelInvalid = !model;
            return (
              <div key={`${m.name}-${i}`} className="flex items-center justify-between p-3 rounded-lg border border-(--color-border) bg-(--color-secondary)/20">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate">{m.name}</p>
                  <p className={cn(
                    "text-xs",
                    modelInvalid ? "text-amber-700 font-medium" : "text-(--color-muted-foreground)"
                  )}>
                    {modelStatus}
                  </p>
                  <div className="flex items-center gap-1 mt-1 flex-wrap">
                    {m.toolIds.map((tn: string) => {
                      const tool = tools.find((t) => t.id === tn);
                      return (
                        <span key={tn} className="px-1.5 py-0.5 text-[10px] rounded bg-(--color-muted)/30 text-(--color-muted-foreground)">{tool?.name ?? tn}</span>
                      );
                    })}
                    {m.skillIds.map((sn: string) => {
                      const skill = skills.find((s) => (s.id || s.name) === sn);
                      return (
                        <span key={sn} className="px-1.5 py-0.5 text-[10px] rounded bg-amber-100 text-amber-700">{skill?.name ?? sn}</span>
                      );
                    })}
                    {m.hookNames.map((hn: string) => (
                      <span key={hn} className="px-1.5 py-0.5 text-[10px] rounded bg-violet-100 text-violet-700">{hn}</span>
                    ))}
                  </div>
                </div>
                <div className="flex gap-1 shrink-0 ml-2">
                  <button onClick={() => { setEditingMemberIdx(i); setMemberError(""); }}
                    className="px-2 py-1 text-xs rounded hover:bg-(--color-secondary)">Edit</button>
                  <button onClick={() => setRemoveMemberIdx(i)}
                    className="px-2 py-1 text-xs rounded hover:bg-red-50 text-(--color-danger)">Remove</button>
                </div>
              </div>
            );
          })}
        </div>
        {hasInvalidMemberModel && (
          <div className="mb-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>Select a valid model for every team member before configuring contacts.</span>
          </div>
        )}
        <button onClick={() => { setEditingMemberIdx(members.length); setMemberError(""); }}
          className="w-full py-2.5 rounded-lg border-2 border-dashed border-(--color-border) hover:border-(--color-primary) hover:bg-(--color-primary)/5 transition-all text-sm text-(--color-muted-foreground)">
          + Add Agent
        </button>
        <div className="flex gap-2 mt-4">
          <button onClick={() => setStep(0)} className="flex-1 py-2 rounded-lg border border-(--color-border) hover:bg-(--color-secondary) text-sm">Back</button>
          <button onClick={() => { setStep(2); setContacts(syncContacts(members, contacts)); }} disabled={members.length === 0 || hasInvalidMemberModel}
            className="flex-1 py-2.5 rounded-lg border border-(--color-border) bg-(--color-primary) text-(--color-primary-foreground) hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed">Next: Configure Contacts</button>
        </div>
        {removeMemberDialog}
      </div>
    );
  }

  // Step 2: Contacts — 为每个 agent 的每个队友设置 role 描述和可见性
  // contacts 格式: { agentName: { otherName: role } }，不含 self-key
  return (
    <div className="p-6 flex flex-col max-h-[75vh]">
      <h2 className="text-lg font-semibold mb-1">Configure Contacts</h2>
      <p className="text-sm text-(--color-muted-foreground) mb-4">Set role description and visibility for each teammate</p>
      <div className="flex-1 overflow-y-auto min-h-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-(--color-border) text-left text-xs text-(--color-muted-foreground)">
              <th className="py-2 pr-3 font-medium w-[100px]">Agent</th>
              <th className="py-2 font-medium">Teammates (visible &amp; role)</th>
            </tr>
          </thead>
          <tbody>
            {members.map((member) => {
              const memberContacts = contacts[member.name] ?? {};
              const others = members.filter((m) => m.name !== member.name);
              return (
                <tr key={member.name} className="border-b border-(--color-border)/50">
                  <td className="py-2.5 pr-3 font-medium align-top">{member.name}</td>
                  <td className="py-2.5 align-top">
                    {others.length === 0 && (
                      <p className="text-xs text-(--color-muted-foreground)">No other members</p>
                    )}
                    <div className="space-y-2">
                      {others.map((other) => {
                        const isVisible = other.name in memberContacts;
                        return (
                          <div key={other.name} className="flex items-center gap-2">
                            <label className="flex items-center gap-1 text-xs cursor-pointer shrink-0">
                              <input
                                type="checkbox"
                                checked={isVisible}
                                onChange={(e) => {
                                  const newContacts = { ...contacts };
                                  const entry = { ...(newContacts[member.name] ?? {}) };
                                  if (e.target.checked) {
                                    entry[other.name] = "";
                                  } else {
                                    delete entry[other.name];
                                  }
                                  newContacts[member.name] = entry;
                                  setContacts(newContacts);
                                }}
                                className="rounded" />
                              {other.name}
                            </label>
                            {isVisible && (
                              <input
                                type="text"
                                value={memberContacts[other.name] ?? ""}
                                onChange={(e) => {
                                  const newContacts = { ...contacts };
                                  newContacts[member.name] = { ...(newContacts[member.name] ?? {}), [other.name]: e.target.value };
                                  setContacts(newContacts);
                                }}
                                placeholder="Role description..."
                                className="flex-1 px-2 py-1 text-xs rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring)" />
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex gap-2 mt-4 pt-4 border-t border-(--color-border) shrink-0">
        <button onClick={() => setStep(1)} className="flex-1 py-2 rounded-lg border border-(--color-border) hover:bg-(--color-secondary) text-sm">Back</button>
        <button onClick={() => onSave({ name: teamName, teamDescription: teamDesc, workingDir: teamWorkingDir, members, contacts, deleteRemovedMemberIds })}
          className="flex-1 py-2.5 rounded-lg border border-(--color-border) bg-(--color-primary) text-(--color-primary-foreground) hover:opacity-90">Create Team</button>
      </div>
      {removeMemberDialog}
    </div>
  );
}

// === Top-level AgentConfigDialog ===

interface AgentConfigDialogProps {
  open: boolean;
  onClose: () => void;
  mode: "create" | "edit";
  type: "agent" | "team" | "";
  agentId?: string;
}

// Helper: turn existing SingleAgent data into SingleAgentFormData for editing.
function agentToFormData(agent: SingleAgent): SingleAgentFormData {
  return {
    name: agent.name,
    modelId: agent.modelId,
    systemPrompt: agent.systemPrompt,
    workingDir: agent.workingDir ?? "",
    toolIds: agent.toolIds ?? [],
    skillIds: agent.skillIds ?? [],
    hookNames: agent.hookNames ?? DEFAULT_HOOK_NAMES,
    toolPolicy: agent.toolPolicy ?? DEFAULT_TOOL_POLICY,
    hookConfig: agent.hookConfig ?? {},
  };
}

export function AgentConfigDialog({ open, onClose, mode, type, agentId }: AgentConfigDialogProps) {
  const agents = useAppStore((s) => s.agents);
  const models = useAppStore((s) => s.models);
  const tools = useAppStore((s) => s.tools);
  const skills = useAppStore((s) => s.skills);
  const addAgent = useAppStore((s) => s.createAgentApi);
  const addTeam = useAppStore((s) => s.createTeamApi);
  const updateAgent = useAppStore((s) => s.updateAgent);
  const updateTeam = useAppStore((s) => s.updateTeam);
  const addToast = useAppStore((s) => s.addToast);
  const [localType, setLocalType] = useState<"agent" | "team" | "">(type);

  useEffect(() => {
    setLocalType(type);
  }, [open, type]);

  const existingAgent = agentId ? agents.find((a) => a.id === agentId) : null;
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Template import state
  const [templatePickerOpen, setTemplatePickerOpen] = useState(false);
  const [importedFormData, setImportedFormData] = useState<{
    type: "agent" | "team";
    agentData?: SingleAgentFormData;
    teamData?: {
      name: string;
      teamDescription: string;
      workingDir: string;
      members: SingleAgentFormData[];
      contacts: Record<string, Record<string, string>>;
    };
  } | null>(null);

  const handleTemplatePicked = async (filePath: string) => {
    try {
      const data = await api.readFile(filePath);
      const jsonStr = typeof data.content === "string" ? data.content : JSON.stringify(data.content ?? data);
      const obj = JSON.parse(jsonStr);
      const tplType = detectTemplateType(obj);
      if (!tplType) {
        addToast("Unrecognized template format", "warning");
        return;
      }
      const template = obj as Template;
      const resolved = resolveTemplate(
        template,
        models,
        tools,
        skills,
      );
      if (resolved.warnings.length > 0) {
        for (const w of resolved.warnings) {
          addToast(w, "warning");
        }
      }
      if (resolved.type === "agent") {
        setImportedFormData({
          type: "agent",
          agentData: {
            name: resolved.name,
            modelId: "",
            systemPrompt: resolved.systemPrompt,
            workingDir: "",
            toolIds: resolved.toolIds,
            skillIds: resolved.skillIds,
            hookNames: resolved.hookNames,
            toolPolicy: resolved.toolPolicy as ToolPolicy,
            hookConfig: resolved.hookConfig,
          },
        });
        setLocalType("agent");
      } else if (resolved.type === "team" && resolved.members) {
        setImportedFormData({
          type: "team",
          teamData: {
            name: resolved.name,
            teamDescription: resolved.teamDescription ?? "",
            workingDir: "",
            members: resolved.members.map((m) => ({
              name: m.name,
              modelId: "",
              systemPrompt: m.systemPrompt,
              workingDir: "",
              toolIds: m.toolIds,
              skillIds: m.skillIds,
              hookNames: m.hookNames,
              toolPolicy: m.toolPolicy as ToolPolicy,
              hookConfig: m.hookConfig,
            })),
            contacts: resolved.contacts ?? {},
          },
        });
        setLocalType("team");
      }
    } catch (e) {
      addToast(`Failed to parse template: ${e instanceof Error ? e.message : String(e)}`, "warning");
    }
  };

  // Export helper — saves template JSON to ./templates/ directory
  const handleExportAgent = async () => {
    if (existingAgent && isSingleAgent(existingAgent)) {
      const tpl = agentToTemplate(existingAgent, models, tools, skills);
      const jsonStr = JSON.stringify(tpl, null, 2);
      const filePath = `./templates/${existingAgent.name}_template.json`;
      try {
        await api.writeFile(filePath, jsonStr);
        addToast(`Template exported to ${filePath}`, "info");
      } catch (e) {
        addToast(`Export failed: ${e instanceof Error ? e.message : String(e)}`, "warning");
      }
    }
  };

  const handleExportTeam = async () => {
    if (existingAgent && isTeam(existingAgent)) {
      const memberTemplates = existingAgent.members.map((m) =>
        agentToTemplate(m, models, tools, skills)
      );
      const tpl = {
        type: "team",
        name: existingAgent.name,
        teamDescription: existingAgent.teamDescription ?? "",
        members: memberTemplates,
        contacts: existingAgent.contacts ?? {},
      };
      const jsonStr = JSON.stringify(tpl, null, 2);
      const filePath = `./templates/${existingAgent.name}_template.json`;
      try {
        await api.writeFile(filePath, jsonStr);
        addToast(`Template exported to ${filePath}`, "info");
      } catch (e) {
        addToast(`Export failed: ${e instanceof Error ? e.message : String(e)}`, "warning");
      }
    }
  };

  if (!open) return null;

  if (!localType && mode === "create") {
    return (
      <>
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
          <div className="relative w-full max-w-2xl bg-(--color-background) rounded-2xl shadow-[-8px_8px_24px_rgba(0,0,0,0.08)] overflow-hidden">
            <button onClick={onClose} className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-(--color-secondary) transition-colors z-10"><X size={18} /></button>
            <TypeSelection
              onSelect={(t) => { setLocalType(t); setImportedFormData(null); }}
              onTemplate={() => setTemplatePickerOpen(true)}
            />
          </div>
        </div>
        <TemplatePicker
          open={templatePickerOpen}
          onClose={() => setTemplatePickerOpen(false)}
          onSelect={handleTemplatePicked}
        />
      </>
    );
  }

  const hasImportData = importedFormData !== null;

  const handleSingleSave = async (data: SingleAgentFormData) => {
    setError(null);
    setSaving(true);
    try {
      const toolPolicyWithCwd = { ...data.toolPolicy, cwd: data.workingDir };
      const payload: CreateAgentPayload = {
        name: data.name,
        modelId: data.modelId,
        systemPrompt: data.systemPrompt,
        workingDir: data.workingDir,
        toolIds: data.toolIds,
        skillIds: data.skillIds,
        hookNames: data.hookNames,
        hookConfig: data.hookConfig,
        toolPolicy: toolPolicyWithCwd,
      };

      if (mode === "edit" && existingAgent) {
        await updateAgent(existingAgent.id || existingAgent.name, payload);
      } else {
        await addAgent(payload);
      }
      onClose();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      console.error("Failed to save agent:", e);
    } finally {
      setSaving(false);
    }
  };

  const handleTeamSave = (data: TeamFormData) => {
    const memberPayloads: CreateAgentPayload[] = data.members.map((m) => ({
      name: m.name,
      modelId: m.modelId,
      systemPrompt: m.systemPrompt,
      workingDir: m.workingDir,
      toolIds: m.toolIds,
      skillIds: m.skillIds,
      hookNames: m.hookNames,
      hookConfig: m.hookConfig,
      toolPolicy: { ...m.toolPolicy, cwd: m.workingDir },
    }));

    const payload: CreateTeamPayload = {
      name: data.name,
      teamDescription: data.teamDescription,
      workingDir: data.workingDir,
      members: memberPayloads,
      contacts: data.contacts,
    };

    if (mode === "edit" && existingAgent) {
      updateTeam(existingAgent.id, {
        ...payload,
        deleteRemovedMemberIds: data.deleteRemovedMemberIds,
      });
    } else {
      addTeam(payload);
    }
    onClose();
  };

  const effectiveType = localType || existingAgent?.type || "agent";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-4xl bg-(--color-background) rounded-2xl shadow-[-8px_8px_24px_rgba(0,0,0,0.08)] overflow-hidden">
        <button onClick={onClose} className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-(--color-secondary) transition-colors z-10"><X size={18} /></button>
        {effectiveType === "agent" && (
          <SingleAgentForm
            initialData={hasImportData ? importedFormData.agentData : (existingAgent && isSingleAgent(existingAgent) ? agentToFormData(existingAgent) : undefined)}
            onSave={handleSingleSave}
            saving={saving}
            saveError={error}
            onExport={mode === "edit" && existingAgent && isSingleAgent(existingAgent) ? handleExportAgent : undefined}
          />
        )}
        {effectiveType === "team" && existingAgent && isTeam(existingAgent) && (
          <TeamForm
            initialData={hasImportData ? importedFormData.teamData : {
              name: existingAgent.name,
              teamDescription: existingAgent.teamDescription ?? "",
              workingDir: existingAgent.workingDir ?? existingAgent.baseDir ?? "",
              members: existingAgent.members.map((m) => ({
                id: m.id,
                name: m.name,
                modelId: m.modelId,
                systemPrompt: m.systemPrompt,
                workingDir: m.workingDir,
                toolIds: m.toolIds,
                skillIds: m.skillIds,
                hookNames: m.hookNames ?? DEFAULT_HOOK_NAMES,
                toolPolicy: m.toolPolicy ?? DEFAULT_TOOL_POLICY,
                hookConfig: m.hookConfig ?? {},
              })),
              contacts: existingAgent.contacts ?? {},
            }}
            onSave={handleTeamSave}
            onExport={mode === "edit" ? handleExportTeam : undefined}
          />
        )}
        {effectiveType === "team" && !existingAgent && (
          <TeamForm
            initialData={hasImportData ? importedFormData.teamData : undefined}
            onSave={handleTeamSave}
          />
        )}
      </div>
    </div>
  );
}
