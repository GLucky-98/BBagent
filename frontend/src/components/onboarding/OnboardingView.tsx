import { Bot } from "lucide-react";
import { useAppStore } from "../../store";
import { OnboardingStep } from "./OnboardingStep";
import type { SettingsTab } from "../../types";

interface Step {
  stepNumber: number;
  title: string;
  description: string;
  completed: boolean;
  inProgress: boolean;
  action: () => void;
  actionLabel: string;
  required: boolean;
}

function useOnboardingSteps(): Step[] {
  const models = useAppStore((s) => s.models);
  const skills = useAppStore((s) => s.skills);
  const mcpServers = useAppStore((s) => s.mcpServers);
  const isSettingsOpen = useAppStore((s) => s.isSettingsOpen);
  const settingsActiveTab = useAppStore((s) => s.settingsActiveTab);
  const openSettings = useAppStore((s) => s.openSettings);
  const openConfigDialog = useAppStore((s) => s.openConfigDialog);

  return [
    {
      stepNumber: 1,
      title: "Configure Models",
      description: "Select AI language models available for your agents",
      completed: models.length > 0,
      inProgress: isSettingsOpen && settingsActiveTab === "models",
      action: () => openSettings("models" as SettingsTab),
      actionLabel: "Configure \u2192",
      required: true,
    },
    {
      stepNumber: 2,
      title: "Configure Skills",
      description: "Add reusable skill packages to extend agent capabilities",
      completed: skills.length > 0,
      inProgress: isSettingsOpen && settingsActiveTab === "skills",
      action: () => openSettings("skills" as SettingsTab),
      actionLabel: "Configure \u2192",
      required: false,
    },
    {
      stepNumber: 3,
      title: "Configure MCP Servers",
      description: "Connect external tools and data sources",
      completed: mcpServers.length > 0,
      inProgress: isSettingsOpen && settingsActiveTab === "mcps",
      action: () => openSettings("mcps" as SettingsTab),
      actionLabel: "Configure \u2192",
      required: false,
    },
    {
      stepNumber: 4,
      title: "Create Your First Agent",
      description: "Set up and launch your first Agent or Agent Team",
      completed: false,
      inProgress: false,
      action: () => openConfigDialog("create", ""),
      actionLabel: "Create \u2192",
      required: true,
    },
  ];
}

export function OnboardingView() {
  const steps = useOnboardingSteps();

  return (
    <div className="flex-1 flex items-center justify-center bg-[--color-muted]/30">
      <div className="w-[520px] bg-white rounded-xl shadow-lg border border-[--color-border] p-8">
        <div className="text-center mb-8">
          <Bot className="w-12 h-12 text-[--color-primary] mx-auto mb-3" />
          <h1 className="text-xl font-semibold text-[--color-foreground]">
            Welcome to BBagent
          </h1>
          <p className="text-sm text-[--color-muted-foreground] mt-1">
            Complete the following steps to get started
          </p>
        </div>

        <div className="space-y-2">
          {steps.map((step) => {
            const status = step.completed
              ? "completed"
              : step.inProgress
                ? "in_progress"
                : "pending";
            return (
              <OnboardingStep
                key={step.stepNumber}
                stepNumber={step.stepNumber}
                title={step.title}
                description={step.description}
                status={status}
                actionLabel={step.actionLabel}
                onAction={step.action}
                required={step.required}
              />
            );
          })}
        </div>

        <p className="text-xs text-[--color-muted-foreground]/60 text-center mt-6">
          Tip: At minimum, you need one Model and one Agent to get started
        </p>
      </div>
    </div>
  );
}
