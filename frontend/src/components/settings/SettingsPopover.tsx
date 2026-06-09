import { X } from "lucide-react";
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
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 背景层 */}
      <div
        className="absolute inset-0 bg-black/20 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* 居中弹窗 */}
      <div className="relative w-[960px] max-w-[95vw] h-[85vh] max-h-[800px] bg-(--color-background) rounded-xl shadow-2xl flex flex-col overflow-hidden animate-dialog-in">
        <header className="flex items-center justify-between px-5 h-12 border-b border-(--color-rule-soft) shrink-0">
          <h2 className="text-[15px] font-semibold">Settings</h2>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-full hover:bg-(--color-secondary) flex items-center justify-center"
          >
            <X className="w-3.5 h-3.5 text-(--color-ink-2)" />
          </button>
        </header>

        {/* 侧边 tab 列表 + 详情面板 */}
        <div className="flex flex-1 min-h-0">
          <nav className="w-[160px] border-r border-(--color-rule-soft) py-2 shrink-0">
            {SETTINGS_TABS.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => onTabChange(tab.id)}
                  className={cn(
                    "w-full text-left px-5 py-2 text-[13px] transition-colors",
                    isActive
                      ? "text-(--color-foreground) font-semibold bg-(--color-secondary)"
                      : "text-(--color-ink-2) hover:bg-(--color-secondary)/60"
                  )}
                >
                  {tab.label}
                </button>
              );
            })}
          </nav>

          {/* 详情面板：内部模块各自处理 overflow，此处不拦截高度 */}
          <div className="flex-1 min-h-0 overflow-hidden">
            {activeTab === "models" && <ModelsModule />}
            {activeTab === "skills" && <SkillsModule />}
            {activeTab === "mcps" && <MCPsModule />}
            {activeTab === "prompts" && <PromptsModule />}
          </div>
        </div>
      </div>
    </div>
  );
}
