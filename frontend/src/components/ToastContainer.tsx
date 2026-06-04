import { X, Info, AlertTriangle } from "lucide-react";
import { useAppStore } from "../store";

export function ToastContainer() {
  const toasts = useAppStore((s) => s.toasts);
  const dismissToast = useAppStore((s) => s.dismissToast);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[80] flex flex-col gap-2 max-w-[420px]">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg text-sm animate-in slide-in-from-right ${
            toast.type === "warning"
              ? "bg-amber-50 border-amber-200 text-amber-900"
              : "bg-white border-(--color-border) text-(--color-foreground)"
          }`}
        >
          {toast.type === "warning" ? (
            <AlertTriangle size={16} className="shrink-0 mt-0.5 text-amber-500" />
          ) : (
            <Info size={16} className="shrink-0 mt-0.5 text-(--color-primary)" />
          )}
          <span className="flex-1">{toast.message}</span>
          <button
            onClick={() => dismissToast(toast.id)}
            className="shrink-0 p-0.5 rounded hover:bg-black/5"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
