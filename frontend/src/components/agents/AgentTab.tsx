import { useState, useMemo, useRef, useCallback } from "react";
import { Settings2, Trash2, Play, Square, Loader2 } from "lucide-react";
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
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  const tabRef = useRef<HTMLDivElement>(null);
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
    setIsToggling(true);
    try {
      if (isRunning) {
        await (isTeam ? stopTeam(agent.id) : stopAgent(agent.id));
      } else {
        await (isTeam ? startTeam(agent.id) : startAgent(agent.id));
      }
    } finally {
      setIsToggling(false);
    }
  };

  const handleOpenChange = useCallback((open: boolean) => {
    setDropdownOpen(open);
    if (open) {
      onClick();
    }
  }, [onClick]);

  const stateDotClass = cn(
    "w-1.5 h-1.5 rounded-full shrink-0",
    agentState === "waiting" && "bg-(--color-success)",
    agentState === "running" && "bg-(--color-success) animate-halo-green-yellow",
    agentState === "error" && "bg-(--color-danger)",
    agentState === "ready" && "bg-(--color-ink-4)"
  );

  const tabContent = (
    <div
      className={cn(
        "group flex items-center gap-1.5 px-3 h-9 rounded-md cursor-pointer transition-colors select-none min-w-0 max-w-[220px]",
        !isActive && "text-(--color-muted-foreground) hover:bg-(--color-secondary) hover:text-(--color-foreground)",
        isActive && "bg-(--color-secondary) text-(--color-foreground)"
      )}
      ref={tabRef}
      onClick={isTeam ? undefined : onClick}
    >
      <button
        onClick={handleToggleState}
        onPointerDown={(e) => e.stopPropagation()}
        disabled={isToggling}
        className="flex items-center justify-center w-5 h-5 rounded hover:bg-(--color-muted) shrink-0 disabled:opacity-70"
        title={isRunning ? "Stop agent" : "Start agent"}
      >
        {isToggling ? <Loader2 size={10} className="animate-spin" /> : isRunning ? <Square size={10} /> : <Play size={10} />}
      </button>
      <div className={stateDotClass} />
      <span className="text-[13px] font-medium truncate flex-1 tracking-[-0.01em]">
        {displayName}
      </span>
      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        <button
          onClick={(e) => { e.stopPropagation(); onConfig(); }}
          onPointerDown={(e) => e.stopPropagation()}
          className="w-5 h-5 flex items-center justify-center rounded hover:bg-black/5 text-(--color-muted-foreground) shrink-0">
          <Settings2 className="w-3 h-3" />
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); setDeleteDialogOpen(true); }}
          onPointerDown={(e) => e.stopPropagation()}
          className="w-5 h-5 flex items-center justify-center rounded hover:bg-red-50 text-(--color-muted-foreground) hover:text-red-600 shrink-0">
          <Trash2 className="w-3 h-3" />
        </button>
      </div>
    </div>
  );

  if (!isTeam) {
    return (
      <>
        {tabContent}
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

  return (
    <>
      <DropdownMenu.Root open={dropdownOpen} onOpenChange={handleOpenChange} modal={false}>
        <DropdownMenu.Trigger asChild>
          {tabContent}
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="start"
            sideOffset={4}
            className="z-[100]"
            style={{ minWidth: tabRef.current?.offsetWidth || 200, maxHeight: "50vh" }}
          >
            <TeamDropdown
              agent={agent}
              onClose={() => setDropdownOpen(false)}
            />
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
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
