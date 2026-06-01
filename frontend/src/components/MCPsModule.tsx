import { useState } from "react";
import { Server, Plus, FolderOpen, X } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import type { MCPServer } from "../types";
import { FolderPickerModal } from "./FolderPickerModal";

const ACTIVE_CLASS = "bg-(--color-primary)/10 text-(--color-primary) font-semibold shadow-[inset_4px_0_0_0_#10b981]";

function NewServerForm({ onClose }: { onClose: () => void }) {
  const addMcpServer = useAppStore((s) => s.addMcpServer);
  const [form, setForm] = useState<{ name: string; command: string; args: string; env: string }>({ name: "", command: "", args: "", env: "" });

  const handleSave = () => {
    const server: MCPServer = {
      name: form.name, command: form.command,
      args: form.args.split(" ").filter(Boolean),
      env: form.env.split("\n").filter(Boolean).reduce<Record<string, string>>((acc, line) => {
        const [k, ...v] = line.split("=");
        if (k) acc[k.trim()] = v.join("=").trim();
        return acc;
      }, {}),
      tools: [],
    };
    addMcpServer(server);
    onClose();
  };

  return (
    <div className="flex-1 h-full flex flex-col bg-(--color-background)">
      <div className="flex items-center justify-between px-4 py-3 bg-white border-b border-(--color-border)">
        <h3 className="text-sm font-semibold">New MCP Server</h3>
        <button onClick={onClose} className="p-1 rounded hover:bg-(--color-secondary)"><X size={14} /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <div>
          <label className="block text-sm font-medium mb-1">Name</label>
          <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full px-2 py-1.5 text-sm rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring)" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Command</label>
          <input type="text" value={form.command} onChange={(e) => setForm({ ...form, command: e.target.value })}
            placeholder="npx" className="w-full px-2 py-1.5 text-sm rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring)" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Arguments (space-separated)</label>
          <input type="text" value={form.args} onChange={(e) => setForm({ ...form, args: e.target.value })}
            placeholder="-y @firecrawl/mcp" className="w-full px-2 py-1.5 text-sm rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring)" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Environment (KEY=VALUE per line)</label>
          <textarea value={form.env} onChange={(e) => setForm({ ...form, env: e.target.value })}
            rows={4} className="w-full px-2 py-1.5 text-sm rounded border border-(--color-border) bg-white focus:outline-none focus:ring-1 focus:ring-(--color-ring) resize-none" />
        </div>
        <button onClick={handleSave} disabled={!form.name || !form.command}
          className="w-full py-2 rounded-lg border border-(--color-border) bg-(--color-primary) text-(--color-primary-foreground) text-sm hover:opacity-90 disabled:opacity-50">Save</button>
      </div>
    </div>
  );
}

function MCPList({ onNew }: { onNew: () => void }) {
  const mcpServers = useAppStore((s) => s.mcpServers);
  const selectedMcpId = useAppStore((s) => s.selectedMcpId);
  const setSelectedMcpId = useAppStore((s) => s.setSelectedMcpId);
  const importMcpServers = useAppStore((s) => s.importMcpServers);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importing, setImporting] = useState(false);

  const handleImport = async (path: string) => {
    setImporting(true);
    try {
      await importMcpServers(path);
    } finally {
      setImporting(false);
    }
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
              <button key={server.name} onClick={() => setSelectedMcpId(server.name)}
                className={cn("w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-all hover:bg-(--color-secondary)", selectedMcpId === server.name && ACTIVE_CLASS)}>
                <Server size={14} className="shrink-0" /><span className="flex-1 text-sm font-medium truncate">{server.name}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MCPDetailPanel({ showNew, onCloseForms }: { showNew: boolean; onCloseForms: () => void }) {
  const mcpServers = useAppStore((s) => s.mcpServers);
  const selectedMcpId = useAppStore((s) => s.selectedMcpId);

  if (showNew) return <NewServerForm onClose={onCloseForms} />;

  const selectedServer = mcpServers.find((s) => s.name === selectedMcpId);

  if (!selectedServer) {
    return (
      <div className="flex-1 h-full flex flex-col items-center justify-center bg-(--color-background) text-(--color-muted-foreground)">
        <Server size={48} className="mb-4 opacity-30" /><p className="text-lg font-medium">No server selected</p><p className="text-sm mt-1">Select a server to view details</p>
      </div>
    );
  }

  return (
    <div className="flex-1 h-full flex flex-col bg-(--color-background)">
      <header className="px-4 py-3 bg-white border-b border-(--color-border)">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-(--color-primary)/10 text-(--color-primary) flex items-center justify-center"><Server size={16} /></div>
          <h2 className="font-semibold text-sm">{selectedServer.name}</h2>
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
                <div key={tool.id} className="text-xs">
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
  const [showNew, setShowNew] = useState(false);

  return (
    <div className="flex h-full">
      <MCPList onNew={() => setShowNew(true)} />
      <MCPDetailPanel showNew={showNew} onCloseForms={() => setShowNew(false)} />
    </div>
  );
}
