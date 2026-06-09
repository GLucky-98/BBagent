import { useState, useEffect, useRef } from "react";
import {
  Folder,
  FolderOpen,
  ChevronRight,
  ChevronUp,
  Loader2,
  FolderPlus,
  Pencil,
  Trash2,
  Check,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import { useAppStore } from "../store";

interface FolderPickerProps {
  value: string;
  onChange: (path: string) => void;
  placeholder?: string;
}

export function FolderPicker({ value, onChange, placeholder }: FolderPickerProps) {
  const [open, setOpen] = useState(false);
  const [currentPath, setCurrentPath] = useState(value || "~");
  const [dirs, setDirs] = useState<string[]>([]);
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
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

  const handleOpen = () => {
    setOpen(true);
    setCreatingNew(false);
    setRenamingDir(null);
    loadDirs(value || "~");
  };

  const handleNavigate = (dirName: string) => {
    const sep = currentPath.endsWith("/") ? "" : "/";
    const newPath = currentPath + sep + dirName;
    loadDirs(newPath);
  };

  const handleGoUp = () => {
    if (parentPath) loadDirs(parentPath);
  };

  const handleSelect = () => {
    onChange(currentPath);
    setOpen(false);
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

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <div className="relative" ref={dropdownRef}>
      <div className="flex gap-1">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="flex-1 px-3 py-2 rounded-lg border border-(--color-border) bg-white focus:outline-none focus:ring-2 focus:ring-(--color-ring)"
        />
        <button
          type="button"
          onClick={handleOpen}
          className="px-3 py-2 rounded-lg border border-(--color-border) hover:bg-(--color-secondary) transition-colors"
          title="Browse folders"
        >
          <FolderOpen size={16} />
        </button>
      </div>

      {open && (
        <div className="absolute z-50 left-0 right-0 mt-1 bg-white border border-(--color-border) rounded-lg shadow-lg max-h-[280px] flex flex-col">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-(--color-border) bg-(--color-muted)/20 text-xs text-(--color-muted-foreground) truncate">
            <Folder size={12} className="shrink-0" />
            <span className="truncate">{currentPath}</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 size={16} className="animate-spin text-(--color-muted-foreground)" />
              </div>
            ) : (
              <>
                {parentPath && (
                  <button
                    onClick={handleGoUp}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-(--color-secondary) text-(--color-muted-foreground)"
                  >
                    <ChevronUp size={14} />
                    <span>..</span>
                  </button>
                )}
                {dirs.length === 0 && !parentPath && !creatingNew && (
                  <div className="px-3 py-6 text-center text-xs text-(--color-muted-foreground)">
                    No subdirectories
                  </div>
                )}
                {dirs.map((d) => (
                  <div key={d} className="group flex items-center">
                    {renamingDir === d ? (
                      <div className="flex-1 flex items-center gap-1 px-2 py-1.5">
                        <Folder size={14} className="text-amber-500 shrink-0" />
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
                      className="flex-1 min-w-0 px-1.5 py-0.5 text-sm border border-(--color-primary) rounded focus:outline-none"
                      disabled={actionLoading}
                    />
                    <button
                      onClick={handleConfirmRename}
                      className="p-0.5 rounded hover:bg-(--color-secondary) text-emerald-600"
                          disabled={actionLoading}
                        >
                          <Check size={14} />
                        </button>
                        <button
                          onClick={() => setRenamingDir(null)}
                          className="p-0.5 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground)"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ) : (
                      <>
                        <button
                          onClick={() => handleNavigate(d)}
                          className="flex-1 flex items-center gap-2 px-3 py-2 text-sm hover:bg-(--color-secondary) min-w-0"
                        >
                          <Folder size={14} className="text-amber-500 shrink-0" />
                          <span className="truncate">{d}</span>
                          <ChevronRight size={14} className="ml-auto shrink-0 text-(--color-muted-foreground)" />
                        </button>
                        <div className="hidden group-hover:flex items-center gap-0.5 pr-2 shrink-0">
                          <button
                            onClick={() => handleStartRename(d)}
                            className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground)"
                            title="Rename"
                          >
                            <Pencil size={12} />
                          </button>
                          <button
                            onClick={() => handleDelete(d)}
                            className="p-1 rounded hover:bg-red-50 text-(--color-muted-foreground) hover:text-red-600"
                            title="Delete"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                ))}
                {creatingNew && (
                  <div className="flex items-center gap-1 px-2 py-1.5">
                    <Folder size={14} className="text-amber-500 shrink-0" />
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
                      className="flex-1 min-w-0 px-1.5 py-0.5 text-sm border border-(--color-primary) rounded focus:outline-none"
                      disabled={actionLoading}
                    />
                    <button
                      onClick={handleConfirmCreate}
                      className="p-0.5 rounded hover:bg-(--color-secondary) text-emerald-600"
                      disabled={actionLoading}
                    >
                      <Check size={14} />
                    </button>
                    <button
                      onClick={() => setCreatingNew(false)}
                      className="p-0.5 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground)"
                    >
                      <X size={14} />
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
          <div className="px-3 py-2 border-t border-(--color-border) flex gap-1.5">
            <button
              onClick={handleStartCreate}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg border border-(--color-border) text-xs hover:bg-(--color-secondary) text-(--color-muted-foreground)"
              disabled={creatingNew}
            >
              <FolderPlus size={13} />
              New Folder
            </button>
            <button
              onClick={handleSelect}
              className="flex-1 py-1.5 rounded-lg border border-(--color-border) bg-(--color-primary) text-(--color-primary-foreground) text-xs hover:opacity-90"
            >
              Select This Folder
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
