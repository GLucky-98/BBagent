import { useState, useEffect } from "react";
import {
  Folder,
  File as FileIcon,
  Search,
  ChevronRight,
  RefreshCw,
  Loader2,
} from "lucide-react";
import { useAppStore } from "../../store";
import { api } from "../../lib/api";
import { cn, getMimeType } from "../../lib/utils";
import type { FileNode } from "../../types";

export function WorkingDirView() {
  const workingDirPath = useAppStore((s) => s.workingDirPath);
  const openFilePreview = useAppStore((s) => s.openFilePreview);
  const [filter, setFilter] = useState("");
  const [entries, setEntries] = useState<FileNode[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!workingDirPath) return;
    let ignore = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    api
      .getFileTree(workingDirPath)
      .then((tree: FileNode) => {
        if (ignore) return;
        setEntries(tree.children || []);
        setLoading(false);
      })
      .catch(() => {
        if (ignore) return;
        setEntries([]);
        setLoading(false);
      });
    return () => { ignore = true; };
  }, [workingDirPath]);

  const handleRefresh = () => {
    if (!workingDirPath) return;
    setLoading(true);
    api
      .getFileTree(workingDirPath)
      .then((tree: FileNode) => {
        setEntries(tree.children || []);
      })
      .catch(() => {
        setEntries([]);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  const handleOpenFile = async (entry: FileNode) => {
    const mimeType = getMimeType(entry.name);
    openFilePreview({
      path: entry.path,
      name: entry.name,
      content: null,
      mimeType,
    });
    try {
      const data = await api.readFile(entry.path);
      openFilePreview({
        path: entry.path,
        name: entry.name,
        content: data.content ?? data,
        mimeType,
      });
    } catch (err) {
      openFilePreview({
        path: entry.path,
        name: entry.name,
        content: null,
        mimeType,
        error: err instanceof Error ? err.message : "Failed to read file",
      });
    }
  };

  const filtered = entries.filter((entry) =>
    entry.name.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-1 px-3 py-1.5 border-b border-(--color-border) shrink-0">
        <span className="text-[10px] text-(--color-muted-foreground) uppercase tracking-wide mr-1">Working Dir</span>
        <span className="text-xs text-(--color-muted-foreground) truncate flex-1">
          {workingDirPath || "Not set"}
        </span>
        <button className="p-0.5 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground)" onClick={handleRefresh}>
          <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} />
        </button>
      </div>

      <div className="flex items-center gap-1 px-2 py-1 border-b border-(--color-border) shrink-0">
        <Search className="w-3 h-3 text-(--color-muted-foreground)" />
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter files..."
          className="flex-1 text-xs bg-transparent outline-none placeholder:text-(--color-muted-foreground)/50"
        />
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-(--color-muted-foreground)" />
          </div>
        ) : !workingDirPath ? (
          <div className="px-3 py-8 text-center text-xs text-(--color-muted-foreground)">
            No working directory set
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-3 py-8 text-center text-xs text-(--color-muted-foreground)">
            {filter ? "No matching entries" : "Empty directory"}
          </div>
        ) : (
          filtered.map((entry) => (
            <div
              key={entry.path}
              className={cn(
                "flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-(--color-secondary)/50 text-sm select-none"
              )}
              onClick={() => {
                if (entry.type === "file") {
                  handleOpenFile(entry);
                }
              }}
            >
              {entry.type === "directory" ? (
                <>
                  <Folder className="w-4 h-4 text-amber-500 shrink-0" />
                  <span className="truncate flex-1">{entry.name}</span>
                  <ChevronRight className="w-3.5 h-3.5 text-(--color-muted-foreground)" />
                </>
              ) : (
                <>
                  <FileIcon className="w-4 h-4 text-(--color-muted-foreground) shrink-0" />
                  <span className="truncate flex-1">{entry.name}</span>
                  <span className="text-xs text-(--color-muted-foreground)">
                    {entry.extension}
                  </span>
                </>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
