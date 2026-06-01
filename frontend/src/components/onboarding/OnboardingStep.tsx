import { Circle, Loader2, CheckCircle2 } from "lucide-react";
import { cn } from "../../lib/utils";

interface OnboardingStepProps {
  stepNumber: number;
  title: string;
  description: string;
  status: "pending" | "in_progress" | "completed";
  actionLabel: string;
  onAction: () => void;
  required: boolean;
}

export function OnboardingStep({
  stepNumber,
  title,
  description,
  status,
  actionLabel,
  onAction,
  required,
}: OnboardingStepProps) {
  const icon = {
    pending: <Circle className="w-5 h-5 text-(--color-muted-foreground)/40" />,
    in_progress: (
      <Loader2 className="w-5 h-5 text-(--color-primary) animate-spin" />
    ),
    completed: <CheckCircle2 className="w-5 h-5 text-green-500" />,
  }[status];

  return (
    <div
      className={cn(
        "flex items-center gap-4 px-4 py-3 rounded-lg",
        status === "in_progress" && "bg-(--color-primary)/5",
        status === "completed" && "bg-green-50"
      )}
    >
      <div className="shrink-0">{icon}</div>

      <div className="flex-1 min-w-0">
        <p
          className={cn(
            "text-sm font-medium",
            status === "completed" && "text-green-700 line-through",
            status === "in_progress" && "text-(--color-primary)"
          )}
        >
          {stepNumber}. {title}
          {!required && (
            <span className="text-xs text-(--color-muted-foreground) ml-1">
              (Optional)
            </span>
          )}
        </p>
        <p className="text-xs text-(--color-muted-foreground) mt-0.5">
          {description}
        </p>
      </div>

      <button
        onClick={onAction}
        disabled={status === "completed"}
        className={cn(
          "shrink-0 px-3 py-1.5 text-xs rounded-md transition-colors border border-(--color-border)",
          status === "completed"
            ? "text-green-600 bg-green-100 cursor-default"
            : "bg-(--color-primary) text-(--color-primary-foreground) hover:opacity-90"
        )}
      >
        {status === "completed" ? "Done \u2713" : actionLabel}
      </button>
    </div>
  );
}
