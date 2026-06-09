import { useState } from "react";
import { Settings2, Trash2, Play, Square, Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";
import { useAppStore } from "../../store";
import { ConfirmDialog } from "../ConfirmDialog";
import type { Team, SingleAgent } from "../../types";

interface TeamDropdownProps {
  agent: Team;
  onClose: () => void;
}

function MemberItem({ member, teamId, onClose }: { member: SingleAgent; teamId: string; onClose: () => void }) {
  const [isHovered, setIsHovered] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  const activeTeamMemberName = useAppStore((s) => s.activeTeamMemberName);
  const selectTeamMember = useAppStore((s) => s.selectTeamMember);
  const openConfigDialog = useAppStore((s) => s.openConfigDialog);
  const removeAgent = useAppStore((s) => s.removeAgent);
  const agentState = useAppStore((s) => s.agentStates[member.id] || member.state || "ready");
  const startAgent = useAppStore((s) => s.startAgent);
  const stopAgent = useAppStore((s) => s.stopAgent);
  const isActive = activeTeamMemberName === member.name;
  const isRunning = agentState === "running" || agentState === "waiting";

  const handleToggleState = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsToggling(true);
    try {
      if (isRunning) {
        await stopAgent(member.id);
      } else {
        await startAgent(member.id);
      }
    } finally {
      setIsToggling(false);
    }
  };

  const handleDelete = (deleteFiles: boolean) => {
    setDeleteDialogOpen(false);
    removeAgent(member.id, deleteFiles);
  };

  const stateDotClass = cn(
    "w-2 h-2 rounded-full shrink-0",
    agentState === "waiting" && "bg-(--color-success)",
    agentState === "running" && "bg-(--color-success) animate-halo-green-yellow",
    agentState === "error" && "bg-(--color-danger)",
    agentState === "ready" && "bg-(--color-ink-4)"
  );

  return (
    <>
      <div
        className={cn(
          "flex items-center gap-1 w-full px-3 py-1.5 cursor-pointer transition-colors",
          isActive && "bg-(--color-primary)/10 text-(--color-primary)",
          !isActive && "hover:bg-(--color-secondary)"
        )}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        onClick={() => { selectTeamMember(teamId, member.name); onClose(); }}
      >
        <button
          onClick={handleToggleState}
          disabled={isToggling}
          className="flex items-center justify-center w-5 h-5 rounded hover:bg-(--color-muted) shrink-0 disabled:opacity-70"
          title={isRunning ? "Stop agent" : "Start agent"}
        >
          {isToggling ? <Loader2 size={10} className="animate-spin" /> : isRunning ? <Square size={10} /> : <Play size={10} />}
        </button>
        <div className={stateDotClass} />
        <span className="text-sm font-medium truncate flex-1">
          {member.name}
        </span>
        {(isHovered || isActive) && (
          <>
            <button
              onClick={(e) => { e.stopPropagation(); openConfigDialog("edit", "agent", member.id); onClose(); }}
              className="w-5 h-5 flex items-center justify-center rounded hover:bg-(--color-muted) text-(--color-muted-foreground) hover:text-(--color-foreground) shrink-0"
            >
              <Settings2 className="w-3 h-3" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setDeleteDialogOpen(true); }}
              className="w-5 h-5 flex items-center justify-center rounded hover:bg-red-50 text-(--color-muted-foreground) hover:text-red-600 shrink-0"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </>
        )}
      </div>
      <ConfirmDialog
        open={deleteDialogOpen}
        title="Delete Agent"
        message={`Are you sure you want to delete "${member.name}"? Do you want to delete the source files as well?`}
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

export function TeamDropdown({ agent, onClose }: TeamDropdownProps) {
  return (
    <div className="bg-white rounded-lg shadow-lg border border-(--color-border) py-0.5 min-w-[200px] max-h-[50vh] overflow-y-auto">
      {agent.members.map((member) => (
        <MemberItem
          key={member.id || member.name}
          member={member}
          teamId={agent.id}
          onClose={onClose}
        />
      ))}
    </div>
  );
}
