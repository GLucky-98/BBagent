import { useState, useEffect } from "react";
import { Folder, ChevronRight, ChevronUp, Loader2, X } from "lucide-react";
import { api } from "../lib/api";

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

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center"
      onClick={handleOverlayClick}
    >
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative w-[480px] max-h-[60vh] bg-white rounded-xl shadow-2xl border border-[--color-border] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[--color-border] shrink-0">
          <h2 className="text-sm font-semibold">{title}</h2>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-[--color-secondary] transition-colors">
            <X className="w-4 h-4 text-[--color-muted-foreground]" />
          </button>
        </div>

        <div className="flex items-center gap-2 px-4 py-2 border-b border-[--color-border] bg-[--color-muted]/20 text-xs text-[--color-muted-foreground] truncate shrink-0">
          <Folder size={12} className="shrink-0" />
          <span className="truncate">{currentPath}</span>
        </div>

        <div className="flex-1 overflow-y-auto min-h-[200px]">
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 size={20} className="animate-spin text-[--color-muted-foreground]" />
            </div>
          ) : (
            <>
              {parentPath && (
                <button
                  onClick={handleGoUp}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-[--color-secondary] text-[--color-muted-foreground]"
                >
                  <ChevronUp size={16} />
                  <span>..</span>
                </button>
              )}
              {dirs.length === 0 && !parentPath && (
                <div className="px-4 py-10 text-center text-sm text-[--color-muted-foreground]">
                  No subdirectories
                </div>
              )}
              {dirs.map((d) => (
                <button
                  key={d}
                  onClick={() => handleNavigate(d)}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-[--color-secondary]"
                >
                  <Folder size={16} className="text-amber-500 shrink-0" />
                  <span className="truncate">{d}</span>
                  <ChevronRight size={16} className="ml-auto shrink-0 text-[--color-muted-foreground]" />
                </button>
              ))}
            </>
          )}
        </div>

        <div className="px-4 py-3 border-t border-[--color-border] flex gap-2 shrink-0">
          <button
            onClick={handleSelect}
            className="flex-[3] py-2 rounded-lg border border-[--color-border] bg-[--color-primary] text-[--color-primary-foreground] text-sm hover:opacity-90"
          >
            Select This Folder
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-lg border border-[--color-border] text-sm hover:bg-[--color-secondary]"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
