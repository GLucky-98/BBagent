import { useState } from "react";
import { Plus, Box, Play, X } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import type { Model } from "../types";

const ACTIVE_CLASS = "bg-[--color-primary]/10 text-[--color-primary] font-semibold shadow-[inset_4px_0_0_0_#10b981]";

function NewModelForm({ onClose, editModel }: { onClose: () => void; editModel?: Model }) {
  const addModel = useAppStore((s) => s.addModel);
  const updateModel = useAppStore((s) => s.updateModel);

  const [form, setForm] = useState({
    name: editModel?.name ?? "",
    provider: editModel?.provider ?? "anthropic" as "anthropic" | "openai",
    modelName: editModel?.modelName ?? "",
    apiKey: editModel?.apiKey ?? "",
    baseUrl: editModel?.baseUrl ?? (editModel?.provider === "openai" ? "https://api.openai.com/v1" : "https://api.anthropic.com"),
    maxContextTokens: editModel?.maxContextTokens ?? 200000,
    maxCompletionTokens: editModel?.maxCompletionTokens ?? 100000,
    temperature: editModel?.temperature ?? 1,
    topP: editModel?.topP ?? 0.95,
    thinkingEnabled: !!editModel?.thinking,
  });

  const handleSave = () => {
    const model: Model = {
      id: editModel?.id ?? crypto.randomUUID(),
      name: form.name, provider: form.provider, modelName: form.modelName,
      apiKey: form.apiKey, baseUrl: form.baseUrl,
      maxContextTokens: form.maxContextTokens, maxCompletionTokens: form.maxCompletionTokens,
      temperature: form.temperature, topP: form.topP,
      thinking: form.thinkingEnabled ? { type: "adaptive" } : undefined,
    };
    if (editModel) { updateModel(editModel.id, model); } else { addModel(model); }
    onClose();
  };

  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">{editModel ? "Edit Model" : "New Model"}</h3>
        <button onClick={onClose} className="p-1 rounded hover:bg-[--color-secondary]"><X size={14} /></button>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <FieldRow label="Name">
          <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Claude Sonnet 4" className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
        </FieldRow>
        <FieldRow label="Provider">
          <select value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value as "anthropic" | "openai" })}
            className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]">
            <option value="anthropic">Anthropic</option>
            <option value="openai">OpenAI</option>
          </select>
        </FieldRow>
      </div>
      <FieldRow label="Model Name">
        <input type="text" value={form.modelName} onChange={(e) => setForm({ ...form, modelName: e.target.value })}
          placeholder="claude-sonnet-4-20250514" className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
      </FieldRow>
      <FieldRow label="API Key">
        <input type="text" value={form.apiKey} onChange={(e) => setForm({ ...form, apiKey: e.target.value })}
          className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
      </FieldRow>
      <FieldRow label="Base URL">
        <input type="text" value={form.baseUrl} onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
          className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
      </FieldRow>

      <div className="border-t border-[--color-border] pt-3 space-y-3">
        <FieldRow label="Max Context Tokens" hint="Maximum context window size">
          <input type="number" value={form.maxContextTokens} onChange={(e) => setForm({ ...form, maxContextTokens: Number(e.target.value) })}
            className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
        </FieldRow>
        <FieldRow label="Max Completion Tokens" hint="Maximum tokens per response">
          <input type="number" value={form.maxCompletionTokens} onChange={(e) => setForm({ ...form, maxCompletionTokens: Number(e.target.value) })}
            className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
        </FieldRow>
        <FieldRow label="Temperature" hint="Controls randomness (0-2)">
          <input type="number" step="0.1" min="0" max="2" value={form.temperature} onChange={(e) => setForm({ ...form, temperature: Number(e.target.value) })}
            className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
        </FieldRow>
        <FieldRow label="Top P" hint="Nucleus sampling threshold (0-1)">
          <input type="number" step="0.05" min="0" max="1" value={form.topP} onChange={(e) => setForm({ ...form, topP: Number(e.target.value) })}
            className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
        </FieldRow>
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-medium">Thinking</span>
            <p className="text-xs text-[--color-muted-foreground] mt-0.5">Enable extended thinking mode</p>
          </div>
          <button onClick={() => setForm({ ...form, thinkingEnabled: !form.thinkingEnabled })}
            className={cn("relative w-11 h-6 rounded-full transition-colors shadow-inner", form.thinkingEnabled ? "bg-emerald-500" : "bg-gray-300")}>
            <div className={cn("absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform", form.thinkingEnabled ? "translate-x-[22px]" : "translate-x-0.5")} />
          </button>
        </div>
      </div>

      <button onClick={handleSave} className="w-full py-2 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] text-sm font-medium hover:opacity-90">Save</button>
    </div>
  );
}

function FieldRow({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1">{label}</label>
      {children}
      {hint && <p className="text-xs text-[--color-muted-foreground] mt-0.5">{hint}</p>}
    </div>
  );
}

