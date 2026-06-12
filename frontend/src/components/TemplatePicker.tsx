import { useState, useEffect } from "react";
import { X, Folder, FileJson, ChevronRight, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { cn } from "../lib/utils";
import type { FileNode } from "../types";

interface TemplatePickerProps {
  open: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
}

export function TemplatePicker({ open, onClose, onSelect }: TemplatePickerProps) {
  const [currentPath, setCurrentPath] = useState("~");
  const [nodes, setNodes] = useState<FileNode[]>([]);
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  const loadTree = async (path: string) => {
    setLoading(true);
    setSelectedFile(null);
    setCurrentPath(path);
    try {
      const data = await api.getFileTree(path, 1);
      const resolvedPath = data.path ?? path;
      setCurrentPath(resolvedPath);
      const lastSep = Math.max(resolvedPath.lastIndexOf("/"), resolvedPath.lastIndexOf("\\"));
      setParentPath(lastSep > 0 ? resolvedPath.substring(0, lastSep) : null);
      setNodes(data.children ?? []);
    } catch {
      setNodes([]);
      const lastSep = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
      setParentPath(lastSep > 0 ? path.substring(0, lastSep) : null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Opening the picker intentionally loads external file-tree data.
      loadTree("./templates");
    }
  }, [open]);

  const handleNavigate = (_name: string, dirPath: string) => {
    loadTree(dirPath);
  };

  const handleFileClick = (filePath: string) => {
    setSelectedFile(filePath === selectedFile ? null : filePath);
  };

  const handleSelect = () => {
    if (selectedFile) {
      onSelect(selectedFile);
      onClose();
    }
  };

  if (!open) return null;

  // Separate dirs and .json files from other files
  const dirs = nodes.filter((n) => n.type === "directory");
  const jsonFiles = nodes.filter(
    (n) => n.type === "file" && n.name.toLowerCase().endsWith(".json")
  );
  const otherFiles = nodes.filter(
    (n) => n.type === "file" && !n.name.toLowerCase().endsWith(".json")
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-(--color-background) rounded-2xl shadow-[-8px_8px_24px_rgba(0,0,0,0.08)] overflow-hidden flex flex-col max-h-[70vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-(--color-border) shrink-0">
          <div>
            <h3 className="text-base font-semibold">Select Template File</h3>
            <p className="text-xs text-(--color-muted-foreground) mt-0.5 truncate max-w-[300px]">
              {currentPath}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-(--color-secondary) transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body: file list */}
        <div className="flex-1 overflow-y-auto p-3 space-y-0.5 min-h-[200px]">
          {/* Go up */}
          {parentPath !== null && (
            <button
              onClick={() => loadTree(parentPath)}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-(--color-muted-foreground) hover:bg-(--color-secondary) rounded transition-colors"
            >
              <ChevronRight className="w-3.5 h-3.5 rotate-180" />
              ..
            </button>
          )}

          {loading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-(--color-muted-foreground)" />
            </div>
          )}

          {!loading && nodes.length === 0 && (
            <div className="py-8 text-center text-sm text-(--color-muted-foreground)">
              This directory is empty
            </div>
          )}

          {/* Directories */}
          {dirs.map((dir) => (
            <button
              key={dir.path}
              onClick={() => handleNavigate(dir.name, dir.path)}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-(--color-secondary) rounded transition-colors"
            >
              <Folder className="w-4 h-4 text-amber-500 shrink-0" />
              <span className="truncate">{dir.name}</span>
            </button>
          ))}

          {/* JSON files (selectable) */}
          {jsonFiles.map((file) => {
            const isSelected = selectedFile === file.path;
            return (
              <button
                key={file.path}
                onClick={() => handleFileClick(file.path)}
                className={cn(
                  "w-full flex items-center gap-2 px-3 py-1.5 text-sm rounded transition-colors",
                  isSelected
                    ? "bg-(--color-primary)/10 border border-(--color-primary)/30"
                    : "hover:bg-(--color-secondary)"
                )}
              >
                <FileJson className="w-4 h-4 text-blue-500 shrink-0" />
                <span className="truncate">{file.name}</span>
                {isSelected && (
                  <span className="ml-auto text-xs text-(--color-primary) font-medium">
                    Selected
                  </span>
                )}
              </button>
            );
          })}

          {/* Other files (not selectable, shown dimmed) */}
          {otherFiles.map((file) => (
            <div
              key={file.path}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-(--color-muted-foreground) opacity-50 cursor-not-allowed"
            >
              <FileJson className="w-4 h-4 shrink-0" />
              <span className="truncate">{file.name}</span>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-6 py-4 border-t border-(--color-border) shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-(--color-border) hover:bg-(--color-secondary) text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleSelect}
            disabled={!selectedFile}
            className="px-4 py-2 rounded-lg border border-(--color-primary) bg-(--color-primary) text-(--color-primary-foreground) text-sm hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Select
          </button>
        </div>
      </div>
    </div>
  );
}
