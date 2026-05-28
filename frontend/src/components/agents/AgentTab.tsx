import { useState, useMemo } from "react";
import { Settings2 } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { cn } from "../../lib/utils";
import { useAppStore } from "../../store";
import { TeamDropdown } from "./TeamDropdown";
import type { Agent } from "../../types";

interface AgentTabProps {
  agent: Agent;
  isActive: boolean;
  onClick: () => void;
  onConfig: () => void;
}

export function AgentTab({ agent, isActive, onClick, onConfig }: AgentTabProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const activeTeamMemberId = useAppStore((s) => s.activeTeamMemberId);
  const isTeam = agent.type === "team";

  const displayName = useMemo(() => {
    if (!isTeam) return agent.name;
    if (agent.id !== activeAgentId || !activeTeamMemberId) return agent.name;
    const member = agent.teamMembers?.find((m) => m.id === activeTeamMemberId);
    return member ? `${agent.name} \u203A ${member.name}` : agent.name;
  }, [agent, isTeam, activeAgentId, activeTeamMemberId]);

  return (
    <DropdownMenu.Root open={isTeam && dropdownOpen} onOpenChange={setDropdownOpen}>
      <div
        className={cn(
          "flex items-center gap-1 px-3 py-1.5 h-full cursor-pointer border-b-2 transition-colors select-none min-w-0 max-w-[200px]",
          !isActive && "bg-transparent text-[--color-muted-foreground] border-transparent hover:bg-[--color-secondary]/50"
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
        {isTeam ? (
          <DropdownMenu.Trigger asChild>
            <span className="text-sm font-medium truncate flex-1">
              {displayName}
            </span>
          </DropdownMenu.Trigger>
        ) : (
          <span className="text-sm font-medium truncate flex-1" onClick={onClick}>
            {displayName}
          </span>
        )}
        {(isHovered || isActive) && (
          <button onClick={(e) => { e.stopPropagation(); onConfig(); }} className="w-5 h-5 flex items-center justify-center rounded hover:bg-[--color-muted] text-[--color-muted-foreground] hover:text-[--color-foreground] shrink-0">
            <Settings2 className="w-3 h-3" />
          </button>
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
  );
}
