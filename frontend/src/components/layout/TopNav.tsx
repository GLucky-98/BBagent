import { AppIcon } from "./AppIcon";
import { AgentTabs } from "../agents/AgentTabs";

export function TopNav() {
  return (
    <div
      className="flex items-center h-[52px] shrink-0 z-50
                 bg-white/72 backdrop-blur-xl border-b border-(--color-border)"
      style={{ WebkitBackdropFilter: "saturate(180%) blur(20px)" }}
    >
      <AppIcon />
      <div className="flex-1 flex items-center h-full overflow-x-auto">
        <AgentTabs />
      </div>
    </div>
  );
}
