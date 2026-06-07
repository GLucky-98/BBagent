import { useState, useEffect } from "react";
import { X, Bot, Users, Search, FileText, Settings, Copy } from "lucide-react";
import { useAppStore } from "../../store";
import { cn } from "../../lib/utils";
import type {
  SingleAgent,
  HookDescriptor,
  HookFieldSchema,
  HookSection,
  ToolPolicy,
  CreateAgentPayload,
  CreateTeamPayload,
} from "../../types";
import { isTeam, isSingleAgent } from "../../types";
import { FolderPicker } from "../FolderPicker";

// === Field defaults ===

const DEFAULT_TOOL_POLICY: ToolPolicy = {
  maxReadSize: 200000,
  maxReadLines: 3000,
  maxWriteSize: 5242880,
  writeCreateDirectories: true,
  bashMaxOutputLines: 1000,
  bashDefaultTimeout: 60,
};

const DEFAULT_HOOK_NAMES: string[] = ["built_in.memory", "built_in.compress"];

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
      <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[80vh]">
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
  const [promptFilter, setPromptFilter] = useState("");
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
    const filteredPrompts = promptFilter
      ? prompts.filter((p) => p.name.toLowerCase().includes(promptFilter.toLowerCase()) || p.content.toLowerCase().includes(promptFilter.toLowerCase()))
      : prompts;
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
            onClick={() => { setShowPromptPicker(!showPromptPicker); setPromptFilter(""); }}
            className="flex items-center gap-1 text-xs text-(--color-primary) hover:underline"
          >
            <FileText className="w-3 h-3" />
            {showPromptPicker ? "Hide Prompt Library" : "From Prompt Library"}
          </button>
        </div>
        {showPromptPicker && (
          <div className="mb-2 border border-(--color-border) rounded-lg overflow-hidden">
            <div className="flex items-center gap-1 px-3 py-2 border-b border-(--color-border) bg-(--color-muted)/20">
              <Search className="w-3 h-3 text-(--color-muted-foreground) shrink-0" />
              <input
                type="text"
                value={promptFilter}
                onChange={(e) => setPromptFilter(e.target.value)}
                placeholder="Search by prompt title..."
                className="flex-1 text-xs bg-transparent outline-none"
              />
            </div>
            <div className="max-h-[120px] overflow-y-auto">
              {prompts.length === 0 ? (
                <div className="px-3 py-4 text-center text-xs text-(--color-muted-foreground)">No prompts available</div>
              ) : filteredPrompts.length === 0 ? (
                <div className="px-3 py-4 text-center text-xs text-(--color-muted-foreground)">No matching prompts found</div>
              ) : (
                filteredPrompts.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className="w-full text-left px-3 py-2 hover:bg-(--color-secondary) text-sm"
                    onClick={() => {
                      onChange(p.content);
                      setShowPromptPicker(false);
                    }}
                  >
                    <span className="font-medium">{p.name}</span>
                  </button>
                ))
              )}
            </div>
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
}

