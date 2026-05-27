import { ChevronRight, Folder, FolderOpen, File as FileIcon } from "lucide-react";
import { useAppStore } from "../../store";
import { cn } from "../../lib/utils";
import type { FileNode } from "../../types";

interface TreeNodeProps {
  node: FileNode;
  depth: number;
  expandedPaths: Set<string>;
  onToggleExpand: (path: string) => void;
}

function TreeNode({
  node,
  depth,
  expandedPaths,
  onToggleExpand,
}: TreeNodeProps) {
  const openFilePreview = useAppStore((s) => s.openFilePreview);
  const setWorkingDirPath = useAppStore((s) => s.setWorkingDirPath);
  const isExpanded = expandedPaths.has(node.path);
  const indent = depth * 16;

  if (node.type === "directory") {
    return (
      <>
        <div
          className={cn(
            "flex items-center gap-1 px-2 py-1 cursor-pointer hover:bg-[--color-secondary]/50 text-sm select-none"
          )}
          style={{ paddingLeft: indent + 8 }}
          onClick={() => {
            onToggleExpand(node.path);
            setWorkingDirPath(node.path);
          }}
        >
          <ChevronRight
            className={cn(
              "w-3.5 h-3.5 shrink-0 transition-transform",
              isExpanded && "rotate-90"
            )}
          />
          {isExpanded ? (
            <FolderOpen className="w-4 h-4 text-amber-500 shrink-0" />
          ) : (
            <Folder className="w-4 h-4 text-amber-500 shrink-0" />
          )}
          <span className="truncate">{node.name}</span>
        </div>
        {isExpanded &&
          node.children?.map((child) => (
            <TreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              expandedPaths={expandedPaths}
              onToggleExpand={onToggleExpand}
            />
          ))}
      </>
    );
  }

  return (
    <div
      className={cn(
        "flex items-center gap-1 px-2 py-1 cursor-pointer hover:bg-[--color-secondary]/50 text-sm select-none"
      )}
      style={{ paddingLeft: indent + 8 }}
      onClick={() => {
        const mimeType = getMimeTypeFromName(node.name);
        openFilePreview({
          path: node.path,
          name: node.name,
          content: `// Preview of ${node.path}\n// File content would be loaded from server`,
          mimeType,
        });
      }}
    >
      <span className="w-3.5 h-3.5 shrink-0" />
      <FileIcon className="w-4 h-4 text-[--color-muted-foreground] shrink-0" />
      <span className="truncate">{node.name}</span>
    </div>
  );
}

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
    ".env": "text/plain",
    ".gitignore": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
  };
  return map[ext] ?? "text/plain";
}

const mockFileTree: FileNode = {
  name: "workspace",
  path: "/workspace",
  type: "directory",
  children: [
    {
      name: "src",
      path: "/workspace/src",
      type: "directory",
      children: [
        {
          name: "components",
          path: "/workspace/src/components",
          type: "directory",
          children: [
            {
              name: "App.tsx",
              path: "/workspace/src/components/App.tsx",
              type: "file",
              extension: ".tsx",
            },
            {
              name: "ChatWindow.tsx",
              path: "/workspace/src/components/ChatWindow.tsx",
              type: "file",
              extension: ".tsx",
            },
          ],
        },
        {
          name: "utils.ts",
          path: "/workspace/src/utils.ts",
          type: "file",
          extension: ".ts",
        },
        {
          name: "index.ts",
          path: "/workspace/src/index.ts",
          type: "file",
          extension: ".ts",
        },
      ],
    },
    {
      name: "public",
      path: "/workspace/public",
      type: "directory",
      children: [
        {
          name: "index.html",
          path: "/workspace/public/index.html",
          type: "file",
          extension: ".html",
        },
      ],
    },
    {
      name: "package.json",
      path: "/workspace/package.json",
      type: "file",
      extension: ".json",
    },
    {
      name: "tsconfig.json",
      path: "/workspace/tsconfig.json",
      type: "file",
      extension: ".json",
    },
    {
      name: "README.md",
      path: "/workspace/README.md",
      type: "file",
      extension: ".md",
    },
  ],
};

export function BasedirTree() {
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const agents = useAppStore((s) => s.agents);
  const expandedPaths = useAppStore((s) => s.basedirExpandedPaths);
  const toggleExpand = useAppStore((s) => s.toggleBasedirExpand);

  const agent = agents.find((a) => a.id === activeAgentId);
  const rootPath = agent?.basePath ?? mockFileTree.path;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-[--color-muted-foreground] border-b border-[--color-border] shrink-0">
        <FolderOpen className="w-3.5 h-3.5" />
        <span className="truncate">{rootPath}</span>
      </div>

      <div className="flex-1 overflow-y-auto py-1">
        <TreeNode
          node={mockFileTree}
          depth={0}
          expandedPaths={expandedPaths}
          onToggleExpand={toggleExpand}
        />
      </div>
    </div>
  );
}
