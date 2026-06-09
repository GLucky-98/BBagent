import { useState, useEffect, useRef } from "react";
import { FileText, Copy, Check, FolderOpen, Plus, X, Pencil, Trash2, ChevronRight, FolderPlus, FolderClosed } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import { FolderPickerModal } from "./FolderPickerModal";
import type { Prompt } from "../types";

const ACTIVE_CLASS = "bg-(--color-primary)/10 text-(--color-primary) font-semibold shadow-[inset_4px_0_0_0_#3b82f6]";

// --- helpers ---

/** Group prompts into { groupName: Prompt[] }, ungrouped under "" */
function groupPrompts(prompts: Prompt[]): { ungrouped: Prompt[]; groups: { name: string; prompts: Prompt[] }[] } {
  const ungrouped: Prompt[] = [];
  const groupMap = new Map<string, Prompt[]>();
  for (const p of prompts) {
    if (!p.group) {
      ungrouped.push(p);
    } else {
      const list = groupMap.get(p.group) ?? [];
      list.push(p);
      groupMap.set(p.group, list);
    }
  }
  // sort groups alphabetically
  const groups = Array.from(groupMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([name, prompts]) => ({ name, prompts }));
  return { ungrouped, groups };
}

// --- Context Menu ---

interface ContextMenuState {
  x: number;
  y: number;
  target: { type: "prompt"; id: string; group: string } | { type: "group"; name: string };
}

function ContextMenu({
  state,
  groups,
  onClose,
  onMoveToGroup,
  onRemoveFromGroup,
  onDeleteGroup,
  onRenameGroup,
  onNewGroup,
}: {
  state: ContextMenuState;
  groups: string[];
  onClose: () => void;
  onMoveToGroup: (promptId: string, groupName: string) => void;
  onRemoveFromGroup: (promptId: string) => void;
  onDeleteGroup: (groupName: string, deletePrompts: boolean) => void;
  onRenameGroup: (oldName: string, newName: string) => void;
  onNewGroup: (promptId: string) => void;
}) {
  const [showMoveMenu, setShowMoveMenu] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showRename, setShowRename] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const renameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (showRename && renameRef.current) renameRef.current.focus();
  }, [showRename]);

  if (state.target.type === "prompt") {
    const { id, group } = state.target;
    return (
      <>
        <div className="fixed inset-0 z-40" onClick={onClose} onContextMenu={(e) => { e.preventDefault(); onClose(); }} />
        <div className="fixed z-50 bg-white border border-(--color-border) rounded-lg shadow-lg py-1 min-w-[160px]" style={{ left: state.x, top: state.y }}>
          <button className="w-full text-left px-3 py-1.5 text-sm hover:bg-(--color-secondary) flex items-center justify-between"
            onClick={() => setShowMoveMenu(!showMoveMenu)}>
            Move to Group
            <ChevronRight size={12} className="ml-auto" />
          </button>
          {showMoveMenu && (
            <div className="absolute left-full top-0 bg-white border border-(--color-border) rounded-lg shadow-lg py-1 min-w-[140px]">
              <button className="w-full text-left px-3 py-1.5 text-sm hover:bg-(--color-secondary)"
                onClick={() => { onNewGroup(id); onClose(); }}>
                <FolderPlus size={12} className="inline mr-1.5" />New Group...
              </button>
              {group && (
                <button className="w-full text-left px-3 py-1.5 text-sm hover:bg-(--color-secondary)"
                  onClick={() => { onRemoveFromGroup(id); onClose(); }}>
                  Remove from Group
                </button>
              )}
              <div className="border-t border-(--color-border) my-1" />
              {groups
                .filter((g) => g !== group)
                .map((g) => (
                  <button key={g} className="w-full text-left px-3 py-1.5 text-sm hover:bg-(--color-secondary) truncate"
                    onClick={() => { onMoveToGroup(id, g); onClose(); }}>
                    {g}
                  </button>
                ))}
            </div>
          )}
        </div>
      </>
    );
  }

  // group context menu
  const { name } = state.target;
  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} onContextMenu={(e) => { e.preventDefault(); onClose(); }} />
      <div className="fixed z-50 bg-white border border-(--color-border) rounded-lg shadow-lg py-1 min-w-[160px]" style={{ left: state.x, top: state.y }}>
        <button className="w-full text-left px-3 py-1.5 text-sm hover:bg-(--color-secondary)"
          onClick={() => { setRenameValue(name); setShowRename(true); }}>
          Rename Group
        </button>
        <button className="w-full text-left px-3 py-1.5 text-sm hover:bg-red-50 text-red-600"
          onClick={() => setShowDeleteConfirm(true)}>
          Delete Group
        </button>
        {showRename && (
          <div className="px-2 py-1.5">
            <input ref={renameRef} value={renameValue} onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && renameValue.trim() && renameValue.trim() !== name) {
                  onRenameGroup(name, renameValue.trim());
                  onClose();
                }
                if (e.key === "Escape") onClose();
              }}
              className="w-full px-2 py-1 text-sm rounded border border-(--color-border) focus:outline-none focus:ring-1 focus:ring-(--color-ring)" />
          </div>
        )}
        {showDeleteConfirm && (
          <div className="px-2 py-1.5 space-y-1">
            <p className="text-xs text-(--color-muted-foreground)">Delete group "{name}"?</p>
            <button className="w-full text-left px-2 py-1 text-xs rounded hover:bg-(--color-secondary)"
              onClick={() => { onDeleteGroup(name, false); onClose(); }}>
              Remove group only (prompts move to top)
            </button>
            <button className="w-full text-left px-2 py-1 text-xs rounded hover:bg-red-50 text-red-600"
              onClick={() => { onDeleteGroup(name, true); onClose(); }}>
              Delete group and all prompts
            </button>
          </div>
        )}
      </div>
    </>
  );
}

