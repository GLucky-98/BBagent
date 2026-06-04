import { Plus } from "lucide-react";
import { useAppStore } from "../../store";
import { AgentTab } from "./AgentTab";

export function AgentTabs() {
  const agents = useAppStore((s) => s.agents);
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const setActiveAgentId = useAppStore((s) => s.setActiveAgentId);
  const openConfigDialog = useAppStore((s) => s.openConfigDialog);

  if (agents.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-sm text-(--color-muted-foreground)">
          No agents yet. Complete onboarding to create your first agent.
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center h-full gap-0.5">
      {agents.map((agent) => (
        <AgentTab
          key={agent.id || agent.name}
          agent={agent}
          isActive={agent.id === activeAgentId}
          onClick={() => setActiveAgentId(agent.id)}
          onConfig={() => openConfigDialog("edit", agent.type === "single" ? "agent" : "team", agent.id)}
        />
      ))}
      <button
        onClick={() => openConfigDialog("create", "")}
        className="flex items-center justify-center w-8 h-8 ml-1 rounded-md hover:bg-(--color-secondary) text-(--color-muted-foreground) hover:text-(--color-foreground) transition-colors shrink-0"
        title="New Agent"
      >
        <Plus className="w-4 h-4" />
      </button>
    </div>
  );
}
