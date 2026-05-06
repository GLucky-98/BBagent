import {
  Bot,
  Box,
  Wrench,
  Sparkles,
  Server,
  FileText,
} from "lucide-react";
import { useAppStore } from "../store";
import type { NavItem } from "../types";
import { cn } from "../lib/utils";

const navItems: { id: NavItem; icon: typeof Bot; label: string }[] = [
  { id: "agents", icon: Bot, label: "Agents" },
  { id: "models", icon: Box, label: "Models" },
  { id: "tools", icon: Wrench, label: "Tools" },
  { id: "skills", icon: Sparkles, label: "Skills" },
  { id: "mcps", icon: Server, label: "MCPs" },
  { id: "prompts", icon: FileText, label: "Prompts" },
];

export function Sidebar() {
  const currentNav = useAppStore((s) => s.currentNav);
  const setCurrentNav = useAppStore((s) => s.setCurrentNav);

  return (
    <aside className="w-[60px] h-screen bg-white border-r border-[--color-border] flex flex-col items-center py-4 gap-2">
      {navItems.map(({ id, icon: Icon, label }) => (
        <button
          key={id}
          onClick={() => setCurrentNav(id)}
          className={cn(
            "w-10 h-10 rounded-lg flex items-center justify-center transition-all duration-200",
            "hover:bg-[--color-secondary] group relative",
            currentNav === id && "bg-[--color-primary] text-[--color-primary-foreground]"
          )}
          title={label}
        >
          <Icon
            size={20}
            className={cn(
              "transition-transform duration-200",
              currentNav === id
                ? "scale-110"
                : "group-hover:scale-110"
            )}
          />
          <span className="absolute left-full ml-2 px-2 py-1 bg-[--color-foreground] text-[--color-background] text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
            {label}
          </span>
        </button>
      ))}
    </aside>
  );
}
