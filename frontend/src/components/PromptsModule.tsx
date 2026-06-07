import { useState, useEffect } from "react";
import { FileText, Copy, Check, FolderOpen, Plus, X, Pencil, Trash2 } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import { FolderPickerModal } from "./FolderPickerModal";
import type { Prompt } from "../types";

const ACTIVE_CLASS = "bg-(--color-primary)/10 text-(--color-primary) font-semibold shadow-[inset_4px_0_0_0_#3b82f6]";

function PromptForm({ onClose, editPrompt, copyPrompt }: { onClose: () => void; editPrompt?: Prompt; copyPrompt?: Prompt }) {
  const addPrompt = useAppStore((s) => s.addPrompt);
  const updatePrompt = useAppStore((s) => s.updatePrompt);
  const src = copyPrompt ?? editPrompt;
  const [name, setName] = useState(src?.name ? (copyPrompt ? src.name + " (copy)" : src.name) : "");
  const [content, setContent] = useState(src?.content ?? "");

  useEffect(() => {
    if (copyPrompt) {
      setName(copyPrompt.name + " (copy)");
      setContent(copyPrompt.content);
    }
  }, [copyPrompt]);

  const handleSave = () => {
    if (editPrompt) {
      updatePrompt(editPrompt.id, { name, content });
    } else {
      addPrompt({ id: crypto.randomUUID(), name, content });
    }
    onClose();
  };

  return (
    <div className="flex-1 h-full flex flex-col bg-(--color-background)">
      <div className="flex items-center justify-between px-4 py-3 bg-white border-b border-(--color-border)">
        <h3 className="text-sm font-semibold">{editPrompt ? "Edit Prompt" : "New Prompt"}</h3>
        <button onClick={onClose} className="p-1 rounded hover:bg-(--color-secondary)"><X size={14} /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <div>
          <label className="block text-sm font-medium mb-1">Title</label>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Code Review Assistant" className="w-full px-2 py-1.5 text-sm rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring)" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Content</label>
          <textarea value={content} onChange={(e) => setContent(e.target.value)}
            placeholder="Enter the system prompt content..." rows={10}
            className="w-full px-2 py-1.5 text-sm rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring) resize-none" />
        </div>
        <button onClick={handleSave} disabled={!name || !content}
          className="w-full py-2 rounded-lg border border-(--color-border) bg-(--color-primary) text-(--color-primary-foreground) text-sm hover:opacity-90 disabled:opacity-50">Save</button>
      </div>
    </div>
  );
}

