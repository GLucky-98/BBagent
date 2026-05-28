import { Settings2, X } from "lucide-react";
import { cn } from "../../lib/utils";
import { ModelsModule } from "../ModelsModule";
import { SkillsModule } from "../SkillsModule";
import { MCPsModule } from "../MCPsModule";
import { PromptsModule } from "../PromptsModule";
import type { SettingsTab } from "../../types";

interface SettingsPopoverProps {
  activeTab: SettingsTab;
  onTabChange: (tab: SettingsTab) => void;
  onClose: () => void;
}

const SETTINGS_TABS: { id: SettingsTab; label: string }[] = [
  { id: "models", label: "Models" },
  { id: "skills", label: "Skills" },
  { id: "mcps", label: "MCPs" },
  { id: "prompts", label: "Prompts" },
];

const tabActiveStyle: React.CSSProperties = {
  borderBottomColor: "#3b82f6",
  color: "#3b82f6",
  fontWeight: 600,
  backgroundColor: "rgba(59, 130, 246, 0.08)",
};

const tabInactiveStyle: React.CSSProperties = {
  borderBottomColor: "transparent",
};

export function SettingsPopover({
  activeTab,
  onTabChange,
  onClose,
}: SettingsPopoverProps) {
  return (
    <div className="w-[800px] h-[80vh] bg-white rounded-xl shadow-2xl border border-[--color-border] flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[--color-border] shrink-0">
        <div className="flex items-center gap-2">
          <Settings2 className="w-4 h-4 text-[--color-muted-foreground]" />
          <span className="text-sm font-semibold text-[--color-foreground]">
            Settings
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md hover:bg-[--color-secondary] transition-colors"
        >
          <X className="w-4 h-4 text-[--color-muted-foreground]" />
        </button>
      </div>

      <div className="flex border-b border-[--color-border] px-4 shrink-0">
        {SETTINGS_TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={cn(
                "px-4 py-2 text-sm border-b-2 transition-colors rounded-t-md",
                !isActive && "text-[--color-muted-foreground] hover:text-[--color-foreground] hover:bg-[--color-secondary]/50"
              )}
              style={{
                ...(isActive ? tabActiveStyle : tabInactiveStyle),
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <div className="flex-1 min-h-0 p-4">
        {activeTab === "models" && <div className="h-full"><ModelsModule /></div>}
        {activeTab === "skills" && <div className="h-full"><SkillsModule /></div>}
        {activeTab === "mcps" && <div className="h-full"><MCPsModule /></div>}
        {activeTab === "prompts" && <div className="h-full"><PromptsModule /></div>}
      </div>
    </div>
  );
}
