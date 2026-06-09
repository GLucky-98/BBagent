import { useState, useEffect, useRef } from "react";
import {
  Folder,
  ChevronRight,
  ChevronUp,
  Loader2,
  X,
  FolderPlus,
  Pencil,
  Trash2,
  Check,
} from "lucide-react";
import { api } from "../lib/api";
import { useAppStore } from "../store";

interface FolderPickerModalProps {
  open: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
  title?: string;
}

export function FolderPickerModal({ open, onClose, onSelect, title = "Select Folder" }: FolderPickerModalProps) {
  const [currentPath, setCurrentPath] = useState("~");
  const [dirs, setDirs] = useState<string[]>([]);
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const refreshFileTree = useAppStore((s) => s.refreshFileTree);

  // Inline action states
  const [creatingNew, setCreatingNew] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [renamingDir, setRenamingDir] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const newFolderInputRef = useRef<HTMLInputElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  const loadDirs = async (path: string) => {
    setLoading(true);
    try {
      const res = await api.listDirs(path);
      setCurrentPath(res.current);
      setParentPath(res.parent);
      setDirs(res.directories);
    } catch {
      setDirs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      setCreatingNew(false);
      setRenamingDir(null);
      loadDirs("~");
    }
  }, [open]);

  const handleNavigate = (dirName: string) => {
    const sep = currentPath.endsWith("/") ? "" : "/";
    loadDirs(currentPath + sep + dirName);
  };

  const handleGoUp = () => {
    if (parentPath) loadDirs(parentPath);
  };

  const handleSelect = () => {
    onSelect(currentPath);
    onClose();
  };

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  // --- New folder ---
  const handleStartCreate = () => {
    setCreatingNew(true);
    setRenamingDir(null);
    setNewFolderName("");
    setTimeout(() => newFolderInputRef.current?.focus(), 0);
  };

  const handleConfirmCreate = async () => {
    const name = newFolderName.trim();
    if (!name) return;
    setActionLoading(true);
    try {
      const sep = currentPath.endsWith("/") ? "" : "/";
      await api.createDir(currentPath + sep + name);
      await loadDirs(currentPath);
      refreshFileTree();
      setCreatingNew(false);
      setNewFolderName("");
    } catch (e) {
      console.error("Failed to create folder:", e);
    } finally {
      setActionLoading(false);
    }
  };

  // --- Rename ---
  const handleStartRename = (dirName: string) => {
    setCreatingNew(false);
    setRenamingDir(dirName);
    setRenameValue(dirName);
    setTimeout(() => renameInputRef.current?.focus(), 0);
  };

  const handleConfirmRename = async () => {
    const newName = renameValue.trim();
    if (!newName || !renamingDir || newName === renamingDir) {
      setRenamingDir(null);
      return;
    }
    setActionLoading(true);
    try {
      const sep = currentPath.endsWith("/") ? "" : "/";
      await api.renameDir(currentPath + sep + renamingDir, currentPath + sep + newName);
      await loadDirs(currentPath);
      refreshFileTree();
      setRenamingDir(null);
    } catch (e) {
      console.error("Failed to rename folder:", e);
    } finally {
      setActionLoading(false);
    }
  };

  // --- Delete ---
  const handleDelete = async (dirName: string) => {
    const sep = currentPath.endsWith("/") ? "" : "/";
    const fullPath = currentPath + sep + dirName;
    if (!confirm(`Delete folder "${dirName}"? This will delete all contents.`)) return;
    setActionLoading(true);
    try {
      await api.deleteDir(fullPath, true);
      await loadDirs(currentPath);
      refreshFileTree();
    } catch (e) {
      console.error("Failed to delete folder:", e);
    } finally {
      setActionLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center"
      onClick={handleOverlayClick}
    >
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative w-[480px] max-h-[60vh] bg-white rounded-xl shadow-2xl border border-(--color-border) flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-(--color-border) shrink-0">
          <h2 className="text-sm font-semibold">{title}</h2>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-(--color-secondary) transition-colors">
            <X className="w-4 h-4 text-(--color-muted-foreground)" />
          </button>
        </div>

        <div className="flex items-center gap-2 px-4 py-2 border-b border-(--color-border) bg-(--color-muted)/20 text-xs text-(--color-muted-foreground) truncate shrink-0">
          <Folder size={12} className="shrink-0" />
          <span className="truncate">{currentPath}</span>
        </div>

        <div className="flex-1 overflow-y-auto min-h-[200px]">
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 size={20} className="animate-spin text-(--color-muted-foreground)" />
            </div>
          ) : (
            <>
              {parentPath && (
                <button
                  onClick={handleGoUp}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-(--color-secondary) text-(--color-muted-foreground)"
                >
                  <ChevronUp size={16} />
                  <span>..</span>
                </button>
              )}
              {dirs.length === 0 && !parentPath && !creatingNew && (
                <div className="px-4 py-10 text-center text-sm text-(--color-muted-foreground)">
                  No subdirectories
                </div>
              )}
              {dirs.map((d) => (
                <div key={d} className="group flex items-center">
                  {renamingDir === d ? (
                    <div className="flex-1 flex items-center gap-2 px-4 py-2">
                      <Folder size={16} className="text-amber-500 shrink-0" />
                      <input
                        ref={renameInputRef}
                        type="text"
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.nativeEvent.isComposing) return;
                          if (e.key === "Enter") handleConfirmRename();
                          if (e.key === "Escape") setRenamingDir(null);
                        }}
                        className="flex-1 min-w-0 px-2 py-1 text-sm border border-(--color-primary) rounded focus:outline-none"
                        disabled={actionLoading}
                      />
                      <button
                        onClick={handleConfirmRename}
                        className="p-1 rounded hover:bg-(--color-secondary) text-emerald-600"
                        disabled={actionLoading}
                      >
                        <Check size={16} />
                      </button>
                      <button
                        onClick={() => setRenamingDir(null)}
                        className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground)"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  ) : (
                    <>
                      <button
                        onClick={() => handleNavigate(d)}
                        className="flex-1 flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-(--color-secondary) min-w-0"
                      >
                        <Folder size={16} className="text-amber-500 shrink-0" />
                        <span className="truncate">{d}</span>
                        <ChevronRight size={16} className="ml-auto shrink-0 text-(--color-muted-foreground)" />
                      </button>
                      <div className="hidden group-hover:flex items-center gap-1 pr-3 shrink-0">
                        <button
                          onClick={() => handleStartRename(d)}
                          className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground)"
                          title="Rename"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          onClick={() => handleDelete(d)}
                          className="p-1 rounded hover:bg-red-50 text-(--color-muted-foreground) hover:text-red-600"
                          title="Delete"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
              {creatingNew && (
                <div className="flex items-center gap-2 px-4 py-2">
                  <Folder size={16} className="text-amber-500 shrink-0" />
                  <input
                    ref={newFolderInputRef}
                    type="text"
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.nativeEvent.isComposing) return;
                      if (e.key === "Enter") handleConfirmCreate();
                      if (e.key === "Escape") setCreatingNew(false);
                    }}
                    placeholder="Folder name"
                    className="flex-1 min-w-0 px-2 py-1 text-sm border border-(--color-primary) rounded focus:outline-none"
                    disabled={actionLoading}
                  />
                  <button
                    onClick={handleConfirmCreate}
                    className="p-1 rounded hover:bg-(--color-secondary) text-emerald-600"
                    disabled={actionLoading}
                  >
                    <Check size={16} />
                  </button>
                  <button
                    onClick={() => setCreatingNew(false)}
                    className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground)"
                  >
                    <X size={16} />
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        <div className="px-4 py-3 border-t border-(--color-border) flex gap-2 shrink-0">
          <button
            onClick={handleStartCreate}
            className="flex items-center gap-1 px-3 py-2 rounded-lg border border-(--color-border) text-sm hover:bg-(--color-secondary) text-(--color-muted-foreground)"
            disabled={creatingNew}
          >
            <FolderPlus size={14} />
            New Folder
          </button>
          <button
            onClick={handleSelect}
            className="flex-[3] py-2 rounded-lg border border-(--color-border) bg-(--color-primary) text-(--color-primary-foreground) text-sm hover:opacity-90"
          >
            Select This Folder
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-lg border border-(--color-border) text-sm hover:bg-(--color-secondary)"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
