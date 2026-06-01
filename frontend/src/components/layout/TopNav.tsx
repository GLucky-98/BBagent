import { AppIcon } from "./AppIcon";
import { AgentTabs } from "../agents/AgentTabs";

export function TopNav() {
  return (
    <div className="flex items-center h-12 bg-white border-b border-(--color-border) shrink-0 z-50">
      <AppIcon />
      <div className="flex-1 flex items-center h-full overflow-x-auto">
        <AgentTabs />
      </div>
    </div>
  );
}
