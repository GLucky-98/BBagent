import { useState, useEffect, useRef } from "react";
import {
  ChevronRight,
  Folder,
  FolderOpen,
  File as FileIcon,
  Copy,
  ExternalLink,
  Loader2,
  FolderPlus,
  Pencil,
  Trash2,
  Check,
  X,
} from "lucide-react";
import { useAppStore } from "../../store";
import { api } from "../../lib/api";
import { cn, getMimeType } from "../../lib/utils";
import type { FileNode } from "../../types";

interface TreeNodeProps {
  node: FileNode;
  depth: number;
  expandedPaths: Set<string>;
  onToggleExpand: (path: string) => void;
  renamingPath: string | null;
  renameValue: string;
  onStartRename: (path: string, name: string) => void;
  onRenameValueChange: (value: string) => void;
  onConfirmRename: () => void;
  onCancelRename: () => void;
  onDelete: (path: string, name: string) => void;
  renameInputRef: React.RefObject<HTMLInputElement | null>;
}

function TreeNode({
  node,
  depth,
  expandedPaths,
  onToggleExpand,
  renamingPath,
  renameValue,
  onStartRename,
  onRenameValueChange,
  onConfirmRename,
  onCancelRename,
  onDelete,
  renameInputRef,
}: TreeNodeProps) {
  const openFilePreview = useAppStore((s) => s.openFilePreview);
  const isExpanded = expandedPaths.has(node.path);
  const indent = depth * 16;

  if (node.type === "directory") {
    const isRenaming = renamingPath === node.path;

    return (
      <>
        <div
          className={cn(
            "group flex items-center gap-1 px-2 py-1 cursor-pointer hover:bg-black/5 text-[13px] select-none rounded-sm"
          )}
          style={{ paddingLeft: indent + 8 }}
          draggable={!isRenaming}
          onDragStart={(e) => {
            e.dataTransfer.setData("text/plain", node.path);
            e.dataTransfer.effectAllowed = "copy";
          }}
        >
          <ChevronRight
            className={cn(
              "w-3.5 h-3.5 shrink-0 transition-transform",
              isExpanded && "rotate-90"
            )}
            onClick={() => onToggleExpand(node.path)}
          />
          {isExpanded ? (
            <FolderOpen className="w-4 h-4 text-amber-500 shrink-0" onClick={() => onToggleExpand(node.path)} />
          ) : (
            <Folder className="w-4 h-4 text-amber-500 shrink-0" onClick={() => onToggleExpand(node.path)} />
          )}
          {isRenaming ? (
            <>
              <input
                ref={renameInputRef}
                type="text"
                value={renameValue}
                onChange={(e) => onRenameValueChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.nativeEvent.isComposing) return;
                  if (e.key === "Enter") onConfirmRename();
                  if (e.key === "Escape") onCancelRename();
                }}
                onClick={(e) => e.stopPropagation()}
                className="flex-1 min-w-0 px-1 py-0.5 text-[13px] border border-(--color-primary) rounded focus:outline-none bg-white"
              />
              <button
                onClick={(e) => { e.stopPropagation(); onConfirmRename(); }}
                className="p-0.5 rounded hover:bg-(--color-secondary) text-emerald-600 shrink-0"
              >
                <Check size={13} />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onCancelRename(); }}
                className="p-0.5 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground) shrink-0"
              >
                <X size={13} />
              </button>
            </>
          ) : (
            <>
              <span className="truncate flex-1 min-w-0" onClick={() => onToggleExpand(node.path)}>{node.name}</span>
              <div className="hidden group-hover:flex items-center gap-0.5 shrink-0">
                <button
                  onClick={(e) => { e.stopPropagation(); onStartRename(node.path, node.name); }}
                  className="p-0.5 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground)"
                  title="Rename"
                >
                  <Pencil size={12} />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onDelete(node.path, node.name); }}
                  className="p-0.5 rounded hover:bg-red-50 text-(--color-muted-foreground) hover:text-red-600"
                  title="Delete"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </>
          )}
        </div>
        {isExpanded &&
          node.children?.map((child) => (
            <TreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              expandedPaths={expandedPaths}
              onToggleExpand={onToggleExpand}
              renamingPath={renamingPath}
              renameValue={renameValue}
              onStartRename={onStartRename}
              onRenameValueChange={onRenameValueChange}
              onConfirmRename={onConfirmRename}
              onCancelRename={onCancelRename}
              onDelete={onDelete}
              renameInputRef={renameInputRef}
            />
          ))}
      </>
    );
  }

  return (
    <div
      className={cn(
        "flex items-center gap-1 px-2 py-1 cursor-pointer hover:bg-black/5 text-[13px] select-none rounded-sm"
      )}
      style={{ paddingLeft: indent + 8 }}
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", node.path);
        e.dataTransfer.effectAllowed = "copy";
      }}
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

