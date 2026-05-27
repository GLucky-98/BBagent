import { useState } from "react";
import { Server, Plug, Unplug, Loader2, Plus, FolderOpen, X } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import type { MCPServer } from "../types";

const ACTIVE_CLASS = "bg-[--color-primary]/10 text-[--color-primary] font-semibold shadow-[inset_4px_0_0_0_#10b981]";

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
      isConnected: false, tools: [], source: "imported",
    };
    addMcpServer(server);
    onClose();
  };

  return (
    <div className="flex-1 h-full flex flex-col bg-[--color-background]">
      <div className="flex items-center justify-between px-4 py-3 bg-white border-b border-[--color-border]">
        <h3 className="text-sm font-semibold">New MCP Server</h3>
        <button onClick={onClose} className="p-1 rounded hover:bg-[--color-secondary]"><X size={14} /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <div>
          <label className="block text-sm font-medium mb-1">Name</label>
          <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Command</label>
          <input type="text" value={form.command} onChange={(e) => setForm({ ...form, command: e.target.value })}
            placeholder="npx" className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Arguments (space-separated)</label>
          <input type="text" value={form.args} onChange={(e) => setForm({ ...form, args: e.target.value })}
            placeholder="-y @firecrawl/mcp" className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Environment (KEY=VALUE per line)</label>
          <textarea value={form.env} onChange={(e) => setForm({ ...form, env: e.target.value })}
            rows={4} className="w-full px-2 py-1.5 text-sm rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring] resize-none" />
        </div>
        <button onClick={handleSave} disabled={!form.name || !form.command}
          className="w-full py-2 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] text-sm font-medium hover:opacity-90 disabled:opacity-50">Save</button>
      </div>
    </div>
  );
}

