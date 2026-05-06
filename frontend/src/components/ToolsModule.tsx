import { useState } from "react";
import { Wrench, Cpu } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";

function ToolList() {
  const tools = useAppStore((s) => s.tools);
  const selectedToolId = useAppStore((s) => s.selectedToolId);
  const setSelectedToolId = useAppStore((s) => s.setSelectedToolId);
  const [filter, setFilter] = useState<"all" | "builtin" | "mcp">("all");

  const builtinTools = tools.filter((t) => !t.isMcp);
  const mcpTools = tools.filter((t) => t.isMcp);
  const filteredTools =
    filter === "all"
      ? tools
      : filter === "builtin"
      ? builtinTools
      : mcpTools;

  return (
    <div className="w-[320px] h-screen bg-white border-r border-[--color-border] flex flex-col">
      <div className="p-3 border-b border-[--color-border]">
        <div className="flex gap-1 p-1 bg-[--color-secondary] rounded-lg">
          {(["all", "builtin", "mcp"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "flex-1 px-2 py-1.5 rounded-md text-xs font-medium transition-all",
                filter === f
                  ? "bg-white text-[--color-foreground] shadow-sm"
                  : "text-[--color-muted-foreground] hover:text-[--color-foreground]"
              )}
            >
              {f === "all" ? "All" : f === "builtin" ? "Built-in" : "MCP"}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {filteredTools.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[--color-muted-foreground]">
            <Wrench size={32} className="mb-2 opacity-50" />
            <p className="text-sm">No tools found</p>
          </div>
        ) : (
          <div className="space-y-1">
            {filteredTools.map((tool) => (
              <button
                key={tool.id}
                onClick={() => setSelectedToolId(tool.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all duration-150",
                  "hover:bg-[--color-secondary]",
                  selectedToolId === tool.id && "bg-[--color-primary]/10 text-[--color-primary]"
                )}
              >
                <div
                  className={cn(
                    "w-8 h-8 rounded-lg flex items-center justify-center",
                    tool.isMcp
                      ? "bg-amber-100 text-amber-600"
                      : "bg-[--color-primary]/10 text-[--color-primary]"
                  )}
                >
                  {tool.isMcp ? <Cpu size={14} /> : <Wrench size={14} />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{tool.name}</p>
                  <p className="text-xs text-[--color-muted-foreground] truncate">
                    {tool.description.slice(0, 50)}...
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ToolDetailPanel() {
  const tools = useAppStore((s) => s.tools);
  const selectedToolId = useAppStore((s) => s.selectedToolId);

  const selectedTool = tools.find((t) => t.id === selectedToolId);

  if (!selectedTool) {
    return (
      <div className="flex-1 h-screen flex flex-col items-center justify-center bg-[--color-background] text-[--color-muted-foreground]">
        <Wrench size={48} className="mb-4 opacity-30" />
        <p className="text-lg font-medium">No tool selected</p>
        <p className="text-sm mt-1">Select a tool to view details</p>
      </div>
    );
  }

  return (
    <div className="flex-1 h-screen flex flex-col bg-[--color-background]">
      <header className="px-6 py-4 bg-white border-b border-[--color-border]">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "w-10 h-10 rounded-lg flex items-center justify-center",
              selectedTool.isMcp
                ? "bg-amber-100 text-amber-600"
                : "bg-[--color-primary]/10 text-[--color-primary]"
            )}
          >
            {selectedTool.isMcp ? <Cpu size={20} /> : <Wrench size={20} />}
          </div>
          <div>
            <h2 className="font-semibold text-[--color-foreground]">
              {selectedTool.name}
            </h2>
            <p className="text-xs text-[--color-muted-foreground]">
              {selectedTool.isMcp ? "MCP Tool" : "Built-in Tool"}
            </p>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          <div>
            <h3 className="text-sm font-medium mb-2">Description</h3>
            <div className="bg-white rounded-lg border border-[--color-border] p-4">
              <p className="text-sm text-[--color-foreground]">
                {selectedTool.description}
              </p>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium mb-2">Input Schema</h3>
            <div className="bg-white rounded-lg border border-[--color-border] p-4">
              <pre className="text-xs font-mono text-[--color-foreground] overflow-x-auto">
                {JSON.stringify(selectedTool.inputSchema, null, 2)}
              </pre>
            </div>
          </div>

          {selectedTool.inputSchema.properties && (
            <div>
              <h3 className="text-sm font-medium mb-2">Parameters</h3>
              <div className="bg-white rounded-lg border border-[--color-border] divide-y divide-[--color-border]">
                {Object.entries(selectedTool.inputSchema.properties as Record<string, any>).map(
                  ([name, prop]: [string, any]) => (
                    <div key={name} className="p-4">
                      <div className="flex items-center gap-2 mb-1">
                        <code className="text-sm font-mono font-medium text-[--color-primary]">
                          {name}
                        </code>
                        <span className="text-xs text-[--color-muted-foreground]">
                          ({prop.type})
                        </span>
                      </div>
                      <p className="text-sm text-[--color-muted-foreground]">
                        {prop.description || "No description"}
                      </p>
                      {selectedTool.inputSchema.required?.includes(name) && (
                        <span className="inline-block mt-1 px-1.5 py-0.5 bg-[--color-danger]/10 text-[--color-danger] text-xs rounded">
                          Required
                        </span>
                      )}
                    </div>
                  )
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function ToolsModule() {
  return (
    <>
      <ToolList />
      <ToolDetailPanel />
    </>
  );
}