export function WorkingDirView() {
  const workingDirPath = useAppStore((s) => s.workingDirPath);
  const expandedPaths = useAppStore((s) => s.workingDirExpandedPaths);
  const toggleExpand = useAppStore((s) => s.toggleWorkingDirExpand);
  const refreshKey = useAppStore((s) => s.workingDirRefreshKey);
  const [fileTree, setFileTree] = useState<FileNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  // Inline action states
  const [creatingNew, setCreatingNew] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [renamingPath, setRenamingPath] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const newFolderInputRef = useRef<HTMLInputElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!workingDirPath) return;
    let ignore = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Working directory changes trigger an external file-tree refresh with local loading state.
    setLoading(true);
    api
      .getFileTree(workingDirPath)
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
  }, [workingDirPath, refreshKey]);

  const handleCopy = async () => {
    if (!workingDirPath) return;
    try {
      await navigator.clipboard.writeText(workingDirPath);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback: ignore clipboard errors
    }
  };

  // --- New folder ---
  const handleStartCreate = () => {
    setCreatingNew(true);
    setRenamingPath(null);
    setNewFolderName("");
    setTimeout(() => newFolderInputRef.current?.focus(), 0);
  };

  const handleConfirmCreate = async () => {
    const name = newFolderName.trim();
    if (!name || !workingDirPath) return;
    setActionLoading(true);
    try {
      await api.createDir(workingDirPath + "/" + name);
      setCreatingNew(false);
      setNewFolderName("");
    } catch (e) {
      console.error("Failed to create folder:", e);
    } finally {
      setActionLoading(false);
    }
  };

  // --- Rename ---
  const handleStartRename = (path: string, name: string) => {
    setCreatingNew(false);
    setRenamingPath(path);
    setRenameValue(name);
    setTimeout(() => renameInputRef.current?.focus(), 0);
  };

  const handleConfirmRename = async () => {
    const newName = renameValue.trim();
    if (!newName || !renamingPath) return;
    const parentPath = renamingPath.substring(0, renamingPath.lastIndexOf("/"));
    if (newName === renamingPath.substring(renamingPath.lastIndexOf("/") + 1)) {
      setRenamingPath(null);
      return;
    }
    setActionLoading(true);
    try {
      await api.renameDir(renamingPath, parentPath + "/" + newName);
      setRenamingPath(null);
    } catch (e) {
      console.error("Failed to rename folder:", e);
    } finally {
      setActionLoading(false);
    }
  };

  // --- Delete ---
  const handleDelete = async (path: string, name: string) => {
    if (!confirm(`Delete "${name}"? This will delete all contents.`)) return;
    setActionLoading(true);
    try {
      await api.deleteDir(path, true);
    } catch (e) {
      console.error("Failed to delete:", e);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-(--color-border) shrink-0">
        <span className="text-[10.5px] font-semibold uppercase tracking-[0.04em] text-(--color-ink-3)">Working Dir</span>
        <span className="truncate">{workingDirPath || "Not set"}</span>
        <div className="flex items-center gap-0.5 ml-auto shrink-0">
          <button
            className="p-0.5 rounded hover:bg-(--color-secondary) transition-colors"
            onClick={handleStartCreate}
            title="New Folder"
            disabled={!workingDirPath}
          >
            <FolderPlus className="w-3 h-3" />
          </button>
          <button
            className="p-0.5 rounded hover:bg-(--color-secondary) transition-colors"
            onClick={() => workingDirPath && api.openPath(workingDirPath)}
            title="Open in Finder"
          >
            <ExternalLink className="w-3 h-3" />
          </button>
          <button
            className={cn(
              "p-0.5 rounded hover:bg-(--color-secondary) transition-colors",
              copied && "text-emerald-500"
            )}
            onClick={handleCopy}
            title="Copy path"
          >
            <Copy className="w-3 h-3" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto py-1">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-(--color-muted-foreground)" />
          </div>
        ) : !workingDirPath ? (
          <div className="px-3 py-8 text-center text-xs text-(--color-muted-foreground)">
            No working directory set
          </div>
        ) : !fileTree ? (
          <div className="px-3 py-8 text-center text-xs text-(--color-muted-foreground)">
            Unable to load file tree
          </div>
        ) : (
          <>
            {creatingNew && (
              <div className="flex items-center gap-1 px-2 py-1" style={{ paddingLeft: 8 }}>
                <Folder className="w-4 h-4 text-amber-500 shrink-0" />
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
                  className="flex-1 min-w-0 px-1 py-0.5 text-[13px] border border-(--color-primary) rounded focus:outline-none bg-white"
                  disabled={actionLoading}
                />
                <button
                  onClick={handleConfirmCreate}
                  className="p-0.5 rounded hover:bg-(--color-secondary) text-emerald-600"
                  disabled={actionLoading}
                >
                  <Check size={13} />
                </button>
                <button
                  onClick={() => setCreatingNew(false)}
                  className="p-0.5 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground)"
                >
                  <X size={13} />
                </button>
              </div>
            )}
            {fileTree.children?.map((child) => (
              <TreeNode
                key={child.path}
                node={child}
                depth={0}
                expandedPaths={expandedPaths}
                onToggleExpand={toggleExpand}
                renamingPath={renamingPath}
                renameValue={renameValue}
                onStartRename={handleStartRename}
                onRenameValueChange={setRenameValue}
                onConfirmRename={handleConfirmRename}
                onCancelRename={() => setRenamingPath(null)}
                onDelete={handleDelete}
                renameInputRef={renameInputRef}
              />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
