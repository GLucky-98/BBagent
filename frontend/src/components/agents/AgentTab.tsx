import { useState, useMemo } from "react";
import { Settings2, Trash2, Play, Square } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { cn } from "../../lib/utils";
import { useAppStore } from "../../store";
import { TeamDropdown } from "./TeamDropdown";
import { ConfirmDialog } from "../ConfirmDialog";
import type { Agent } from "../../types";
import { isTeam as isTeamType } from "../../types";

interface AgentTabProps {
  agent: Agent;
  isActive: boolean;
  onClick: () => void;
  onConfig: () => void;
}

export function AgentTab({ agent, isActive, onClick, onConfig }: AgentTabProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const activeTeamMemberName = useAppStore((s) => s.activeTeamMemberName);
  const removeAgent = useAppStore((s) => s.removeAgent);
  const removeTeam = useAppStore((s) => s.removeTeam);
  const agentState = useAppStore((s) => s.agentStates[agent.id] || agent.state || "ready");
  const startAgent = useAppStore((s) => s.startAgent);
  const stopAgent = useAppStore((s) => s.stopAgent);
  const startTeam = useAppStore((s) => s.startTeam);
  const stopTeam = useAppStore((s) => s.stopTeam);
  const isTeam = isTeamType(agent);
  const isRunning = agentState === "running" || agentState === "waiting";

  const teamActive = agent.id === activeAgentId
    || (isTeam && activeTeamMemberName
      && agent.members.some((m) => m.name === activeTeamMemberName));

  const displayName = useMemo(() => {
    if (!isTeam) return agent.name;
    if (teamActive && activeTeamMemberName) {
      return `${agent.name} \u203A ${activeTeamMemberName}`;
    }
    return agent.name;
  }, [agent, isTeam, teamActive, activeTeamMemberName]);

  const handleDelete = (deleteFiles: boolean) => {
    setDeleteDialogOpen(false);
    if (isTeam) {
      removeTeam(agent.id);
    } else {
      removeAgent(agent.id, deleteFiles);
    }
  };

  const handleToggleState = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isRunning) {
      await (isTeam ? stopTeam(agent.id) : stopAgent(agent.id));
    } else {
      await (isTeam ? startTeam(agent.id) : startAgent(agent.id));
    }
  };

  const stateDotClass = cn(
    "w-2 h-2 rounded-full shrink-0",
    agentState === "waiting" && "bg-green-500",
    agentState === "running" && "animate-pulse-green-yellow",
    agentState === "error" && "bg-red-500",
    agentState === "ready" && "bg-gray-400"
  );

  return (
    <>
      <DropdownMenu.Root open={isTeam && dropdownOpen} onOpenChange={setDropdownOpen}>
        <div
          className={cn(
            "flex items-center gap-1 px-3 py-1.5 h-full cursor-pointer border-b-2 transition-colors select-none min-w-0 max-w-[240px]",
            !isActive && "bg-transparent text-(--color-muted-foreground) border-transparent hover:bg-(--color-secondary)/50"
          )}
          style={isActive ? {
            backgroundColor: "var(--color-background)",
            color: "var(--color-foreground)",
            borderBottomColor: "#3b82f6",
            fontWeight: 500,
          } : undefined}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
        >
          <button
            onClick={handleToggleState}
            className="flex items-center justify-center w-5 h-5 rounded hover:bg-(--color-muted) shrink-0"
            title={isRunning ? "Stop agent" : "Start agent"}
          >
            {isRunning ? <Square size={10} /> : <Play size={10} />}
          </button>
          <div className={stateDotClass} />
          {isTeam ? (
            <DropdownMenu.Trigger asChild>
              <span
                className="text-sm font-medium truncate flex-1"
                onClick={(e) => { onClick(); setDropdownOpen(true); }}
              >
                {displayName}
              </span>
            </DropdownMenu.Trigger>
          ) : (
            <span className="text-sm font-medium truncate flex-1" onClick={onClick}>
              {displayName}
            </span>
          )}
          {(isHovered || isActive) && (
            <>
              <button onClick={(e) => { e.stopPropagation(); onConfig(); }} className="w-5 h-5 flex items-center justify-center rounded hover:bg-(--color-muted) text-(--color-muted-foreground) hover:text-(--color-foreground) shrink-0">
                <Settings2 className="w-3 h-3" />
              </button>
              <button onClick={(e) => { e.stopPropagation(); setDeleteDialogOpen(true); }} className="w-5 h-5 flex items-center justify-center rounded hover:bg-red-50 text-(--color-muted-foreground) hover:text-red-600 shrink-0">
                <Trash2 className="w-3 h-3" />
              </button>
            </>
          )}
        </div>
        {isTeam && (
          <DropdownMenu.Portal>
            <DropdownMenu.Content align="start" sideOffset={4} className="z-[100]">
              <TeamDropdown agent={agent} />
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        )}
      </DropdownMenu.Root>

      <ConfirmDialog
        open={deleteDialogOpen}
        title="Delete Agent"
        message={`Are you sure you want to delete "${agent.name}"? Do you want to delete the source files as well?`}
        confirmLabel="Yes"
        secondaryLabel="No"
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={() => handleDelete(true)}
        onSecondary={() => handleDelete(false)}
        onCancel={() => setDeleteDialogOpen(false)}
      />
    </>
  );
}
