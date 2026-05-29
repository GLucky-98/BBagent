import { X } from "lucide-react";

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

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onCancel} />
      <div className="relative w-[400px] bg-white rounded-xl shadow-2xl border border-[--color-border] overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[--color-border]">
          <h2 className="text-sm font-semibold">{title}</h2>
          <button onClick={onCancel} className="p-1 rounded-md hover:bg-[--color-secondary] transition-colors">
            <X className="w-4 h-4 text-[--color-muted-foreground]" />
          </button>
        </div>

        <div className="px-5 py-4">
          <p className="text-sm text-[--color-foreground]">{message}</p>
        </div>

        <div className="px-5 py-3 border-t border-[--color-border] flex gap-2 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg border border-[--color-border] text-sm hover:bg-[--color-secondary]"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onSecondary}
            className="px-4 py-2 rounded-lg border border-[--color-border] text-sm hover:bg-[--color-secondary]"
          >
            {secondaryLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 rounded-lg border text-sm text-white hover:opacity-90 ${
              variant === "danger"
                ? "border-red-500 bg-red-500"
                : "border-[--color-border] bg-[--color-primary] text-[--color-primary-foreground]"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
