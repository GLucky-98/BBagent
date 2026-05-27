import { User, Users, Settings2 } from "lucide-react";
import { cn } from "../../lib/utils";
import { useAppStore } from "../../store";
import type { Agent } from "../../types";

interface TeamDropdownProps {
  agent: Agent;
}

export function TeamDropdown({ agent }: TeamDropdownProps) {
  const activeTeamMemberId = useAppStore((s) => s.activeTeamMemberId);
  const selectTeamMember = useAppStore((s) => s.selectTeamMember);
  const openConfigDialog = useAppStore((s) => s.openConfigDialog);

  return (
    <div className="w-52 bg-white rounded-lg shadow-lg border border-[--color-border] p-1.5">
      {agent.teamMembers?.map((member) => (
        <button key={member.id} onClick={() => selectTeamMember(agent.id, member.id)}
          className={cn("flex items-center justify-between w-full px-3 py-2 rounded-md text-sm cursor-pointer hover:bg-[--color-secondary] outline-none", activeTeamMemberId === member.id && "bg-[--color-primary]/10 text-[--color-primary]")}>
          <div className="flex items-center gap-2"><User className="w-4 h-4" /><span>{member.name}</span></div>
          <button onClick={(e) => { e.stopPropagation(); openConfigDialog("edit", "agent", member.id); }}
            className="w-5 h-5 flex items-center justify-center rounded hover:bg-[--color-muted] text-[--color-muted-foreground] hover:text-[--color-foreground]">
            <Settings2 className="w-3 h-3" />
          </button>
        </button>
      ))}
      <div className="h-px bg-[--color-border] my-1" />
      <button onClick={() => selectTeamMember(agent.id, null)}
        className={cn("flex items-center justify-between w-full px-3 py-2 rounded-md text-sm cursor-pointer hover:bg-[--color-secondary] outline-none", !activeTeamMemberId && "bg-[--color-primary]/10 text-[--color-primary]")}>
        <div className="flex items-center gap-2"><Users className="w-4 h-4" /><span>Team Settings</span></div>
        <button onClick={(e) => { e.stopPropagation(); openConfigDialog("edit", "team", agent.id); }}
          className="w-5 h-5 flex items-center justify-center rounded hover:bg-[--color-muted] text-[--color-muted-foreground] hover:text-[--color-foreground]">
          <Settings2 className="w-3 h-3" />
        </button>
      </button>
    </div>
  );
}