function ModelList({ onNew }: { onNew: () => void }) {
  const models = useAppStore((s) => s.models);
  const selectedModelId = useAppStore((s) => s.selectedModelId);
  const setSelectedModelId = useAppStore((s) => s.setSelectedModelId);

  return (
    <div className="w-[300px] h-full bg-white border-r border-[--color-border] flex flex-col">
      <div className="p-3 border-b border-[--color-border]">
        <button onClick={onNew}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] hover:opacity-90 transition-opacity">
          <Plus size={16} /><span className="text-sm font-medium">New Model</span>
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {models.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[--color-muted-foreground]">
            <Box size={32} className="mb-2 opacity-50" /><p className="text-sm">No models yet</p>
          </div>
        ) : (
          <div className="space-y-1">
            {models.map((model) => (
              <button key={model.id} onClick={() => setSelectedModelId(model.id)}
                className={cn("w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all hover:bg-[--color-secondary]", selectedModelId === model.id && ACTIVE_CLASS)}>
                <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center text-xs font-medium", model.provider === "anthropic" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-600")}>
                  {model.provider === "anthropic" ? "ANT" : "OA"}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{model.name}</p>
                  <p className="text-xs text-[--color-muted-foreground] truncate">{model.modelName}</p>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ModelTestPanel({ showForm, editModel, onCloseForm, onNew, onEdit }: {
  showForm: boolean; editModel?: Model; onCloseForm: () => void;
  onNew: () => void; onEdit: (id: string) => void;
}) {
  const models = useAppStore((s) => s.models);
  const selectedModelId = useAppStore((s) => s.selectedModelId);
  const [input, setInput] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const selectedModel = models.find((m) => m.id === selectedModelId);

  return (
    <div className="flex-1 h-full flex flex-col bg-[--color-background] overflow-y-auto">
      {showForm ? (
        <NewModelForm onClose={onCloseForm} editModel={editModel} />
      ) : selectedModel ? (
        <>
          <ModelDetailView selectedModel={selectedModel} />
          <div className="p-4 border-t border-[--color-border]">
            <div className="flex gap-2 mb-3">
              <button onClick={onNew} className="flex-1 py-1.5 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] text-xs font-medium hover:opacity-90">New</button>
              <button onClick={() => onEdit(selectedModel.id)} className="flex-1 py-1.5 rounded-lg border border-[--color-border] text-xs font-medium hover:bg-[--color-secondary]">Edit</button>
            </div>
            <textarea value={input} onChange={(e) => setInput(e.target.value)} placeholder="Test prompt..." rows={3}
              className="w-full px-3 py-2 rounded-lg border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring] resize-none text-sm mb-2" />
            <button onClick={() => { setIsLoading(true); setTimeout(() => { setIsLoading(false); setResult(`[Test response from ${selectedModel.name}]`); }, 1500); }}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-1.5 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] text-sm hover:opacity-90 disabled:opacity-50">
              <Play size={14} />{isLoading ? "Testing..." : "Run Test"}
            </button>
            {result && <pre className="mt-2 p-3 bg-white rounded border border-[--color-border] text-xs whitespace-pre-wrap">{result}</pre>}
          </div>
        </>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center bg-[--color-background] text-[--color-muted-foreground]">
          <Box size={48} className="mb-4 opacity-30" /><p className="text-lg font-medium">No model selected</p><p className="text-sm mt-1">Select a model to view details</p>
        </div>
      )}
    </div>
  );
}

function ModelDetailView({ selectedModel }: { selectedModel: Model | undefined }) {
  if (!selectedModel) return null;
  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center gap-3 mb-2">
        <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center text-xs font-bold", selectedModel.provider === "anthropic" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-600")}>
          {selectedModel.provider === "anthropic" ? "ANT" : "OA"}
        </div>
        <div><h2 className="font-semibold">{selectedModel.name}</h2><p className="text-xs text-[--color-muted-foreground]">{selectedModel.provider} \u2022 {selectedModel.modelName}</p></div>
      </div>
      <div className="bg-white rounded-lg border border-[--color-border] p-3 space-y-2 text-xs">
        {[["Base URL", selectedModel.baseUrl], ["API Key", selectedModel.apiKey || "(empty)"], ["Max Context Tokens", String(selectedModel.maxContextTokens)], ["Max Completion Tokens", String(selectedModel.maxCompletionTokens)], ["Temperature", String(selectedModel.temperature ?? "-")], ["Top P", String(selectedModel.topP ?? "-")], ["Thinking", selectedModel.thinking ? "Enabled" : "Disabled"]].map(([label, value]) => (
          <div key={label} className="flex justify-between"><span className="text-[--color-muted-foreground]">{label}</span><span className="font-mono">{value}</span></div>
        ))}
      </div>
    </div>
  );
}

export function ModelsModule() {
  const models = useAppStore((s) => s.models);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  return (
    <div className="flex h-full">
      <ModelList onNew={() => { setShowForm(true); setEditingId(null); }} />
      <ModelTestPanel
        showForm={showForm}
        editModel={editingId ? models.find((m) => m.id === editingId) : undefined}
        onCloseForm={() => { setShowForm(false); setEditingId(null); }}
        onNew={() => { setShowForm(true); setEditingId(null); }}
        onEdit={(id) => { setEditingId(id); setShowForm(true); }}
      />
    </div>
  );
}