// --- PromptForm ---

function PromptForm({ onClose, editPrompt, copyPrompt, prompts }: { onClose: () => void; editPrompt?: Prompt; copyPrompt?: Prompt; prompts: Prompt[] }) {
  const addPrompt = useAppStore((s) => s.addPrompt);
  const updatePrompt = useAppStore((s) => s.updatePrompt);
  const src = copyPrompt ?? editPrompt;
  const [name, setName] = useState(src?.name ? (copyPrompt ? src.name + " (copy)" : src.name) : "");
  const [content, setContent] = useState(src?.content ?? "");
  const [group, setGroup] = useState(src?.group ?? "");
  const [showGroupInput, setShowGroupInput] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");

  const existingGroups = [...new Set(prompts.map((p) => p.group).filter(Boolean))].sort();

  useEffect(() => {
    if (copyPrompt) {
      setName(copyPrompt.name + " (copy)");
      setContent(copyPrompt.content);
      setGroup(copyPrompt.group);
    }
  }, [copyPrompt]);

  const handleSave = () => {
    if (editPrompt) {
      updatePrompt(editPrompt.id, { name, content, group });
    } else {
      addPrompt({ id: crypto.randomUUID(), name, content, group });
    }
    onClose();
  };

  const handleCreateGroup = () => {
    if (newGroupName.trim()) {
      setGroup(newGroupName.trim());
      setShowGroupInput(false);
      setNewGroupName("");
    }
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
          <label className="block text-sm font-medium mb-1">Group</label>
          <div className="flex gap-1.5">
            <select value={group} onChange={(e) => setGroup(e.target.value)}
              className="flex-1 px-2 py-1.5 text-sm rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring)">
              <option value="">No Group</option>
              {existingGroups.map((g) => <option key={g} value={g}>{g}</option>)}
            </select>
            <button type="button" onClick={() => setShowGroupInput(!showGroupInput)}
              className="px-2 py-1.5 rounded border border-(--color-border) text-sm hover:bg-(--color-secondary)"
              title="Create new group">
              <FolderPlus size={14} />
            </button>
          </div>
          {showGroupInput && (
            <div className="flex gap-1.5 mt-1.5">
              <input type="text" value={newGroupName} onChange={(e) => setNewGroupName(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleCreateGroup(); }}
                placeholder="New group name..." className="flex-1 px-2 py-1 text-sm rounded border border-(--color-border) focus:outline-none focus:ring-1 focus:ring-(--color-ring)" />
              <button onClick={handleCreateGroup} disabled={!newGroupName.trim()}
                className="px-2 py-1 text-sm rounded border border-(--color-border) bg-(--color-primary) text-(--color-primary-foreground) disabled:opacity-50">Add</button>
            </div>
          )}
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

// --- PromptList (with groups, drag & drop, context menu) ---

function PromptList({ onNew, onSelect, onEdit, onCopyFrom }: { onNew: () => void; onSelect: () => void; onEdit: (id: string) => void; onCopyFrom: (id: string) => void }) {
  const prompts = useAppStore((s) => s.prompts);
  const selectedPromptId = useAppStore((s) => s.selectedPromptId);
  const setSelectedPromptId = useAppStore((s) => s.setSelectedPromptId);
  const importPrompts = useAppStore((s) => s.importPrompts);
  const updatePrompt = useAppStore((s) => s.updatePrompt);
  const deletePrompt = useAppStore((s) => s.deletePrompt);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const [copyOpen, setCopyOpen] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [newGroupInline, setNewGroupInline] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");
  const newGroupInputRef = useRef<HTMLInputElement>(null);
  const [dragOverGroup, setDragOverGroup] = useState<string | null>(null);
  const [emptyGroups, setEmptyGroups] = useState<Set<string>>(new Set());

  const { ungrouped, groups } = groupPrompts(prompts);
  // Merge empty groups into the groups list for rendering
  const existingGroupNames = new Set(groups.map((g) => g.name));
  const allGroups = [
    ...groups,
    ...Array.from(emptyGroups)
      .filter((name) => !existingGroupNames.has(name))
      .sort()
      .map((name) => ({ name, prompts: [] as Prompt[] })),
  ];
  const groupNames = allGroups.map((g) => g.name);

  useEffect(() => {
    if (newGroupInline && newGroupInputRef.current) newGroupInputRef.current.focus();
  }, [newGroupInline]);

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

  const toggleGroup = (name: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  // --- drag & drop ---
  const handleDragStart = (e: React.DragEvent, promptId: string) => {
    e.dataTransfer.setData("promptId", promptId);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e: React.DragEvent, groupName: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverGroup(groupName);
  };

  const handleDragLeave = () => {
    setDragOverGroup(null);
  };

  const handleDropOnGroup = (e: React.DragEvent, groupName: string) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverGroup(null);
    const promptId = e.dataTransfer.getData("promptId");
    if (promptId) {
      updatePrompt(promptId, { group: groupName });
      setEmptyGroups((prev) => {
        if (prev.has(groupName)) {
          const next = new Set(prev);
          next.delete(groupName);
          return next;
        }
        return prev;
      });
    }
  };

  const handleDropOnTopLevel = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOverGroup(null);
    const promptId = e.dataTransfer.getData("promptId");
    if (promptId) {
      updatePrompt(promptId, { group: "" });
    }
  };

  // --- context menu handlers ---
  const handleContextMenu = (e: React.MouseEvent, target: ContextMenuState["target"]) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ x: e.clientX, y: e.clientY, target });
  };

  const handleMoveToGroup = (promptId: string, groupName: string) => {
    updatePrompt(promptId, { group: groupName });
    // Remove from emptyGroups if it was there (now has a prompt)
    setEmptyGroups((prev) => {
      if (prev.has(groupName)) {
        const next = new Set(prev);
        next.delete(groupName);
        return next;
      }
      return prev;
    });
  };

  const handleRemoveFromGroup = (promptId: string) => {
    updatePrompt(promptId, { group: "" });
  };

  const handleDeleteGroup = (groupName: string, deletePrompts: boolean) => {
    const groupPrompts = prompts.filter((p) => p.group === groupName);
    if (deletePrompts) {
      groupPrompts.forEach((p) => deletePrompt(p.id));
    } else {
      groupPrompts.forEach((p) => updatePrompt(p.id, { group: "" }));
    }
    setEmptyGroups((prev) => {
      if (prev.has(groupName)) {
        const next = new Set(prev);
        next.delete(groupName);
        return next;
      }
      return prev;
    });
  };

  const handleRenameGroup = (oldName: string, newName: string) => {
    prompts.filter((p) => p.group === oldName).forEach((p) => updatePrompt(p.id, { group: newName }));
    setEmptyGroups((prev) => {
      if (prev.has(oldName)) {
        const next = new Set(prev);
        next.delete(oldName);
        next.add(newName);
        return next;
      }
      return prev;
    });
  };

  const handleNewGroupFromContextMenu = (promptId: string) => {
    setNewGroupInline(true);
    // store the prompt id to auto-assign after group creation
    setNewGroupPromptId(promptId);
  };

  const [newGroupPromptId, setNewGroupPromptId] = useState<string | null>(null);

  const handleCreateGroupInline = () => {
    if (newGroupName.trim()) {
      if (newGroupPromptId) {
        updatePrompt(newGroupPromptId, { group: newGroupName.trim() });
        setNewGroupPromptId(null);
      } else {
        // Empty group — add to emptyGroups for rendering
        setEmptyGroups((prev) => {
          const next = new Set(prev);
          next.add(newGroupName.trim());
          return next;
        });
      }
      setNewGroupName("");
      setNewGroupInline(false);
    }
  };

  const handleCreateEmptyGroup = () => {
    setNewGroupInline(true);
    setNewGroupPromptId(null);
  };

  return (
    <div className="w-[300px] h-full bg-white border-r border-(--color-border) flex flex-col">
      <div className="p-3 border-b border-(--color-border) space-y-1.5">
        <button onClick={onNew}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-(--color-border) bg-(--color-primary) text-(--color-primary-foreground) hover:opacity-90 transition-opacity">
          <Plus size={16} /><span className="text-sm">New Prompt</span>
        </button>
        <button onClick={handleCreateEmptyGroup}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-(--color-border) text-sm hover:bg-(--color-secondary) transition-colors">
          <FolderPlus size={16} /><span className="text-sm">New Group</span>
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
                      {p.group ? `${p.group} / ` : ""}{p.name}
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

      <div className="flex-1 overflow-y-auto p-2"
        onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }}
        onDrop={handleDropOnTopLevel}>
        {prompts.length === 0 && !newGroupInline ? (
          <div className="flex flex-col items-center justify-center h-full text-(--color-muted-foreground)">
            <FileText size={32} className="mb-2 opacity-50" /><p className="text-sm">No prompts available</p>
          </div>
        ) : (
          <div className="space-y-0.5">
            {/* New group inline input */}
            {newGroupInline && (
              <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-(--color-secondary)">
                <FolderClosed size={14} className="text-(--color-primary) shrink-0" />
                <input ref={newGroupInputRef} value={newGroupName} onChange={(e) => setNewGroupName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) handleCreateGroupInline(); if (e.key === "Escape") { setNewGroupInline(false); setNewGroupName(""); setNewGroupPromptId(null); } }}
                  onBlur={() => { setTimeout(() => { if (!newGroupName.trim()) { setNewGroupInline(false); setNewGroupPromptId(null); } }, 150); }}
                  placeholder="Group name..." className="flex-1 text-sm bg-transparent outline-none min-w-0" />
                <button onClick={handleCreateGroupInline} disabled={!newGroupName.trim()}
                  className="text-xs px-1.5 py-0.5 rounded bg-(--color-primary) text-(--color-primary-foreground) disabled:opacity-50">OK</button>
              </div>
            )}

            {/* Ungrouped prompts */}
            {ungrouped.map((prompt) => (
              <div
                key={prompt.id}
                draggable
                onDragStart={(e) => handleDragStart(e, prompt.id)}
                onClick={() => { setSelectedPromptId(prompt.id); onSelect(); }}
                onContextMenu={(e) => handleContextMenu(e, { type: "prompt", id: prompt.id, group: "" })}
                className={cn(
                  "w-full flex items-start gap-2 px-3 py-2 rounded-lg text-left transition-all hover:bg-(--color-secondary) cursor-pointer group",
                  selectedPromptId === prompt.id && ACTIVE_CLASS,
                )}
              >
                <div className="w-6 h-6 rounded-lg bg-(--color-primary)/10 text-(--color-primary) flex items-center justify-center shrink-0 mt-0.5"><FileText size={12} /></div>
                <div className="flex-1 min-w-0"><p className="text-sm font-medium truncate">{prompt.name}</p></div>
                <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground) hover:text-(--color-primary)" onClick={(e) => handleEdit(prompt.id, e)} title="Edit prompt"><Pencil size={13} /></button>
                  <button className="p-1 rounded hover:bg-red-50 text-(--color-muted-foreground) hover:text-red-500" onClick={(e) => handleDelete(prompt.id, e)} title="Delete prompt"><Trash2 size={13} /></button>
                </div>
              </div>
            ))}

            {/* Grouped prompts */}
            {allGroups.map((g) => {
              const collapsed = collapsedGroups.has(g.name);
              const isDragOver = dragOverGroup === g.name;
              return (
                <div key={g.name}
                  onDragOver={(e) => handleDragOver(e, g.name)}
                  onDragLeave={handleDragLeave}
                  onDrop={(e) => handleDropOnGroup(e, g.name)}
                  onContextMenu={(e) => handleContextMenu(e, { type: "group", name: g.name })}
                  className={cn("rounded-lg transition-colors", isDragOver && "bg-(--color-primary)/5 ring-1 ring-(--color-primary)/30")}>
                  {/* Group header */}
                  <div
                    className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg cursor-pointer hover:bg-(--color-secondary) select-none"
                    onClick={() => toggleGroup(g.name)}
                  >
                    <ChevronRight size={14} className={cn("transition-transform shrink-0", !collapsed && "rotate-90")} />
                    <FolderClosed size={14} className="text-amber-500 shrink-0" />
                    <span className="text-sm font-medium truncate">{g.name}</span>
                    <span className="text-xs text-(--color-muted-foreground) ml-auto shrink-0">{g.prompts.length}</span>
                  </div>
                  {/* Group items */}
                  {!collapsed && g.prompts.map((prompt) => (
                    <div
                      key={prompt.id}
                      draggable
                      onDragStart={(e) => handleDragStart(e, prompt.id)}
                      onClick={() => { setSelectedPromptId(prompt.id); onSelect(); }}
                      onContextMenu={(e) => handleContextMenu(e, { type: "prompt", id: prompt.id, group: g.name })}
                      className={cn(
                        "w-full flex items-start gap-2 pl-7 pr-3 py-2 rounded-lg text-left transition-all hover:bg-(--color-secondary) cursor-pointer group",
                        selectedPromptId === prompt.id && ACTIVE_CLASS,
                      )}
                    >
                      <div className="w-6 h-6 rounded-lg bg-(--color-primary)/10 text-(--color-primary) flex items-center justify-center shrink-0 mt-0.5"><FileText size={12} /></div>
                      <div className="flex-1 min-w-0"><p className="text-sm font-medium truncate">{prompt.name}</p></div>
                      <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground) hover:text-(--color-primary)" onClick={(e) => handleEdit(prompt.id, e)} title="Edit prompt"><Pencil size={13} /></button>
                        <button className="p-1 rounded hover:bg-red-50 text-(--color-muted-foreground) hover:text-red-500" onClick={(e) => handleDelete(prompt.id, e)} title="Delete prompt"><Trash2 size={13} /></button>
                      </div>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Context menu */}
      {contextMenu && (
        <ContextMenu
          state={contextMenu}
          groups={groupNames}
          onClose={() => setContextMenu(null)}
          onMoveToGroup={handleMoveToGroup}
          onRemoveFromGroup={handleRemoveFromGroup}
          onDeleteGroup={handleDeleteGroup}
          onRenameGroup={handleRenameGroup}
          onNewGroup={handleNewGroupFromContextMenu}
        />
      )}
    </div>
  );
}

// --- PromptDetailPanel ---

function PromptDetailPanel({ showForm, editPrompt, copyPrompt, onCloseForm }: { showForm: boolean; editPrompt?: Prompt; copyPrompt?: Prompt; onCloseForm: () => void }) {
  const prompts = useAppStore((s) => s.prompts);
  const selectedPromptId = useAppStore((s) => s.selectedPromptId);
  const [copied, setCopied] = useState(false);

  if (showForm) return <PromptForm onClose={onCloseForm} editPrompt={editPrompt} copyPrompt={copyPrompt} prompts={prompts} />;

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
            <div>
              <h2 className="font-semibold text-sm">{selectedPrompt.name}</h2>
              {selectedPrompt.group && <p className="text-xs text-(--color-muted-foreground)">{selectedPrompt.group}</p>}
            </div>
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

// --- PromptsModule ---

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
