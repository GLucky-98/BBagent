import { useState } from "react";
import { FileText, Copy, Check, FolderOpen, Plus, X } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import type { Prompt } from "../types";

const ACTIVE_CLASS = "bg-[--color-primary]/10 text-[--color-primary] font-semibold shadow-[inset_4px_0_0_0_#10b981]";

function NewPromptForm({ onClose }: { onClose: () => void }) {
  const addPrompt = useAppStore((s) => s.addPrompt);
  const [name, setName] = useState("");
  const [content, setContent] = useState("");

  const handleSave = () => {
    addPrompt({
      id: crypto.randomUUID(),
      name,
      description: "",
      content,
      source: "imported",
    });
    onClose();
  };

  return (
    <div className="flex-1 h-full flex flex-col bg-[--color-background]">
      <div className="flex items-center justify-between px-4 py-3 bg-white border-b border-[--color-border]">
        <h3 className="text-sm font-semibold">New Prompt</h3>
        <button onClick={onClose} className="p-1 rounded hover:bg-[--color-secondary]"><X size={14} /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <div>
          <label className="block text-sm font-medium mb-1">Title</label>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Code Review Assistant" className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Content</label>
          <textarea value={content} onChange={(e) => setContent(e.target.value)}
            placeholder="Enter the system prompt content..." rows={10}
            className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring] resize-none" />
        </div>
        <button onClick={handleSave} disabled={!name || !content}
          className="w-full py-2 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] text-sm font-medium hover:opacity-90 disabled:opacity-50">Save</button>
      </div>
    </div>
  );
}

