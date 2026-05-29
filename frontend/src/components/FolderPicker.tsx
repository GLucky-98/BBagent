import { useState, useEffect, useRef } from "react";
import { Folder, FolderOpen, ChevronRight, ChevronUp, Loader2 } from "lucide-react";
import { api } from "../lib/api";

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
          className="flex-1 px-3 py-2 rounded-lg border border-[--color-border] bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]"
        />
        <button
          type="button"
          onClick={handleOpen}
          className="px-3 py-2 rounded-lg border border-[--color-border] hover:bg-[--color-secondary] transition-colors"
          title="Browse folders"
        >
          <FolderOpen size={16} />
        </button>
      </div>

      {open && (
        <div className="absolute z-50 left-0 right-0 mt-1 bg-white border border-[--color-border] rounded-lg shadow-lg max-h-[220px] flex flex-col">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-[--color-border] bg-[--color-muted]/20 text-xs text-[--color-muted-foreground] truncate">
            <Folder size={12} className="shrink-0" />
            <span className="truncate">{currentPath}</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 size={16} className="animate-spin text-[--color-muted-foreground]" />
              </div>
            ) : (
              <>
                {parentPath && (
                  <button
                    onClick={handleGoUp}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-[--color-secondary] text-[--color-muted-foreground]"
                  >
                    <ChevronUp size={14} />
                    <span>..</span>
                  </button>
                )}
                {dirs.length === 0 && !parentPath && (
                  <div className="px-3 py-6 text-center text-xs text-[--color-muted-foreground]">
                    No subdirectories
                  </div>
                )}
                {dirs.map((d) => (
                  <button
                    key={d}
                    onClick={() => handleNavigate(d)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-[--color-secondary]"
                  >
                    <Folder size={14} className="text-amber-500 shrink-0" />
                    <span className="truncate">{d}</span>
                    <ChevronRight size={14} className="ml-auto shrink-0 text-[--color-muted-foreground]" />
                  </button>
                ))}
              </>
            )}
          </div>
          <div className="px-3 py-2 border-t border-[--color-border]">
            <button
              onClick={handleSelect}
              className="w-full py-1.5 rounded-lg border border-[--color-border] bg-[--color-primary] text-[--color-primary-foreground] text-xs hover:opacity-90"
            >
              Select This Folder
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
