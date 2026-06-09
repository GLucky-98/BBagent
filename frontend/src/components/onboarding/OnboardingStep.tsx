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
  return (
    <div
      className={cn(
        "flex items-center gap-4 px-4 py-3 rounded-lg transition-colors",
        status === "in_progress" && "bg-(--color-primary)/5",
        status !== "in_progress" && "hover:bg-(--color-secondary)/60"
      )}
    >
      {/* 序号圆 */}
      <div
        className={cn(
          "w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-semibold shrink-0",
          status === "completed" && "bg-(--color-success) text-white",
          status === "in_progress" && "bg-(--color-primary) text-white",
          status === "pending" && "bg-(--color-secondary) text-(--color-ink-2)"
        )}
      >
        {status === "completed" ? "\u2713" : stepNumber}
      </div>

      <div className="flex-1 min-w-0">
        <p
          className={cn(
            "text-[13px] font-medium",
            status === "completed" && "text-(--color-ink-3) line-through",
            status === "in_progress" && "text-(--color-foreground)"
          )}
        >
          {title}
          {!required && (
            <span className="text-[11px] text-(--color-ink-3) ml-1">
              (Optional)
            </span>
          )}
        </p>
        <p className="text-[11px] text-(--color-ink-3) mt-0.5">
          {description}
        </p>
      </div>

      <button
        onClick={onAction}
        disabled={status === "completed"}
        className={cn(
          "shrink-0 px-3 h-7 text-[12px] font-medium rounded-md transition-colors",
          status === "completed"
            ? "text-(--color-success) cursor-default"
            : "bg-(--color-primary) text-(--color-primary-foreground) hover:opacity-90"
        )}
      >
        {status === "completed" ? "Done" : actionLabel}
      </button>
    </div>
  );
}
