import { Settings2, X } from "lucide-react";
import * as Tabs from "@radix-ui/react-tabs";
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

export function SettingsPopover({
  activeTab,
  onTabChange,
  onClose,
}: SettingsPopoverProps) {
  return (
    <Tabs.Root
      value={activeTab}
      onValueChange={(v) => onTabChange(v as SettingsTab)}
    >
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

        <Tabs.List className="flex border-b border-[--color-border] px-4 shrink-0">
          {SETTINGS_TABS.map((tab) => (
            <Tabs.Trigger
              key={tab.id}
              value={tab.id}
              className={cn(
                "px-4 py-2 text-sm border-b-2 transition-colors",
                "data-[state=active]:border-[--color-primary] data-[state=active]:text-[--color-primary]",
                "data-[state=inactive]:border-transparent data-[state=inactive]:text-[--color-muted-foreground]",
                "hover:text-[--color-foreground]"
              )}
            >
              {tab.label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <div className="flex-1 min-h-0 p-4">
          <Tabs.Content value="models" className="h-full">
            <ModelsModule />
          </Tabs.Content>
          <Tabs.Content value="skills" className="h-full">
            <SkillsModule />
          </Tabs.Content>
          <Tabs.Content value="mcps" className="h-full">
            <MCPsModule />
          </Tabs.Content>
          <Tabs.Content value="prompts" className="h-full">
            <PromptsModule />
          </Tabs.Content>
        </div>
      </div>
    </Tabs.Root>
  );
}