function PromptList({ onNew, onSelect, onEdit, onCopyFrom }: { onNew: () => void; onSelect: () => void; onEdit: (id: string) => void; onCopyFrom: (id: string) => void }) {
  const prompts = useAppStore((s) => s.prompts);
  const selectedPromptId = useAppStore((s) => s.selectedPromptId);
  const setSelectedPromptId = useAppStore((s) => s.setSelectedPromptId);
  const importPrompts = useAppStore((s) => s.importPrompts);
  const deletePrompt = useAppStore((s) => s.deletePrompt);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const [copyOpen, setCopyOpen] = useState(false);

  const handleImport = async (path: string) => {
    setImporting(true);
    try {
      await importPrompts(path);
    } catch (e: any) {
      useAppStore.getState().addToast(`Prompt import failed: ${e.message || e}`, "warning");
    } finally {
      setImporting(false);
    }
  };

  const handleEdit = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedPromptId(id);
    onEdit(id);
  };

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    deletePrompt(id);
  };

  return (
    <div className="w-[300px] h-full bg-white border-r border-(--color-border) flex flex-col">
      <div className="p-3 border-b border-(--color-border) space-y-1.5">
        <button onClick={onNew}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-(--color-border) bg-(--color-primary) text-(--color-primary-foreground) hover:opacity-90 transition-opacity">
          <Plus size={16} /><span className="text-sm">New Prompt</span>
        </button>
        {prompts.length > 0 && (
          <div className="relative">
            <button
              onClick={() => setCopyOpen(!copyOpen)}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-(--color-border) text-sm hover:bg-(--color-secondary) transition-colors"
            >
              <Copy size={14} /> Copy From
            </button>
            {copyOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setCopyOpen(false)} />
                <div className="absolute left-0 right-0 top-full mt-1 z-20 bg-white rounded-lg border border-(--color-border) shadow-lg max-h-48 overflow-y-auto">
                  {prompts.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => { onCopyFrom(p.id); setCopyOpen(false); }}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-(--color-secondary) truncate"
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
        <button
          onClick={() => setImportModalOpen(true)}
          disabled={importing}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-(--color-border) text-sm hover:bg-(--color-secondary) disabled:opacity-50"
        >
          <FolderOpen size={16} />
          {importing ? "Importing..." : "Import from Folder"}
        </button>
      </div>

      <FolderPickerModal
        open={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onSelect={handleImport}
        title="Select Prompts Folder"
      />

      <div className="flex-1 overflow-y-auto p-2">
        {prompts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-(--color-muted-foreground)">
            <FileText size={32} className="mb-2 opacity-50" /><p className="text-sm">No prompts available</p>
          </div>
        ) : (
          <div className="space-y-1">
            {prompts.map((prompt) => (
              <div
                key={prompt.id}
                onClick={() => { setSelectedPromptId(prompt.id); onSelect(); }}
                className={cn(
                  "w-full flex items-start gap-2 px-3 py-2 rounded-lg text-left transition-all hover:bg-(--color-secondary) cursor-pointer group",
                  selectedPromptId === prompt.id && ACTIVE_CLASS,
                )}
              >
                <div className="w-6 h-6 rounded-lg bg-(--color-primary)/10 text-(--color-primary) flex items-center justify-center shrink-0 mt-0.5"><FileText size={12} /></div>
                <div className="flex-1 min-w-0"><p className="text-sm font-medium truncate">{prompt.name}</p></div>
                <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground) hover:text-(--color-primary)"
                    onClick={(e) => handleEdit(prompt.id, e)}
                    title="Edit prompt"
                  >
                    <Pencil size={13} />
                  </button>
                  <button
                    className="p-1 rounded hover:bg-red-50 text-(--color-muted-foreground) hover:text-red-500"
                    onClick={(e) => handleDelete(prompt.id, e)}
                    title="Delete prompt"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PromptDetailPanel({ showForm, editPrompt, copyPrompt, onCloseForm }: { showForm: boolean; editPrompt?: Prompt; copyPrompt?: Prompt; onCloseForm: () => void }) {
  const prompts = useAppStore((s) => s.prompts);
  const selectedPromptId = useAppStore((s) => s.selectedPromptId);
  const [copied, setCopied] = useState(false);

  if (showForm) return <PromptForm onClose={onCloseForm} editPrompt={editPrompt} copyPrompt={copyPrompt} />;

  const selectedPrompt = prompts.find((p) => p.id === selectedPromptId);

  const handleCopy = () => {
    if (selectedPrompt) { navigator.clipboard.writeText(selectedPrompt.content); setCopied(true); setTimeout(() => setCopied(false), 2000); }
  };

  if (!selectedPrompt) {
    return (
      <div className="flex-1 h-full flex flex-col items-center justify-center bg-(--color-background) text-(--color-muted-foreground)">
        <FileText size={48} className="mb-4 opacity-30" /><p className="text-lg font-medium">No prompt selected</p><p className="text-sm mt-1">Select a prompt to view details</p>
      </div>
    );
  }

  return (
    <div className="flex-1 h-full flex flex-col bg-(--color-background)">
      <header className="px-4 py-3 bg-white border-b border-(--color-border)">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-(--color-primary)/10 text-(--color-primary) flex items-center justify-center"><FileText size={16} /></div>
            <div><h2 className="font-semibold text-sm">{selectedPrompt.name}</h2></div>
          </div>
          <button onClick={handleCopy}
            className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-(--color-border) text-xs transition-all", copied ? "bg-emerald-100 text-emerald-600" : "bg-(--color-secondary) hover:bg-(--color-secondary)/80")}>
            {copied ? <Check size={14} /> : <Copy size={14} />}<span>{copied ? "Copied!" : "Copy"}</span>
          </button>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto p-4">
        <div><h3 className="text-xs font-medium mb-1">Content</h3><div className="bg-white rounded border border-(--color-border) p-2"><pre className="text-xs whitespace-pre-wrap font-mono">{selectedPrompt.content}</pre></div></div>
      </div>
    </div>
  );
}

export function PromptsModule() {
  const prompts = useAppStore((s) => s.prompts);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [copyPromptId, setCopyPromptId] = useState<string | null>(null);

  const handleNew = () => { setShowForm(true); setEditingId(null); setCopyPromptId(null); };
  const handleSelect = () => { setShowForm(false); setEditingId(null); setCopyPromptId(null); };
  const handleCopyFrom = (id: string) => { setCopyPromptId(id); setShowForm(true); setEditingId(null); };

  return (
    <div className="flex h-full">
      <PromptList onNew={handleNew} onSelect={handleSelect} onEdit={(id) => { setEditingId(id); setShowForm(true); }} onCopyFrom={handleCopyFrom} />
      <PromptDetailPanel
        showForm={showForm}
        editPrompt={editingId ? prompts.find((p) => p.id === editingId) : undefined}
        copyPrompt={copyPromptId ? prompts.find((p) => p.id === copyPromptId) : undefined}
        onCloseForm={() => { setShowForm(false); setEditingId(null); setCopyPromptId(null); }}
      />
    </div>
  );
}
