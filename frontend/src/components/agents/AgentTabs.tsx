import { Plus } from "lucide-react";
import { useAppStore } from "../../store";
import { AgentTab } from "./AgentTab";
import { isTeam } from "../../types";

export function AgentTabs() {
  const agents = useAppStore((s) => s.agents);
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const activeTeamMemberName = useAppStore((s) => s.activeTeamMemberName);
  const setActiveAgentId = useAppStore((s) => s.setActiveAgentId);
  const openConfigDialog = useAppStore((s) => s.openConfigDialog);
  const teamMemberIds = useAppStore((s) => s.teamMemberIds);

  // Filter out teammates — they appear inside team dropdowns, not as standalone tabs
  const visibleAgents = agents.filter((a) => !teamMemberIds.has(a.id));

  if (visibleAgents.length === 0) {
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
      {visibleAgents.map((agent) => {
        const isTeamAgent = isTeam(agent);
        // Team tab is active when its ID matches OR a teammate is selected
        const teamActive = agent.id === activeAgentId
          || (isTeamAgent && activeTeamMemberName
            && agent.members.some((m) => m.name === activeTeamMemberName));

        return (
          <AgentTab
            key={agent.id || agent.name}
            agent={agent}
            isActive={teamActive}
            onClick={() => setActiveAgentId(agent.id)}
            onConfig={() => openConfigDialog("edit", isTeamAgent ? "team" : "agent", agent.id)}
          />
        );
      })}
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
