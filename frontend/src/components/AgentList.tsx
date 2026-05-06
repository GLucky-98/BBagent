import { Plus, ChevronRight, Bot, Users } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import type { Agent } from "../types";

function AgentItem({
  agent,
  depth = 0,
}: {
  agent: Agent;
  depth?: number;
}) {
  const selectedAgentId = useAppStore((s) => s.selectedAgentId);
  const setSelectedAgentId = useAppStore((s) => s.setSelectedAgentId);
  const expandedTeams = useAppStore((s) => s.expandedTeams);
  const toggleTeamExpanded = useAppStore((s) => s.toggleTeamExpanded);
  const agents = useAppStore((s) => s.agents);

  const isSelected = selectedAgentId === agent.id;
  const isTeam = agent.type === "team";
  const isExpanded = expandedTeams.has(agent.id);

  const handleClick = () => {
    if (isTeam) {
      toggleTeamExpanded(agent.id);
    }
    setSelectedAgentId(agent.id);
  };

  const teamMembers = isTeam
    ? agents.filter((a) => agent.teamMembers?.some((m) => m.id === a.id))
    : [];

  return (
    <>
      <button
        onClick={handleClick}
        className={cn(
          "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-all duration-150",
          "hover:bg-[--color-secondary]",
          isSelected && "bg-[--color-primary]/10 text-[--color-primary]",
          depth > 0 && "ml-6"
        )}
      >
        {isTeam ? (
          <ChevronRight
            size={14}
            className={cn(
              "transition-transform duration-200",
              isExpanded && "rotate-90"
            )}
          />
        ) : (
          <Bot size={14} className="shrink-0" />
        )}
        <span className="truncate text-sm font-medium">{agent.name}</span>
      </button>

      {isTeam && isExpanded && teamMembers.length > 0 && (
        <div className="mt-1">
          {teamMembers.map((member) => (
            <AgentItem key={member.id} agent={member} depth={depth + 1} />
          ))}
        </div>
      )}
    </>
  );
}

export function AgentList() {
  const agents = useAppStore((s) => s.agents);
  const setIsCreateDialogOpen = useAppStore((s) => s.setIsCreateDialogOpen);

  const handleCreateClick = () => {
    setIsCreateDialogOpen(true);
  };

  const singleAgents = agents.filter((a) => a.type === "single");
  const teams = agents.filter((a) => a.type === "team");

  return (
    <div className="w-[320px] h-screen bg-white border-r border-[--color-border] flex flex-col">
      <div className="p-3 border-b border-[--color-border]">
        <button
          onClick={handleCreateClick}
          className={cn(
            "w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg",
            "bg-[--color-primary] text-[--color-primary-foreground]",
            "hover:opacity-90 transition-opacity"
          )}
        >
          <Plus size={16} />
          <span className="text-sm font-medium">New Agent</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {agents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[--color-muted-foreground]">
            <Bot size={32} className="mb-2 opacity-50" />
            <p className="text-sm">No agents yet</p>
            <p className="text-xs mt-1">Create your first agent</p>
          </div>
        ) : (
          <div className="space-y-1">
            {singleAgents.map((agent) => (
              <AgentItem key={agent.id} agent={agent} />
            ))}

            {teams.length > 0 && (
              <div className="pt-2 mt-2 border-t border-[--color-border]">
                <div className="px-3 py-1 text-xs font-medium text-[--color-muted-foreground] flex items-center gap-2">
                  <Users size={12} />
                  <span>Teams</span>
                </div>
                {teams.map((team) => (
                  <AgentItem key={team.id} agent={team} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
