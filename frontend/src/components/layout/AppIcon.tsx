import { useState } from "react";
import { Bot, X } from "lucide-react";
import { SettingsPopover } from "../settings/SettingsPopover";
import { useAppStore } from "../../store";
import { cn } from "../../lib/utils";

export function AppIcon() {
  const isSettingsOpen = useAppStore((s) => s.isSettingsOpen);
  const openSettings = useAppStore((s) => s.openSettings);
  const closeSettings = useAppStore((s) => s.closeSettings);
  const settingsActiveTab = useAppStore((s) => s.settingsActiveTab);
  const [localTab, setLocalTab] = useState(settingsActiveTab);

  const handleToggle = () => {
    if (isSettingsOpen) {
      closeSettings();
    } else {
      setLocalTab(settingsActiveTab);
      openSettings();
    }
  };

  return (
    <>
      <button
        onClick={handleToggle}
        className={cn(
          "flex items-center justify-center w-12 h-12 shrink-0",
          "hover:bg-[--color-secondary] rounded-md transition-colors",
          isSettingsOpen && "bg-[--color-secondary]"
        )}
      >
        <Bot className="w-6 h-6 text-[--color-primary]" />
      </button>

      {isSettingsOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={closeSettings} />
          <div className="relative">
            <SettingsPopover
              activeTab={localTab}
              onTabChange={setLocalTab}
              onClose={closeSettings}
            />
          </div>
        </div>
      )}
    </>
  );
}
