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
      actionLabel: "Configure",
      required: true,
    },
    {
      stepNumber: 2,
      title: "Configure Skills",
      description: "Add reusable skill packages to extend agent capabilities",
      completed: skills.length > 0,
      inProgress: isSettingsOpen && settingsActiveTab === "skills",
      action: () => openSettings("skills" as SettingsTab),
      actionLabel: "Configure",
      required: false,
    },
    {
      stepNumber: 3,
      title: "Configure MCP Servers",
      description: "Connect external tools and data sources",
      completed: mcpServers.length > 0,
      inProgress: isSettingsOpen && settingsActiveTab === "mcps",
      action: () => openSettings("mcps" as SettingsTab),
      actionLabel: "Configure",
      required: false,
    },
    {
      stepNumber: 4,
      title: "Create Your First Agent",
      description: "Set up and launch your first Agent or Agent Team",
      completed: false,
      inProgress: false,
      action: () => openConfigDialog("create", ""),
      actionLabel: "Create",
      required: true,
    },
  ];
}

export function OnboardingView() {
  const steps = useOnboardingSteps();

  const completedCount = steps.filter((s) => s.completed).length;
  const progressPercent = Math.round((completedCount / steps.length) * 100);

  return (
    <div className="flex-1 flex items-center justify-center bg-(--color-secondary)/30 px-8">
      <div className="w-[920px] max-w-[95vw] grid grid-cols-[1fr_1.1fr] gap-12 items-start">
        {/* left column: title + progress */}
        <div className="pt-4">
          <div className="text-[11px] font-semibold tracking-[0.2em] uppercase text-(--color-primary) mb-3">
            Getting Started
          </div>
          <h1 className="text-[40px] font-semibold leading-[1.1] tracking-[-0.025em] text-(--color-foreground)">
            Welcome to <em className="font-display">BBagent</em>.
          </h1>
          <p className="text-[15px] text-(--color-ink-2) mt-3 leading-[1.55]">
            Building Block Agent &mdash; Stack Agents, Compose Teams
          </p>

          {/* progress */}
          <div className="mt-8 space-y-2">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-medium text-(--color-ink-2)">
                Step {completedCount} of {steps.length}
              </span>
              <span className="text-(--color-ink-3) tabular-nums">{progressPercent}%</span>
            </div>
            <div className="h-1 bg-(--color-border) rounded-full overflow-hidden">
              <div
                className="h-full bg-(--color-primary) rounded-full transition-all duration-500"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
        </div>

        {/* right column: step card */}
        <div className="bg-(--color-background) rounded-2xl border border-(--color-rule-soft) p-6 space-y-1">
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
      </div>
    </div>
  );
}
