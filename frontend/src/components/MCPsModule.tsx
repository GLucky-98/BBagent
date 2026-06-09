import { useState } from "react";
import { Server, Plus, FolderOpen, X, Trash2, RefreshCw, Pencil } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import type { MCPServer } from "../types";
import { FolderPickerModal } from "./FolderPickerModal";

const ACTIVE_CLASS = "bg-(--color-primary)/10 text-(--color-primary) font-semibold shadow-[inset_4px_0_0_0_#3b82f6]";

const INITIAL_ENV_ROWS = 3;

function ServerForm({ onClose, editServer }: { onClose: () => void; editServer?: MCPServer }) {
  const addMcpServer = useAppStore((s) => s.addMcpServer);
  const updateMcpServer = useAppStore((s) => s.updateMcpServer);

  const [name, setName] = useState(editServer?.name ?? "");
  const [command, setCommand] = useState(editServer?.command ?? "");
  const [args, setArgs] = useState(editServer?.args.join(" ") ?? "");
  const existingEnv = editServer?.env ?? {};
  const envKeys = Object.keys(existingEnv);
  const initialRows = envKeys.length >= INITIAL_ENV_ROWS
    ? envKeys.map((k) => ({ key: k, value: existingEnv[k] }))
    : [
        ...envKeys.map((k) => ({ key: k, value: existingEnv[k] })),
        ...Array.from({ length: INITIAL_ENV_ROWS - envKeys.length }, () => ({ key: "", value: "" })),
      ];
  const [envRows, setEnvRows] = useState<{ key: string; value: string }[]>(initialRows);

  const updateEnvRow = (idx: number, patch: Partial<{ key: string; value: string }>) => {
    setEnvRows((rows) => rows.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  };
  const addEnvRow = () => setEnvRows((rows) => [...rows, { key: "", value: "" }]);
  const removeEnvRow = (idx: number) => setEnvRows((rows) => rows.filter((_, i) => i !== idx));

  const handleSave = () => {
    const env: Record<string, string> = {};
    for (const { key, value } of envRows) {
      const k = key.trim();
      if (k) env[k] = value.trim();
    }
    const server: MCPServer = {
      id: editServer?.id ?? "",
      name, command,
      args: args.split(" ").filter(Boolean),
      env,
      tools: editServer?.tools ?? [],
    };
    if (editServer) {
      updateMcpServer(editServer.id, server);
    } else {
      addMcpServer(server);
    }
    onClose();
  };

  return (
    <div className="flex-1 h-full flex flex-col bg-(--color-background)">
      <div className="flex items-center justify-between px-4 py-3 bg-white border-b border-(--color-border)">
        <h3 className="text-sm font-semibold">{editServer ? "Edit MCP Server" : "New MCP Server"}</h3>
        <button onClick={onClose} className="p-1 rounded hover:bg-(--color-secondary)"><X size={14} /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <div>
          <label className="block text-sm font-medium mb-1">Name</label>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)}
            placeholder="my-mcp-server"
            className="w-full px-2 py-1.5 text-sm rounded border border-(--color-border) bg-white placeholder:text-(--color-muted-foreground)/60 focus:outline-none focus:ring-1 focus:ring-(--color-ring)" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Command</label>
          <input type="text" value={command} onChange={(e) => setCommand(e.target.value)}
            placeholder="npx"
            className="w-full px-2 py-1.5 text-sm rounded border border-(--color-border) bg-white placeholder:text-(--color-muted-foreground)/60 focus:outline-none focus:ring-1 focus:ring-(--color-ring)" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Arguments (space-separated)</label>
          <input type="text" value={args} onChange={(e) => setArgs(e.target.value)}
            placeholder="-y @firecrawl/mcp"
            className="w-full px-2 py-1.5 text-sm rounded border border-(--color-border) bg-white placeholder:text-(--color-muted-foreground)/60 focus:outline-none focus:ring-1 focus:ring-(--color-ring)" />
        </div>
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="block text-sm font-medium">Environment Variables</label>
            <button
              type="button"
              onClick={addEnvRow}
              className="flex items-center gap-1 text-xs text-(--color-primary) hover:underline"
            >
              <Plus size={12} /> Add
            </button>
          </div>
          <div className="space-y-1.5">
            {envRows.map((row, idx) => (
              <div key={idx} className="flex items-center gap-1.5">
                <input
                  type="text"
                  value={row.key}
                  onChange={(e) => updateEnvRow(idx, { key: e.target.value })}
                  placeholder="KEY"
                  className="flex-1 min-w-0 px-2 py-1.5 text-sm rounded border border-(--color-border) bg-white placeholder:text-(--color-muted-foreground)/60 focus:outline-none focus:ring-1 focus:ring-(--color-ring) font-mono"
                />
                <input
                  type="text"
                  value={row.value}
                  onChange={(e) => updateEnvRow(idx, { value: e.target.value })}
                  placeholder="VALUE"
                  className="flex-[1.5] min-w-0 px-2 py-1.5 text-sm rounded border border-(--color-border) bg-white placeholder:text-(--color-muted-foreground)/60 focus:outline-none focus:ring-1 focus:ring-(--color-ring) font-mono"
                />
                <button
                  type="button"
                  onClick={() => removeEnvRow(idx)}
                  disabled={envRows.length <= 1}
                  className="p-1.5 rounded text-(--color-muted-foreground) hover:bg-(--color-secondary) hover:text-red-500 disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-(--color-muted-foreground)"
                  title="Remove"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
          <p className="text-[11px] text-(--color-muted-foreground) mt-1.5">
            Rows with empty KEY will be ignored.
          </p>
        </div>
        <button onClick={handleSave} disabled={!name || !command}
          className="w-full py-2 rounded-lg border border-(--color-border) bg-(--color-primary) text-(--color-primary-foreground) text-sm hover:opacity-90 disabled:opacity-50">Save</button>
      </div>
    </div>
  );
}

function MCPList({ onNew, onSelect, onEdit }: { onNew: () => void; onSelect: () => void; onEdit: (id: string) => void }) {
  const mcpServers = useAppStore((s) => s.mcpServers);
  const selectedMcpId = useAppStore((s) => s.selectedMcpId);
  const setSelectedMcpId = useAppStore((s) => s.setSelectedMcpId);
  const importMcpServers = useAppStore((s) => s.importMcpServers);
  const deleteMcpServer = useAppStore((s) => s.deleteMcpServer);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importing, setImporting] = useState(false);

  const handleImport = async (path: string) => {
    setImporting(true);
    try {
      await importMcpServers(path);
    } catch (e: any) {
      useAppStore.getState().addToast(`MCP import failed: ${e.message || e}`, "warning");
    } finally {
      setImporting(false);
    }
  };

  const handleEdit = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedMcpId(id);
    onEdit(id);
  };

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    deleteMcpServer(id);
  };

  return (
    <div className="w-[300px] h-full bg-white border-r border-(--color-border) flex flex-col">
      <div className="p-3 border-b border-(--color-border) space-y-1.5">
        <button onClick={onNew}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-(--color-border) bg-(--color-primary) text-(--color-primary-foreground) hover:opacity-90 transition-opacity">
          <Plus size={16} /><span className="text-sm">New Server</span>
        </button>
        <button
          onClick={() => setImportModalOpen(true)}
          disabled={importing}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-(--color-border) text-sm hover:bg-(--color-secondary) disabled:opacity-50"
        >
          <FolderOpen size={16} />
          {importing ? "Importing..." : "Import from Folder"}
        </button>
      </div>

      <FolderPickerModal
        open={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onSelect={handleImport}
        title="Select MCP Configs Folder"
      />

      <div className="flex-1 overflow-y-auto p-2">
        {mcpServers.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-(--color-muted-foreground)">
            <Server size={32} className="mb-2 opacity-50" /><p className="text-sm">No MCP servers</p>
          </div>
        ) : (
          <div className="space-y-1">
            {mcpServers.map((server) => (
              <div
                key={server.id || server.name}
                onClick={() => { setSelectedMcpId(server.id || server.name); onSelect(); }}
                className={cn(
                  "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-all hover:bg-(--color-secondary) cursor-pointer group",
                  selectedMcpId === (server.id || server.name) && ACTIVE_CLASS,
                )}
              >
                <Server size={14} className="shrink-0" />
                <span className="flex-1 text-sm font-medium truncate">{server.name}</span>
                <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground) hover:text-(--color-primary)"
                    onClick={(e) => handleEdit(server.id || server.name, e)}
                    title="Edit server"
                  >
                    <Pencil size={13} />
                  </button>
                  <button
                    className="p-1 rounded hover:bg-red-50 text-(--color-muted-foreground) hover:text-red-500"
                    onClick={(e) => handleDelete(server.id || server.name, e)}
                    title="Delete server"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MCPDetailPanel({ showForm, editServer, onCloseForm }: { showForm: boolean; editServer?: MCPServer; onCloseForm: () => void }) {
  const mcpServers = useAppStore((s) => s.mcpServers);
  const selectedMcpId = useAppStore((s) => s.selectedMcpId);
  const discoverMcpTools = useAppStore((s) => s.discoverMcpTools);
  const [discovering, setDiscovering] = useState(false);

  if (showForm) return <ServerForm onClose={onCloseForm} editServer={editServer} />;

  const selectedServer = mcpServers.find((s) => (s.id || s.name) === selectedMcpId);

  if (!selectedServer) {
    return (
      <div className="flex-1 h-full flex flex-col items-center justify-center bg-(--color-background) text-(--color-muted-foreground)">
        <Server size={48} className="mb-4 opacity-30" /><p className="text-lg font-medium">No server selected</p><p className="text-sm mt-1">Select a server to view details</p>
      </div>
    );
  }

  const handleDiscover = async () => {
    setDiscovering(true);
    try {
      await discoverMcpTools(selectedServer.id);
    } finally {
      setDiscovering(false);
    }
  };

  return (
    <div className="flex-1 h-full flex flex-col bg-(--color-background)">
      <header className="px-4 py-3 bg-white border-b border-(--color-border)">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-(--color-primary)/10 text-(--color-primary) flex items-center justify-center"><Server size={16} /></div>
          <h2 className="font-semibold text-sm flex-1">{selectedServer.name}</h2>
          <button
            onClick={handleDiscover}
            disabled={discovering}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-(--color-border) text-xs hover:bg-(--color-secondary) disabled:opacity-50 transition-colors"
            title="Discover tools from this MCP server"
          >
            <RefreshCw size={12} className={discovering ? "animate-spin" : ""} />
            {discovering ? "Discovering..." : "Discover Tools"}
          </button>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div>
          <h3 className="text-xs font-medium mb-2">Configuration</h3>
          <div className="bg-white rounded-lg border border-(--color-border) p-3 space-y-2 text-xs">
            <div><span className="text-(--color-muted-foreground)">Command:</span><code className="ml-2 bg-(--color-secondary) px-1.5 py-0.5 rounded">{selectedServer.command}</code></div>
            <div><span className="text-(--color-muted-foreground)">Arguments:</span><div className="mt-1 flex flex-wrap gap-1">{selectedServer.args.map((arg, i) => <code key={i} className="bg-(--color-secondary) px-1.5 py-0.5 rounded">{arg}</code>)}</div></div>
            {Object.keys(selectedServer.env).length > 0 && (
              <div><span className="text-(--color-muted-foreground)">Environment:</span>
                {Object.entries(selectedServer.env).map(([k, v]) => <div key={k} className="mt-1"><code className="text-(--color-primary)">{k}</code><span className="text-(--color-muted-foreground)"> = </span><code>{v || "(empty)"}</code></div>)}
              </div>
            )}
          </div>
        </div>
        <div>
          <h3 className="text-xs font-medium mb-2">Tools</h3>
          <div className="bg-white rounded-lg border border-(--color-border) p-3 space-y-2">
            {selectedServer.tools.length === 0 ? (
              <p className="text-xs text-(--color-muted-foreground) text-center">No tools loaded</p>
            ) : (
              selectedServer.tools.map((tool) => (
                <div key={tool.id || tool.name} className="text-xs">
                  <div className="font-medium">{tool.name}</div>
                  {tool.description && <div className="text-(--color-muted-foreground) mt-0.5">{tool.description}</div>}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function MCPsModule() {
  const mcpServers = useAppStore((s) => s.mcpServers);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const handleNew = () => { setShowForm(true); setEditingId(null); };
  const handleSelect = () => { setShowForm(false); setEditingId(null); };

  return (
    <div className="flex h-full">
      <MCPList onNew={handleNew} onSelect={handleSelect} onEdit={(id) => { setEditingId(id); setShowForm(true); }} />
      <MCPDetailPanel
        showForm={showForm}
        editServer={editingId ? mcpServers.find((s) => (s.id || s.name) === editingId) : undefined}
        onCloseForm={() => { setShowForm(false); setEditingId(null); }}
      />
    </div>
  );
}
