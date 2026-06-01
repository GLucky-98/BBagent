import { useState, useEffect } from "react";
import { ChevronRight, Folder, FolderOpen, File as FileIcon, Loader2 } from "lucide-react";
import { useAppStore } from "../../store";
import { api } from "../../lib/api";
import { cn, getMimeType } from "../../lib/utils";
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
  const isExpanded = expandedPaths.has(node.path);
  const indent = depth * 16;

  if (node.type === "directory") {
    return (
      <>
        <div
          className={cn(
            "flex items-center gap-1 px-2 py-1 cursor-pointer hover:bg-(--color-secondary)/50 text-sm select-none"
          )}
          style={{ paddingLeft: indent + 8 }}
          onClick={() => {
            onToggleExpand(node.path);
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
        "flex items-center gap-1 px-2 py-1 cursor-pointer hover:bg-(--color-secondary)/50 text-sm select-none"
      )}
      style={{ paddingLeft: indent + 8 }}
      onClick={async () => {
        const mimeType = getMimeType(node.name);
        openFilePreview({
          path: node.path,
          name: node.name,
          content: null,
          mimeType,
        });
        try {
          const data = await api.readFile(node.path);
          openFilePreview({
            path: node.path,
            name: node.name,
            content: data.content ?? data,
            mimeType,
          });
        } catch (err) {
          openFilePreview({
            path: node.path,
            name: node.name,
            content: null,
            mimeType,
            error: err instanceof Error ? err.message : "Failed to read file",
          });
        }
      }}
    >
      <span className="w-3.5 h-3.5 shrink-0" />
      <FileIcon className="w-4 h-4 text-(--color-muted-foreground) shrink-0" />
      <span className="truncate">{node.name}</span>
    </div>
  );
}

export function BasedirTree() {
  const activeAgentName = useAppStore((s) => s.activeAgentName);
  const agents = useAppStore((s) => s.agents);
  const expandedPaths = useAppStore((s) => s.basedirExpandedPaths);
  const toggleExpand = useAppStore((s) => s.toggleBasedirExpand);
  const [fileTree, setFileTree] = useState<FileNode | null>(null);
  const [loading, setLoading] = useState(false);

  const agent = agents.find((a) => a.name === activeAgentName);
  const basePath = agent?.basePath;

  useEffect(() => {
    if (!basePath) return;
    let ignore = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    api
      .getFileTree(basePath)
      .then((tree: FileNode) => {
        if (ignore) return;
        setFileTree(tree);
        setLoading(false);
      })
      .catch(() => {
        if (ignore) return;
        setFileTree(null);
        setLoading(false);
      });
    return () => { ignore = true; };
  }, [basePath]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-(--color-muted-foreground) border-b border-(--color-border) shrink-0">
        <span className="text-[10px] text-(--color-muted-foreground) uppercase tracking-wide mr-1">Base Path</span>
        <FolderOpen className="w-3.5 h-3.5" />
        <span className="truncate">{basePath || "Not set"}</span>
      </div>

      <div className="flex-1 overflow-y-auto py-1">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-(--color-muted-foreground)" />
          </div>
        ) : !basePath ? (
          <div className="px-3 py-8 text-center text-xs text-(--color-muted-foreground)">
            No agent selected
          </div>
        ) : !fileTree ? (
          <div className="px-3 py-8 text-center text-xs text-(--color-muted-foreground)">
            Unable to load file tree
          </div>
        ) : (
          <TreeNode
            node={fileTree}
            depth={0}
            expandedPaths={expandedPaths}
            onToggleExpand={toggleExpand}
          />
        )}
      </div>
    </div>
  );
}
