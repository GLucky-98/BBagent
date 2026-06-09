import { X, Info, AlertTriangle } from "lucide-react";
import { useAppStore } from "../store";

export function ToastContainer() {
  const toasts = useAppStore((s) => s.toasts);
  const dismissToast = useAppStore((s) => s.dismissToast);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[80] flex flex-col gap-2 max-w-[400px]">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-start gap-3 px-4 py-3 rounded-xl bg-(--color-background)/95 backdrop-blur-md shadow-[0_8px_24px_rgba(0,0,0,0.08)] text-[13px] border-l-2 animate-slide-in-from-right ${
            toast.type === "warning"
              ? "border-(--color-warning)"
              : "border-(--color-primary)"
          }`}
        >
          {toast.type === "warning" ? (
            <AlertTriangle size={15} className="shrink-0 mt-0.5 text-(--color-warning)" />
          ) : (
            <Info size={15} className="shrink-0 mt-0.5 text-(--color-primary)" />
          )}
          <span className="flex-1 text-(--color-foreground)">{toast.message}</span>
          <button
            onClick={() => dismissToast(toast.id)}
            className="shrink-0 p-0.5 rounded hover:bg-(--color-secondary)"
          >
            <X size={14} className="text-(--color-ink-3)" />
          </button>
        </div>
      ))}
    </div>
  );
}
