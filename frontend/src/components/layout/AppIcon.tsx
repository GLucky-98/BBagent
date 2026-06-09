import { useAppStore } from "../../store";
import { cn } from "../../lib/utils";

export function AppIcon() {
  const isSettingsOpen = useAppStore((s) => s.isSettingsOpen);
  const openSettings = useAppStore((s) => s.openSettings);
  const closeSettings = useAppStore((s) => s.closeSettings);

  const handleToggle = () => {
    if (isSettingsOpen) {
      closeSettings();
    } else {
      openSettings();
    }
  };

  return (
    <button
      onClick={handleToggle}
      className={cn(
        "flex items-center justify-center w-11 h-11 shrink-0",
        "hover:bg-(--color-secondary) rounded-md transition-colors",
        isSettingsOpen && "bg-(--color-secondary)"
      )}
    >
      <div className="w-[22px] h-[22px] rounded-[5px] bg-(--color-foreground) text-(--color-background) flex items-center justify-center text-[13px] font-semibold">
        B
      </div>
    </button>
  );
}