function ToolPolicyDialog({ open, onClose, toolPolicy, onSave }: ToolPolicyDialogProps) {
  const [draft, setDraft] = useState<ToolPolicy>(toolPolicy);

  useEffect(() => {
    setDraft(toolPolicy);
  }, [toolPolicy, open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-(--color-border) shrink-0">
          <h3 className="text-base font-semibold">Tool Policy</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-(--color-secondary)">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          <p className="text-xs text-(--color-muted-foreground)">
            Limits shared by all built-in tools. cwd is set via Working Directory at the top level.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <NumField label="Max Read Size (bytes)" value={draft.maxReadSize}
              onChange={(v) => setDraft({ ...draft, maxReadSize: v })} />
            <NumField label="Max Read Lines" value={draft.maxReadLines}
              onChange={(v) => setDraft({ ...draft, maxReadLines: v })} />
            <NumField label="Max Write Size (bytes)" value={draft.maxWriteSize}
              onChange={(v) => setDraft({ ...draft, maxWriteSize: v })} />
            <div className="flex items-end pb-1.5">
              <label className="flex items-center gap-2 cursor-pointer text-xs">
                <input
                  type="checkbox"
                  checked={draft.writeCreateDirectories ?? true}
                  onChange={(e) => setDraft({ ...draft, writeCreateDirectories: e.target.checked })}
                  className="rounded"
                />
                Create missing dirs
              </label>
            </div>
            <NumField label="Bash Max Output Lines" value={draft.bashMaxOutputLines}
              onChange={(v) => setDraft({ ...draft, bashMaxOutputLines: v })} />
            <NumField label="Bash Timeout (seconds)" value={draft.bashDefaultTimeout}
              onChange={(v) => setDraft({ ...draft, bashDefaultTimeout: v })} />
          </div>
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

function TypeSelection({ onSelect }: { onSelect: (t: "agent" | "team") => void }) {
  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold mb-1">Create New Agent</h2>
      <p className="text-sm text-(--color-muted-foreground) mb-6">Choose the type of agent to create</p>
      <div className="grid grid-cols-2 gap-4">
        <button onClick={() => onSelect("agent")}
          className="p-6 rounded-xl border-2 border-(--color-border) hover:border-(--color-primary) hover:bg-(--color-primary)/5 transition-all flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-(--color-primary)/10 flex items-center justify-center"><Bot size={24} className="text-(--color-primary)" /></div>
          <div className="text-center"><p className="font-medium">Single Agent</p><p className="text-xs text-(--color-muted-foreground) mt-1">Create a standalone agent</p></div>
        </button>
        <button onClick={() => onSelect("team")}
          className="p-6 rounded-xl border-2 border-(--color-border) hover:border-(--color-primary) hover:bg-(--color-primary)/5 transition-all flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-(--color-primary)/10 flex items-center justify-center"><Users size={24} className="text-(--color-primary)" /></div>
          <div className="text-center"><p className="font-medium">Agent Team</p><p className="text-xs text-(--color-muted-foreground) mt-1">Create a team of agents</p></div>
        </button>
      </div>
    </div>
  );
}

// === SingleAgentForm: the per-agent configuration panel ===

export interface SingleAgentFormData {
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
}: {
  initialData?: Partial<SingleAgentFormData>;
  onSave: (data: SingleAgentFormData) => void | Promise<void>;
  saving?: boolean;
  saveError?: string | null;
}) {
  const models = useAppStore((s) => s.models);
  const tools = useAppStore((s) => s.tools);
  const skills = useAppStore((s) => s.skills);
  const prompts = useAppStore((s) => s.prompts);
  const hooksDescriptor = useAppStore((s) => s.hooksDescriptor);
  const agents = useAppStore((s) => s.agents);
  const [showPromptPicker, setShowPromptPicker] = useState(false);
  const [promptFilter, setPromptFilter] = useState("");
  const [showAllPrompts, setShowAllPrompts] = useState(false);
  const [copyFromOpen, setCopyFromOpen] = useState(false);

  const [form, setForm] = useState({
    name: initialData?.name ?? "",
    modelId: initialData?.modelId ?? models[0]?.id ?? "",
    systemPrompt: initialData?.systemPrompt ?? "",
    workingDir: initialData?.workingDir ?? "",
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

  const filteredPrompts = prompts.filter((p) =>
    showAllPrompts
      ? true
      : promptFilter.trim() === ""
        ? false
        : p.name.toLowerCase().includes(promptFilter.toLowerCase())
  );

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
    <div className="flex flex-col p-8 max-h-[85vh] overflow-hidden">
      <div className="shrink-0 flex items-start justify-between mb-4 pr-10">
          <div>
            <h2 className="text-lg font-semibold mb-1">{initialData ? "Edit Agent" : "Configure Agent"}</h2>
            <p className="text-sm text-(--color-muted-foreground)">{initialData ? "Update agent configuration" : "Fill in the agent configuration details"}</p>
            {saveError && <p className="text-sm text-red-500 mt-1">{saveError}</p>}
          </div>
          <div className="flex items-center gap-2 shrink-0">
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

      <div className="grid grid-cols-2 gap-8 flex-1 min-h-0 overflow-y-auto">
        {/* === LEFT COLUMN: Basic info + Skills === */}
        <div className="space-y-4 overflow-y-auto pr-4 min-h-0">
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
              <button onClick={() => { setShowPromptPicker(!showPromptPicker); setPromptFilter(""); }}
                className="flex items-center gap-1 text-xs text-(--color-primary) hover:underline">
                <FileText className="w-3 h-3" />
                {showPromptPicker ? "Hide Prompt Library" : "From Prompt Library"}
              </button>
            </div>
            {showPromptPicker && (
              <div className="mb-2 border border-(--color-border) rounded-lg overflow-hidden">
                <div className="flex items-center gap-1 px-3 py-2 border-b border-(--color-border) bg-(--color-muted)/20">
                  <Search className="w-3 h-3 text-(--color-muted-foreground) shrink-0" />
                  <input type="text" value={promptFilter} onChange={(e) => setPromptFilter(e.target.value)}
                    placeholder="Search by prompt title..." className="flex-1 text-xs bg-transparent outline-none" />
                  <button
                    type="button"
                    onClick={() => { setShowAllPrompts(!showAllPrompts); setPromptFilter(""); }}
                    className="text-[10px] px-1.5 py-0.5 rounded border border-(--color-border) hover:bg-(--color-secondary) shrink-0"
                  >
                    {showAllPrompts ? "Search" : "Browse All"}
                  </button>
                </div>
                <div className="max-h-[120px] overflow-y-auto">
                  {prompts.length === 0 ? (
                    <div className="px-3 py-4 text-center text-xs text-(--color-muted-foreground)">No prompts available</div>
                  ) : filteredPrompts.length === 0 ? (
                    <div className="px-3 py-4 text-center text-xs text-(--color-muted-foreground)">No matching prompts found</div>
                  ) : (
                    filteredPrompts.map((p) => (
                      <button key={p.id} onClick={() => { setForm({ ...form, systemPrompt: p.content }); setShowPromptPicker(false); }}
                        className="w-full text-left px-3 py-2 hover:bg-(--color-secondary) text-sm">
                        <span className="font-medium">{p.name}</span>
                      </button>
                    ))
                  )}
                </div>
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
        <div className="flex flex-col gap-4 overflow-y-auto pr-4 min-h-0">
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
              <div className="px-3 py-2 bg-(--color-muted)/20 text-xs font-medium text-(--color-muted-foreground)">Built-in Tools</div>
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
                  <div className="px-3 py-2 bg-(--color-muted)/20 text-xs font-medium text-(--color-muted-foreground)">MCP: {serverName}</div>
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
}

function TeamForm({
  initialData,
  onSave,
}: {
  initialData?: { name: string; teamDescription: string; workingDir?: string; members: SingleAgentFormData[]; contacts: Record<string, Record<string, string>> };
  onSave: (data: TeamFormData) => void;
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

  const [showPromptPicker, setShowPromptPicker] = useState(false);
  const [promptFilter, setPromptFilter] = useState("");
  const [showAllPrompts, setShowAllPrompts] = useState(false);

  const [rolePromptOpen, setRolePromptOpen] = useState<string | null>(null);
  const [rolePromptFilter, setRolePromptFilter] = useState("");
  const [roleShowAll, setRoleShowAll] = useState(false);

  const syncContacts = (memberList: SingleAgentFormData[], currentContacts: Record<string, Record<string, string>>) => {
    const result: Record<string, Record<string, string>> = {};
    for (const m of memberList) {
      result[m.name] = {};
      const existing = currentContacts[m.name] ?? {};
      for (const other of memberList) {
        result[m.name][other.name] = existing[other.name] ?? "";
      }
    }
    return result;
  };

  const filteredPrompts = prompts.filter((p) =>
    showAllPrompts
      ? true
      : promptFilter.trim() === ""
        ? false
        : p.name.toLowerCase().includes(promptFilter.toLowerCase())
  );

  const roleFilteredPrompts = prompts.filter((p) =>
    roleShowAll
      ? true
      : rolePromptFilter.trim() === ""
        ? false
        : p.name.toLowerCase().includes(rolePromptFilter.toLowerCase())
  );

  const handleMemberSave = (data: SingleAgentFormData) => {
    const updated = editingMemberIdx != null && editingMemberIdx < members.length
      ? members.map((m, i) => (i === editingMemberIdx ? data : m))
      : [...members, data];
    setMembers(updated);
    setContacts(syncContacts(updated, contacts));
    setEditingMemberIdx(null);
  };

  // Step 0: Team info
  if (step === 0) {
    return (
      <div className="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
        <h2 className="text-lg font-semibold mb-1">Configure Team</h2>
        <p className="text-sm text-(--color-muted-foreground) mb-6">Set up team info and description</p>
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
            <button onClick={() => { setShowPromptPicker(!showPromptPicker); setPromptFilter(""); }}
              className="flex items-center gap-1 text-xs text-(--color-primary) hover:underline">
              <FileText className="w-3 h-3" />
              {showPromptPicker ? "Hide Prompt Library" : "From Prompt Library"}
            </button>
          </div>
          {showPromptPicker && (
            <div className="mb-2 border border-(--color-border) rounded-lg overflow-hidden">
              <div className="flex items-center gap-1 px-3 py-2 border-b border-(--color-border) bg-(--color-muted)/20">
                <Search className="w-3 h-3 text-(--color-muted-foreground) shrink-0" />
                <input type="text" value={promptFilter} onChange={(e) => setPromptFilter(e.target.value)}
                  placeholder="Search by prompt title..." className="flex-1 text-xs bg-transparent outline-none" />
                <button
                  type="button"
                  onClick={() => { setShowAllPrompts(!showAllPrompts); setPromptFilter(""); }}
                  className="text-[10px] px-1.5 py-0.5 rounded border border-(--color-border) hover:bg-(--color-secondary) shrink-0"
                >
                  {showAllPrompts ? "Search" : "Browse All"}
                </button>
              </div>
              <div className="max-h-[120px] overflow-y-auto">
                {prompts.length === 0 ? (
                  <div className="px-3 py-4 text-center text-xs text-(--color-muted-foreground)">No prompts available</div>
                ) : filteredPrompts.length === 0 ? (
                  <div className="px-3 py-4 text-center text-xs text-(--color-muted-foreground)">No matching prompts found</div>
                ) : (
                  filteredPrompts.map((p) => (
                    <button key={p.id} onClick={() => { setTeamDesc(p.content); setShowPromptPicker(false); }}
                      className="w-full text-left px-3 py-2 hover:bg-(--color-secondary) text-sm">
                      <span className="font-medium">{p.name}</span>
                    </button>
                  ))
                )}
              </div>
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
    return (
      <div className="flex flex-col max-h-[85vh]">
        <button
          onClick={() => setEditingMemberIdx(null)}
          className="text-sm text-(--color-muted-foreground) hover:text-(--color-foreground) px-6 pt-4 pb-2 shrink-0 self-start"
        >
          &larr; Back to members
        </button>
        <div className="flex-1 overflow-hidden">
          <SingleAgentForm
            initialData={editingMember ?? undefined}
            onSave={handleMemberSave}
          />
        </div>
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
          {members.map((m, i) => (
            <div key={`${m.name}-${i}`} className="flex items-center justify-between p-3 rounded-lg border border-(--color-border) bg-(--color-secondary)/20">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate">{m.name}</p>
                <p className="text-xs text-(--color-muted-foreground)">{models.find((mod) => mod.id === m.modelId)?.name ?? "No model"}</p>
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
                <button onClick={() => setEditingMemberIdx(i)}
                  className="px-2 py-1 text-xs rounded hover:bg-(--color-secondary)">Edit</button>
                <button onClick={() => {
                  const updated = members.filter((_, j) => j !== i);
                  setMembers(updated);
                  setContacts(syncContacts(updated, contacts));
                }}
                  className="px-2 py-1 text-xs rounded hover:bg-red-50 text-(--color-danger)">Remove</button>
              </div>
            </div>
          ))}
        </div>
        <button onClick={() => setEditingMemberIdx(members.length)}
          className="w-full py-2.5 rounded-lg border-2 border-dashed border-(--color-border) hover:border-(--color-primary) hover:bg-(--color-primary)/5 transition-all text-sm text-(--color-muted-foreground)">
          + Add Agent
        </button>
        <div className="flex gap-2 mt-4">
          <button onClick={() => setStep(0)} className="flex-1 py-2 rounded-lg border border-(--color-border) hover:bg-(--color-secondary) text-sm">Back</button>
          <button onClick={() => { setStep(2); setContacts(syncContacts(members, contacts)); }} disabled={members.length === 0}
            className="flex-1 py-2.5 rounded-lg border border-(--color-border) bg-(--color-primary) text-(--color-primary-foreground) hover:opacity-90 disabled:opacity-50">Next: Configure Contacts</button>
        </div>
      </div>
    );
  }

  // Step 2: Contacts (kept as legacy placeholder — the user said team flow will
  // be discussed later. This preserves the prior behavior for the team dialog
  // to remain functional.)
  return (
    <div className="p-6 flex flex-col max-h-[75vh]">
      <h2 className="text-lg font-semibold mb-1">Configure Contacts</h2>
      <p className="text-sm text-(--color-muted-foreground) mb-4">Set role and visible contacts for each agent</p>
      <div className="flex-1 overflow-y-auto min-h-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-(--color-border) text-left text-xs text-(--color-muted-foreground)">
              <th className="py-2 pr-3 font-medium w-[120px]">Agent</th>
              <th className="py-2 pr-3 font-medium w-[240px]">Role</th>
              <th className="py-2 font-medium">Contacts</th>
            </tr>
          </thead>
          <tbody>
            {members.map((member) => {
              const memberContacts = contacts[member.name] ?? {};
              return (
                <tr key={member.name} className="border-b border-(--color-border)/50">
                  <td className="py-2.5 pr-3 font-medium align-top">{member.name}</td>
                  <td className="py-2.5 pr-3 align-top">
                    {rolePromptOpen === member.name && (
                      <div className="mb-2 border border-(--color-border) rounded-lg overflow-hidden">
                        <div className="flex items-center gap-1 px-3 py-2 border-b border-(--color-border) bg-(--color-muted)/20">
                          <Search className="w-3 h-3 text-(--color-muted-foreground) shrink-0" />
                          <input type="text" value={rolePromptFilter} onChange={(e) => setRolePromptFilter(e.target.value)}
                            placeholder="Search by prompt title..." className="flex-1 text-xs bg-transparent outline-none" />
                          <button
                            type="button"
                            onClick={() => { setRoleShowAll(!roleShowAll); setRolePromptFilter(""); }}
                            className="text-[10px] px-1.5 py-0.5 rounded border border-(--color-border) hover:bg-(--color-secondary) shrink-0"
                          >
                            {roleShowAll ? "Search" : "Browse All"}
                          </button>
                        </div>
                        <div className="max-h-[120px] overflow-y-auto">
                          {prompts.length === 0 ? (
                            <div className="px-3 py-4 text-center text-xs text-(--color-muted-foreground)">No prompts available</div>
                          ) : roleFilteredPrompts.length === 0 ? (
                            <div className="px-3 py-4 text-center text-xs text-(--color-muted-foreground)">No matching prompts found</div>
                          ) : (
                            roleFilteredPrompts.map((p) => (
                              <button key={p.id} onClick={() => {
                                const newContacts = { ...contacts };
                                newContacts[member.name] = { ...(newContacts[member.name] ?? {}), [member.name]: p.content };
                                setContacts(newContacts);
                                setRolePromptOpen(null);
                                setRolePromptFilter("");
                              }}
                                className="w-full text-left px-3 py-2 hover:bg-(--color-secondary) text-sm">
                                <span className="font-medium">{p.name}</span>
                              </button>
                            ))
                          )}
                        </div>
                      </div>
                    )}
                    <div className="flex items-center justify-between mb-1">
                      <button
                        onClick={() => {
                          setRolePromptOpen(rolePromptOpen === member.name ? null : member.name);
                          setRolePromptFilter("");
                          setRoleShowAll(false);
                        }}
                        className="flex items-center gap-1 text-xs text-(--color-primary) hover:underline"
                      >
                        <FileText className="w-3 h-3" />
                        {rolePromptOpen === member.name ? "Hide Prompt Library" : "From Prompt Library"}
                      </button>
                    </div>
                    <input
                      type="text"
                      value={memberContacts[member.name] ?? ""}
                      onChange={(e) => {
                        const newContacts = { ...contacts };
                        newContacts[member.name] = { ...(newContacts[member.name] ?? {}), [member.name]: e.target.value };
                        setContacts(newContacts);
                      }}
                      placeholder="Role description..."
                      className="w-full px-3 py-2 text-sm rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring)" />
                  </td>
                  <td className="py-2.5 align-top">
                    <div className="flex flex-wrap gap-x-3 gap-y-1">
                      {members.filter((m) => m.name !== member.name).map((other) => (
                        <label key={other.name} className="flex items-center gap-1 text-xs cursor-pointer">
                          <input
                            type="checkbox"
                            checked={other.name in (contacts[member.name] ?? {})}
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
                      ))}
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
        <button onClick={() => onSave({ name: teamName, teamDescription: teamDesc, workingDir: teamWorkingDir, members, contacts })}
          className="flex-1 py-2.5 rounded-lg border border-(--color-border) bg-(--color-primary) text-(--color-primary-foreground) hover:opacity-90">Create Team</button>
      </div>
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
  const addAgent = useAppStore((s) => s.createAgentApi);
  const addTeam = useAppStore((s) => s.createTeamApi);
  const updateAgent = useAppStore((s) => s.updateAgent);
  const updateTeam = useAppStore((s) => s.updateTeam);
  const [localType, setLocalType] = useState<"agent" | "team" | "">(type);

  useEffect(() => {
    setLocalType(type);
  }, [open, type]);

  const existingAgent = agentId ? agents.find((a) => a.id === agentId) : null;
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  if (!localType && mode === "create") {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
        <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden">
          <button onClick={onClose} className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-(--color-secondary) transition-colors z-10"><X size={18} /></button>
          <TypeSelection onSelect={(t) => setLocalType(t)} />
        </div>
      </div>
    );
  }

  const handleSingleSave = async (data: SingleAgentFormData) => {
    setError(null);
    setSaving(true);
    try {
      // Sync workingDir into toolPolicy.cwd so backend always has cwd
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
      updateTeam(existingAgent.id, payload);
    } else {
      addTeam(payload);
    }
    onClose();
  };

  const effectiveType = localType || existingAgent?.type || "agent";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-4xl bg-white rounded-2xl shadow-2xl overflow-hidden">
        <button onClick={onClose} className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-(--color-secondary) transition-colors z-10"><X size={18} /></button>
        {effectiveType === "agent" && (
          <SingleAgentForm
            initialData={existingAgent && isSingleAgent(existingAgent) ? agentToFormData(existingAgent) : undefined}
            onSave={handleSingleSave}
            saving={saving}
            saveError={error}
          />
        )}
        {effectiveType === "team" && existingAgent && isTeam(existingAgent) && (
          <TeamForm
            initialData={{
              name: existingAgent.name,
              teamDescription: existingAgent.teamDescription ?? "",
              workingDir: existingAgent.workingDir ?? existingAgent.baseDir ?? "",
              members: existingAgent.members.map((m) => ({
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
            onSave={handleTeamSave} />
        )}
        {effectiveType === "team" && !existingAgent && (
          <TeamForm onSave={handleTeamSave} />
        )}
      </div>
    </div>
  );
}
