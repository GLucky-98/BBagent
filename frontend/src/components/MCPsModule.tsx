import { useState } from "react";
import { Server, ChevronRight, Plug, Unplug, Loader2 } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";

function MCPList() {
  const mcpServers = useAppStore((s) => s.mcpServers);
  const selectedMcpId = useAppStore((s) => s.selectedMcpId);
  const setSelectedMcpId = useAppStore((s) => s.setSelectedMcpId);
  const [expandedServers, setExpandedServers] = useState<Set<string>>(new Set());

  const toggleExpanded = (id: string) => {
    const newSet = new Set(expandedServers);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setExpandedServers(newSet);
  };

  return (
    <div className="w-[320px] h-screen bg-white border-r border-[--color-border] flex flex-col">
      <div className="p-3 border-b border-[--color-border]">
        <div className="h-10 flex items-center px-3">
          <span className="text-sm font-medium text-[--color-muted-foreground]">
            {mcpServers.length} MCP servers
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {mcpServers.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[--color-muted-foreground]">
            <Server size={32} className="mb-2 opacity-50" />
            <p className="text-sm">No MCP servers</p>
          </div>
        ) : (
          <div className="space-y-1">
            {mcpServers.map((server) => (
              <div key={server.id}>
                <button
                  onClick={() => {
                    setSelectedMcpId(server.id);
                    if (server.isConnected) {
                      toggleExpanded(server.id);
                    }
                  }}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all duration-150",
                    "hover:bg-[--color-secondary]",
                    selectedMcpId === server.id && "bg-[--color-primary]/10 text-[--color-primary]"
                  )}
                >
                  <div
                    className={cn(
                      "w-2 h-2 rounded-full shrink-0",
                      server.isConnected ? "bg-emerald-500" : "bg-red-500"
                    )}
                  />
                  <Server size={16} className="shrink-0" />
                  <span className="flex-1 text-sm font-medium truncate">
                    {server.name}
                  </span>
                  {server.isConnected && (
                    <ChevronRight
                      size={14}
                      className={cn(
                        "shrink-0 transition-transform",
                        expandedServers.has(server.id) && "rotate-90"
                      )}
                    />
                  )}
                </button>

                {expandedServers.has(server.id) && server.tools.length > 0 && (
                  <div className="ml-8 mt-1 space-y-1 pb-1">
                    {server.tools.map((tool) => (
                      <div
                        key={tool.id}
                        className="px-3 py-2 text-xs text-[--color-muted-foreground] bg-[--color-secondary]/50 rounded"
                      >
                        <span className="font-mono">{tool.name}</span>
                        <span className="ml-2 line-clamp-1">
                          {tool.description.slice(0, 40)}...
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MCPDetailPanel() {
  const mcpServers = useAppStore((s) => s.mcpServers);
  const selectedMcpId = useAppStore((s) => s.selectedMcpId);
  const updateMcpConnection = useAppStore((s) => s.updateMcpConnection);
  const [isConnecting, setIsConnecting] = useState(false);

  const selectedServer = mcpServers.find((s) => s.id === selectedMcpId);

  if (!selectedServer) {
    return (
      <div className="flex-1 h-screen flex flex-col items-center justify-center bg-[--color-background] text-[--color-muted-foreground]">
        <Server size={48} className="mb-4 opacity-30" />
        <p className="text-lg font-medium">No server selected</p>
        <p className="text-sm mt-1">Select a server to view details</p>
      </div>
    );
  }

  const handleConnect = () => {
    setIsConnecting(true);
    setTimeout(() => {
      updateMcpConnection(selectedServer.id, true);
      setIsConnecting(false);
    }, 1500);
  };

  const handleDisconnect = () => {
    updateMcpConnection(selectedServer.id, false);
  };

  return (
    <div className="flex-1 h-screen flex flex-col bg-[--color-background]">
      <header className="px-6 py-4 bg-white border-b border-[--color-border]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[--color-primary]/10 text-[--color-primary] flex items-center justify-center">
              <Server size={20} />
            </div>
            <div>
              <h2 className="font-semibold text-[--color-foreground]">
                {selectedServer.name}
              </h2>
              <div className="flex items-center gap-2 mt-0.5">
                <span
                  className={cn(
                    "w-2 h-2 rounded-full",
                    selectedServer.isConnected ? "bg-emerald-500" : "bg-red-500"
                  )}
                />
                <span className="text-xs text-[--color-muted-foreground]">
                  {selectedServer.isConnected ? "Connected" : "Disconnected"}
                </span>
              </div>
            </div>
          </div>

          <button
            onClick={selectedServer.isConnected ? handleDisconnect : handleConnect}
            disabled={isConnecting}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all",
              selectedServer.isConnected
                ? "bg-red-100 text-red-600 hover:bg-red-200"
                : "bg-emerald-100 text-emerald-600 hover:bg-emerald-200",
              isConnecting && "opacity-50 cursor-not-allowed"
            )}
          >
            {isConnecting ? (
              <Loader2 size={16} className="animate-spin" />
            ) : selectedServer.isConnected ? (
              <Unplug size={16} />
            ) : (
              <Plug size={16} />
            )}
            <span>
              {isConnecting
                ? "Connecting..."
                : selectedServer.isConnected
                ? "Disconnect"
                : "Connect"}
            </span>
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          <div>
            <h3 className="text-sm font-medium mb-2">Configuration</h3>
            <div className="bg-white rounded-lg border border-[--color-border] p-4 space-y-3">
              <div>
                <span className="text-sm text-[--color-muted-foreground]">Command:</span>
                <code className="ml-2 text-sm font-mono bg-[--color-secondary] px-2 py-0.5 rounded">
                  {selectedServer.command}
                </code>
              </div>
              <div>
                <span className="text-sm text-[--color-muted-foreground]">Arguments:</span>
                <div className="mt-1 flex flex-wrap gap-1">
                  {selectedServer.args.map((arg, idx) => (
                    <code
                      key={idx}
                      className="text-sm font-mono bg-[--color-secondary] px-2 py-0.5 rounded"
                    >
                      {arg}
                    </code>
                  ))}
                </div>
              </div>
              {Object.keys(selectedServer.env).length > 0 && (
                <div>
                  <span className="text-sm text-[--color-muted-foreground]">Environment Variables:</span>
                  <div className="mt-1 space-y-1">
                    {Object.entries(selectedServer.env).map(([key, value]) => (
                      <div key={key} className="flex items-center gap-2 text-sm">
                        <code className="font-mono text-[--color-primary]">{key}</code>
                        <span className="text-[--color-muted-foreground]">=</span>
                        <code className="font-mono">{value || "(empty)"}</code>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium mb-2">
              Available Tools ({selectedServer.tools.length})
            </h3>
            {selectedServer.tools.length === 0 ? (
              <div className="bg-white rounded-lg border border-[--color-border] p-8 text-center text-[--color-muted-foreground] text-sm">
                {selectedServer.isConnected
                  ? "No tools available"
                  : "Connect to view available tools"}
              </div>
            ) : (
              <div className="bg-white rounded-lg border border-[--color-border] divide-y divide-[--color-border]">
                {selectedServer.tools.map((tool) => (
                  <div key={tool.id} className="p-4">
                    <div className="flex items-start gap-2">
                      <code className="text-sm font-mono font-medium text-[--color-primary]">
                        {tool.name}
                      </code>
                    </div>
                    <p className="mt-1 text-sm text-[--color-muted-foreground]">
                      {tool.description}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function MCPsModule() {
  return (
    <>
      <MCPList />
      <MCPDetailPanel />
    </>
  );
}