function MCPList({ onNew, onImport }: { onNew: () => void; onImport: () => void }) {
  const mcpServers = useAppStore((s) => s.mcpServers);
  const selectedMcpId = useAppStore((s) => s.selectedMcpId);
  const setSelectedMcpId = useAppStore((s) => s.setSelectedMcpId);
  const importMcpServers = useAppStore((s) => s.importMcpServers);
  const [showImport, setShowImport] = useState(false);
  const [importPath, setImportPath] = useState("");

  const handleImport = () => {
    importMcpServers([
      { name: "imported-server", command: "node", args: ["./server.js"], env: {}, isConnected: false, tools: [], source: "imported" },
    ]);
    setShowImport(false); setImportPath("");
  };

  const defaults = mcpServers.filter((s) => s.source === "default");
  const imported = mcpServers.filter((s) => s.source === "imported");

  return (
    <div className="w-[300px] h-full bg-white border-r border-[--color-border] flex flex-col">
      <div className="p-2 border-b border-[--color-border] space-y-1">
        <button onClick={onNew}
          className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] text-xs font-medium hover:opacity-90">
          <Plus size={12} />New Server
        </button>
        <button onClick={() => setShowImport(!showImport)}
          className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg border border-[--color-border] text-xs font-medium hover:bg-[--color-secondary]">
          <FolderOpen size={12} />Import from Folder
        </button>
      </div>
      {showImport && (
        <div className="p-2 border-b border-[--color-border] space-y-2">
          <input type="text" value={importPath} onChange={(e) => setImportPath(e.target.value)}
            placeholder="/path/to/mcp/configs" className="w-full px-2 py-1.5 text-xs rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
          <div className="flex gap-2">
            <button onClick={handleImport} disabled={!importPath}
              className="flex-1 py-1 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] text-xs font-medium hover:opacity-90 disabled:opacity-50">Import</button>
            <button onClick={() => setShowImport(false)} className="px-3 py-1 rounded-lg border border-[--color-border] text-xs hover:bg-[--color-secondary]">Cancel</button>
          </div>
        </div>
      )}
      <div className="flex-1 overflow-y-auto p-2">
        {mcpServers.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[--color-muted-foreground]">
            <Server size={32} className="mb-2 opacity-50" /><p className="text-sm">No MCP servers</p>
          </div>
        ) : (
          <div className="space-y-1">
            {defaults.length > 0 && <div className="px-2 py-1 text-xs font-medium text-[--color-muted-foreground]">Default</div>}
            {defaults.map((server) => (
              <button key={server.name} onClick={() => setSelectedMcpId(server.name)}
                className={cn("w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-all hover:bg-[--color-secondary]", selectedMcpId === server.name && ACTIVE_CLASS)}>
                <div className={cn("w-2 h-2 rounded-full shrink-0", server.isConnected ? "bg-emerald-500" : "bg-red-500")} /><Server size={14} className="shrink-0" /><span className="flex-1 text-sm font-medium truncate">{server.name}</span>
              </button>
            ))}
            {imported.length > 0 && <div className="px-2 py-1 text-xs font-medium text-[--color-muted-foreground] mt-2">Imported</div>}
            {imported.map((server) => (
              <button key={server.name} onClick={() => setSelectedMcpId(server.name)}
                className={cn("w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-all hover:bg-[--color-secondary]", selectedMcpId === server.name && ACTIVE_CLASS)}>
                <div className={cn("w-2 h-2 rounded-full shrink-0", server.isConnected ? "bg-emerald-500" : "bg-red-500")} /><Server size={14} className="shrink-0" /><span className="flex-1 text-sm font-medium truncate">{server.name}</span>
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
  const updateMcpConnection = useAppStore((s) => s.updateMcpConnection);
  const [isConnecting, setIsConnecting] = useState(false);

  if (showNew) return <NewServerForm onClose={onCloseForms} />;

  const selectedServer = mcpServers.find((s) => s.name === selectedMcpId);

  if (!selectedServer) {
    return (
      <div className="flex-1 h-full flex flex-col items-center justify-center bg-[--color-background] text-[--color-muted-foreground]">
        <Server size={48} className="mb-4 opacity-30" /><p className="text-lg font-medium">No server selected</p><p className="text-sm mt-1">Select a server to view details</p>
      </div>
    );
  }

  const handleConnect = () => { setIsConnecting(true); setTimeout(() => { updateMcpConnection(selectedServer.name, true); setIsConnecting(false); }, 1500); };
  const handleDisconnect = () => updateMcpConnection(selectedServer.name, false);

  return (
    <div className="flex-1 h-full flex flex-col bg-[--color-background]">
      <header className="px-4 py-3 bg-white border-b border-[--color-border]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[--color-primary]/10 text-[--color-primary] flex items-center justify-center"><Server size={16} /></div>
            <div>
              <h2 className="font-semibold text-sm">{selectedServer.name}</h2>
              <div className="flex items-center gap-1.5 mt-0.5">
                <div className={cn("w-1.5 h-1.5 rounded-full", selectedServer.isConnected ? "bg-emerald-500" : "bg-red-500")} />
                <span className="text-xs text-[--color-muted-foreground]">{selectedServer.isConnected ? "Connected" : "Disconnected"}</span>
              </div>
            </div>
          </div>
          <button onClick={selectedServer.isConnected ? handleDisconnect : handleConnect} disabled={isConnecting}
            className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium", selectedServer.isConnected ? "bg-red-100 text-red-600 hover:bg-red-200" : "bg-emerald-100 text-emerald-600 hover:bg-emerald-200", isConnecting && "opacity-50 cursor-not-allowed")}>
            {isConnecting ? <Loader2 size={14} className="animate-spin" /> : selectedServer.isConnected ? <Unplug size={14} /> : <Plug size={14} />}
            <span>{isConnecting ? "Connecting..." : selectedServer.isConnected ? "Disconnect" : "Connect"}</span>
          </button>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div>
          <h3 className="text-xs font-medium mb-2">Configuration</h3>
          <div className="bg-white rounded-lg border border-[--color-border] p-3 space-y-2 text-xs">
            <div><span className="text-[--color-muted-foreground]">Command:</span><code className="ml-2 bg-[--color-secondary] px-1.5 py-0.5 rounded">{selectedServer.command}</code></div>
            <div><span className="text-[--color-muted-foreground]">Arguments:</span><div className="mt-1 flex flex-wrap gap-1">{selectedServer.args.map((arg, i) => <code key={i} className="bg-[--color-secondary] px-1.5 py-0.5 rounded">{arg}</code>)}</div></div>
            {Object.keys(selectedServer.env).length > 0 && (
              <div><span className="text-[--color-muted-foreground]">Environment:</span>
                {Object.entries(selectedServer.env).map(([k, v]) => <div key={k} className="mt-1"><code className="text-[--color-primary]">{k}</code><span className="text-[--color-muted-foreground]"> = </span><code>{v || "(empty)"}</code></div>)}
              </div>
            )}
          </div>
        </div>
        <div>
          <h3 className="text-xs font-medium mb-2">Tools</h3>
          <div className="bg-white rounded-lg border border-[--color-border] p-4 text-center text-xs text-[--color-muted-foreground]">
            {selectedServer.isConnected ? "Tools loaded dynamically after connection" : "Connect to load available tools"}
          </div>
        </div>
      </div>
    </div>
  );
}

export function MCPsModule() {
  const [showNew, setShowNew] = useState(false);
  const closeForms = () => setShowNew(false);

  return (
    <div className="flex h-full">
      <MCPList
        onNew={() => setShowNew(true)}
        onImport={() => {}}
      />
      <MCPDetailPanel showNew={showNew} onCloseForms={closeForms} />
    </div>
  );
}