function PromptList({ onNew }: { onNew: () => void }) {
  const prompts = useAppStore((s) => s.prompts);
  const selectedPromptId = useAppStore((s) => s.selectedPromptId);
  const setSelectedPromptId = useAppStore((s) => s.setSelectedPromptId);
  const importPrompts = useAppStore((s) => s.importPrompts);
  const [showImport, setShowImport] = useState(false);
  const [importPath, setImportPath] = useState("");

  const handleImport = () => {
    importPrompts([{
      id: crypto.randomUUID(), name: "imported-prompt", description: "Imported prompt", content: "Imported prompt content.", source: "imported",
    }]);
    setShowImport(false); setImportPath("");
  };

  const builtIn = prompts.filter((p) => p.source === "built-in");
  const imported = prompts.filter((p) => p.source === "imported");

  return (
    <div className="w-[300px] h-full bg-white border-r border-[--color-border] flex flex-col">
      <div className="p-3 border-b border-[--color-border] space-y-1.5">
        <button onClick={onNew}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] hover:opacity-90 transition-opacity">
          <Plus size={16} /><span className="text-sm font-medium">New Prompt</span>
        </button>
        <button onClick={() => setShowImport(!showImport)}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-[--color-border] text-sm font-medium hover:bg-[--color-secondary]">
          <FolderOpen size={16} />Import from Folder
        </button>
      </div>
      {showImport && (
        <div className="p-2 border-b border-[--color-border] space-y-2">
          <input type="text" value={importPath} onChange={(e) => setImportPath(e.target.value)}
            placeholder="/path/to/prompts/folder" className="w-full px-2 py-1.5 text-xs rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
          <div className="flex gap-2">
            <button onClick={handleImport} disabled={!importPath}
              className="flex-1 py-1 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] text-xs font-medium hover:opacity-90 disabled:opacity-50">Import</button>
            <button onClick={() => setShowImport(false)} className="px-3 py-1 rounded-lg border border-[--color-border] text-xs hover:bg-[--color-secondary]">Cancel</button>
          </div>
        </div>
      )}
      <div className="flex-1 overflow-y-auto p-2">
        {prompts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[--color-muted-foreground]">
            <FileText size={32} className="mb-2 opacity-50" /><p className="text-sm">No prompts available</p>
          </div>
        ) : (
          <div className="space-y-1">
            {builtIn.length > 0 && <div className="px-2 py-1 text-xs font-medium text-[--color-muted-foreground]">Built-in</div>}
            {builtIn.map((prompt) => (
              <button key={prompt.id} onClick={() => setSelectedPromptId(prompt.id)}
                className={cn("w-full flex items-start gap-2 px-3 py-2 rounded-lg text-left transition-all hover:bg-[--color-secondary]", selectedPromptId === prompt.id && ACTIVE_CLASS)}>
                <div className="w-6 h-6 rounded-lg bg-[--color-primary]/10 text-[--color-primary] flex items-center justify-center shrink-0"><FileText size={12} /></div>
                <div className="flex-1 min-w-0"><p className="text-sm font-medium truncate">{prompt.name}</p><p className="text-xs text-[--color-muted-foreground] mt-0.5 line-clamp-2">{prompt.description}</p></div>
              </button>
            ))}
            {imported.length > 0 && <div className="px-2 py-1 text-xs font-medium text-[--color-muted-foreground] mt-2">Imported</div>}
            {imported.map((prompt) => (
              <button key={prompt.id} onClick={() => setSelectedPromptId(prompt.id)}
                className={cn("w-full flex items-start gap-2 px-3 py-2 rounded-lg text-left transition-all hover:bg-[--color-secondary]", selectedPromptId === prompt.id && ACTIVE_CLASS)}>
                <div className="w-6 h-6 rounded-lg bg-[--color-primary]/10 text-[--color-primary] flex items-center justify-center shrink-0"><FileText size={12} /></div>
                <div className="flex-1 min-w-0"><p className="text-sm font-medium truncate">{prompt.name}</p><p className="text-xs text-[--color-muted-foreground] mt-0.5 line-clamp-2">{prompt.description}</p></div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PromptDetailPanel({ showNew, onCloseNew }: { showNew: boolean; onCloseNew: () => void }) {
  const prompts = useAppStore((s) => s.prompts);
  const selectedPromptId = useAppStore((s) => s.selectedPromptId);
  const [copied, setCopied] = useState(false);
  const selectedPrompt = prompts.find((p) => p.id === selectedPromptId);

  const handleCopy = () => {
    if (selectedPrompt) { navigator.clipboard.writeText(selectedPrompt.content); setCopied(true); setTimeout(() => setCopied(false), 2000); }
  };

  if (showNew) return <NewPromptForm onClose={onCloseNew} />;

  if (!selectedPrompt) {
    return (
      <div className="flex-1 h-full flex flex-col items-center justify-center bg-[--color-background] text-[--color-muted-foreground]">
        <FileText size={48} className="mb-4 opacity-30" /><p className="text-lg font-medium">No prompt selected</p><p className="text-sm mt-1">Select a prompt to view details</p>
      </div>
    );
  }

  return (
    <div className="flex-1 h-full flex flex-col bg-[--color-background]">
      <header className="px-4 py-3 bg-white border-b border-[--color-border]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[--color-primary]/10 text-[--color-primary] flex items-center justify-center"><FileText size={16} /></div>
            <div><h2 className="font-semibold text-sm">{selectedPrompt.name}</h2><p className="text-xs text-[--color-muted-foreground]">{selectedPrompt.source}</p></div>
          </div>
          <button onClick={handleCopy}
            className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all", copied ? "bg-emerald-100 text-emerald-600" : "bg-[--color-secondary] hover:bg-[--color-secondary]/80")}>
            {copied ? <Check size={14} /> : <Copy size={14} />}<span>{copied ? "Copied!" : "Copy"}</span>
          </button>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div><h3 className="text-xs font-medium mb-1">Description</h3><div className="bg-white rounded border border-[--color-border] p-2"><p className="text-xs">{selectedPrompt.description}</p></div></div>
        <div><h3 className="text-xs font-medium mb-1">Content</h3><div className="bg-white rounded border border-[--color-border] p-2"><pre className="text-xs whitespace-pre-wrap font-mono">{selectedPrompt.content}</pre></div></div>
      </div>
    </div>
  );
}

export function PromptsModule() {
  const [showNew, setShowNew] = useState(false);

  return (
    <div className="flex h-full">
      <PromptList onNew={() => setShowNew(true)} />
      <PromptDetailPanel showNew={showNew} onCloseNew={() => setShowNew(false)} />
    </div>
  );
}
