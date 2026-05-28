import { useState } from "react";
import {
  Folder,
  File as FileIcon,
  Search,
  ChevronRight,
  RefreshCw,
} from "lucide-react";
import { useAppStore } from "../../store";
import { cn } from "../../lib/utils";
import type { FileNode } from "../../types";

const mockEntries: FileNode[] = [
  {
    name: "App",
    path: "/workspace/src/App",
    type: "directory",
    children: [],
  },
  {
    name: "hooks",
    path: "/workspace/src/hooks",
    type: "directory",
    children: [],
  },
  {
    name: "Button.tsx",
    path: "/workspace/src/Button.tsx",
    type: "file",
    extension: ".tsx",
  },
  {
    name: "Modal.tsx",
    path: "/workspace/src/Modal.tsx",
    type: "file",
    extension: ".tsx",
  },
  {
    name: "index.ts",
    path: "/workspace/src/index.ts",
    type: "file",
    extension: ".ts",
  },
  {
    name: "types.ts",
    path: "/workspace/src/types.ts",
    type: "file",
    extension: ".ts",
  },
];

function getMimeTypeFromName(fileName: string): string {
  const ext = fileName.substring(fileName.lastIndexOf(".")).toLowerCase();
  const map: Record<string, string> = {
    ".ts": "text/typescript",
    ".tsx": "text/typescript",
    ".js": "text/javascript",
    ".jsx": "text/javascript",
    ".py": "text/x-python",
    ".json": "application/json",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".md": "text/markdown",
    ".css": "text/css",
    ".html": "text/html",
    ".txt": "text/plain",
  };
  return map[ext] ?? "text/plain";
}

export function WorkingDirView() {
  const workingDirPath = useAppStore((s) => s.workingDirPath);
  const openFilePreview = useAppStore((s) => s.openFilePreview);
  const [filter, setFilter] = useState("");

  const filtered = mockEntries.filter((entry) =>
    entry.name.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-1 px-3 py-1.5 border-b border-[--color-border] shrink-0">
        <span className="text-[10px] text-[--color-muted-foreground] uppercase tracking-wide mr-1">Working Dir</span>
        <span className="text-xs text-[--color-muted-foreground] truncate flex-1">
          {workingDirPath || "Not set"}
        </span>
        <button className="p-0.5 rounded hover:bg-[--color-secondary] text-[--color-muted-foreground]">
          <RefreshCw className="w-3 h-3" />
        </button>
      </div>

      <div className="flex items-center gap-1 px-2 py-1 border-b border-[--color-border] shrink-0">
        <Search className="w-3 h-3 text-[--color-muted-foreground]" />
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter files..."
          className="flex-1 text-xs bg-transparent outline-none placeholder:text-[--color-muted-foreground]/50"
        />
      </div>

      <div className="flex-1 overflow-y-auto">
        {filtered.map((entry) => (
          <div
            key={entry.path}
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-[--color-secondary]/50 text-sm select-none"
            )}
            onClick={() => {
              if (entry.type === "file") {
                const mimeType = getMimeTypeFromName(entry.name);
                openFilePreview({
                  path: entry.path,
                  name: entry.name,
                  content: `// Preview of ${entry.name}\n// File content would be loaded from server`,
                  mimeType,
                });
              }
            }}
          >
            {entry.type === "directory" ? (
              <>
                <Folder className="w-4 h-4 text-amber-500 shrink-0" />
                <span className="truncate flex-1">{entry.name}</span>
                <ChevronRight className="w-3.5 h-3.5 text-[--color-muted-foreground]" />
              </>
            ) : (
              <>
                <FileIcon className="w-4 h-4 text-[--color-muted-foreground] shrink-0" />
                <span className="truncate flex-1">{entry.name}</span>
                <span className="text-xs text-[--color-muted-foreground]">
                  {entry.extension}
                </span>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
