import { X } from "lucide-react";
import { createPortal } from "react-dom";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  secondaryLabel: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onSecondary: () => void;
  onCancel: () => void;
  variant?: "danger" | "default";
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  secondaryLabel,
  cancelLabel = "Cancel",
  onConfirm,
  onSecondary,
  onCancel,
  variant = "default",
}: ConfirmDialogProps) {
  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onCancel} />
      <div className="relative w-[min(92vw,460px)] bg-(--color-background) rounded-2xl shadow-[-8px_8px_24px_rgba(0,0,0,0.08)] overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-(--color-rule-soft)">
          <h2 className="text-[15px] font-semibold">{title}</h2>
          <button onClick={onCancel} className="p-1 rounded-md hover:bg-(--color-secondary) transition-colors">
            <X className="w-4 h-4 text-(--color-ink-2)" />
          </button>
        </div>

        <div className="px-5 py-4">
          <p className="text-[14px] text-(--color-foreground)">{message}</p>
        </div>

        <div className="px-5 py-3 border-t border-(--color-rule-soft) grid grid-cols-3 gap-2">
          <button
            onClick={onCancel}
            className="min-h-10 px-3 py-2 rounded-md border border-(--color-border) text-[13px] leading-tight font-medium hover:bg-(--color-secondary) transition-colors whitespace-normal break-words text-center"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onSecondary}
            className="min-h-10 px-3 py-2 rounded-md border border-(--color-border) text-[13px] leading-tight font-medium hover:bg-(--color-secondary) transition-colors whitespace-normal break-words text-center"
          >
            {secondaryLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`min-h-10 px-3 py-2 rounded-md border text-[13px] leading-tight font-medium text-white transition-all hover:opacity-90 whitespace-normal break-words text-center ${
              variant === "danger"
                ? "border-(--color-danger) bg-(--color-danger)"
                : "border-(--color-primary) bg-(--color-primary)"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
