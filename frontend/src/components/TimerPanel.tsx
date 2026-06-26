import { useState } from "react";
import { Play, Square, Pencil, Trash2, Plus, Check, X } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import type { TimerConfig } from "../types";

interface TimerPanelProps {
  agentId: string;
}

function formatSeconds(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return s > 0 ? `${m}m ${s}s` : `${m}m`;
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function formatTrigger(timer: TimerConfig): string {
  if (timer.type === "at" && timer.time) {
    return timer.time;
  }
  return formatSeconds(timer.seconds);
}

interface EditingRow {
  name: string;
  type: "interval" | "at";
  seconds: string;
  time: string;
  hint: string;
}

export function TimerPanel({ agentId }: TimerPanelProps) {
  const timers = useAppStore((s) => s.agentTimers[agentId]) || [];
  const addTimer = useAppStore((s) => s.addTimer);
  const updateTimer = useAppStore((s) => s.updateTimer);
  const startTimer = useAppStore((s) => s.startTimer);
  const stopTimer = useAppStore((s) => s.stopTimer);
  const deleteTimer = useAppStore((s) => s.deleteTimer);

  const [editingName, setEditingName] = useState<string | null>(null);
  const [editingRow, setEditingRow] = useState<EditingRow>({ name: "", type: "interval", seconds: "", time: "", hint: "" });
  const [isAdding, setIsAdding] = useState(false);
  const [addRow, setAddRow] = useState<EditingRow>({ name: "", type: "interval", seconds: "", time: "", hint: "" });

  const handleStartEdit = (timer: TimerConfig) => {
    setEditingName(timer.name);
    setEditingRow({
      name: timer.name,
      type: timer.type || "interval",
      seconds: String(timer.seconds || ""),
      time: timer.time || "",
      hint: timer.hint,
    });
  };

  const handleSaveEdit = async () => {
    if (!editingName) return;
    const originalName = editingName;
    const data: { seconds?: number; time?: string; hint?: string } = { hint: editingRow.hint };

    if (editingRow.type === "at") {
      if (!editingRow.time) return;
      data.time = editingRow.time;
    } else {
      const seconds = parseFloat(editingRow.seconds);
      if (isNaN(seconds) || seconds <= 0) return;
      data.seconds = seconds;
    }

    setEditingName(null);
    await updateTimer(agentId, originalName, data);
  };

  const handleCancelEdit = () => {
    setEditingName(null);
  };

  const isDuplicateName = isAdding && addRow.name.trim() !== "" && timers.some((t) => t.name === addRow.name.trim());

  const handleAdd = async () => {
    if (isDuplicateName) return;

    const data: { name: string; type: "interval" | "at"; seconds?: number; time?: string; hint: string; enabled: boolean } = {
      name: addRow.name || "",
      type: addRow.type,
      hint: addRow.hint || "",
      enabled: true,
    };

    if (addRow.type === "at") {
      if (!addRow.time) return;
      data.time = addRow.time;
    } else {
      const seconds = parseFloat(addRow.seconds);
      if (isNaN(seconds) || seconds <= 0) return;
      data.seconds = seconds;
    }

    await addTimer(agentId, data);
    setAddRow({ name: "", type: "interval", seconds: "", time: "", hint: "" });
    setIsAdding(false);
  };

  const handleCancelAdd = () => {
    setIsAdding(false);
    setAddRow({ name: "", type: "interval", seconds: "", time: "", hint: "" });
  };

  const handleToggleRunning = async (timer: TimerConfig) => {
    if (timer.running) {
      await stopTimer(agentId, timer.name);
    } else {
      await startTimer(agentId, timer.name);
    }
  };

  const handleDelete = async (name: string) => {
    await deleteTimer(agentId, name);
  };

  const renderTriggerCell = (row: EditingRow, setRow: (r: EditingRow) => void) => {
    return (
      <>
        <div className="flex items-center gap-1 mb-1">
          <button
            type="button"
            onClick={() => setRow({ ...row, type: "interval" })}
            className={cn(
              "px-1.5 py-0.5 text-[10px] rounded font-medium transition-colors",
              row.type === "interval"
                ? "bg-(--color-primary) text-white"
                : "bg-(--color-secondary) text-(--color-muted-foreground) hover:bg-(--color-secondary)/80"
            )}
          >
            Interval
          </button>
          <button
            type="button"
            onClick={() => setRow({ ...row, type: "at" })}
            className={cn(
              "px-1.5 py-0.5 text-[10px] rounded font-medium transition-colors",
              row.type === "at"
                ? "bg-(--color-primary) text-white"
                : "bg-(--color-secondary) text-(--color-muted-foreground) hover:bg-(--color-secondary)/80"
            )}
          >
            At Time
          </button>
        </div>
        {row.type === "at" ? (
          <input
            value={row.time}
            onChange={(e) => setRow({ ...row, time: e.target.value })}
            className="w-24 px-2 py-1 rounded border border-(--color-border) bg-white text-xs"
            type="time"
            step="1"
            placeholder="08:00"
          />
        ) : (
          <input
            value={row.seconds}
            onChange={(e) => setRow({ ...row, seconds: e.target.value })}
            className="w-20 px-2 py-1 rounded border border-(--color-border) bg-white text-xs"
            type="number"
            min="1"
            placeholder="seconds"
          />
        )}
      </>
    );
  };

  return (
    <div className="border-t border-(--color-rule-soft) bg-(--color-background)">
      <div className="max-h-64 overflow-y-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left text-(--color-ink-2) border-b border-(--color-rule-soft)">
              <th className="px-3 py-2 text-[11px] font-medium">Name</th>
              <th className="px-3 py-2 text-[11px] font-medium">Trigger</th>
              <th className="px-3 py-2 text-[11px] font-medium">Hint</th>
              <th className="px-3 py-2 text-[11px] font-medium">Status</th>
              <th className="px-3 py-2 text-[11px] font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {timers.map((timer) => (
              editingName === timer.name ? (
                <tr key={timer.name} className="border-b border-(--color-rule-soft) bg-(--color-secondary)/30">
                  <td className="px-3 py-1.5">
                    <input
                      value={editingRow.name}
                      readOnly
                      className="w-full px-2 py-1 rounded border border-(--color-border) bg-gray-50 text-xs text-(--color-muted-foreground) cursor-not-allowed"
                      placeholder="name"
                    />
                  </td>
                  <td className="px-3 py-1.5">
                    {renderTriggerCell(editingRow, setEditingRow)}
                  </td>
                  <td className="px-3 py-1.5">
                    <input
                      value={editingRow.hint}
                      onChange={(e) => setEditingRow((r) => ({ ...r, hint: e.target.value }))}
                      className="w-full px-2 py-1 rounded border border-(--color-border) bg-white text-xs"
                      placeholder="hint"
                    />
                  </td>
                  <td className="px-3 py-1.5">—</td>
                  <td className="px-3 py-1.5 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={handleSaveEdit} className="p-1 rounded hover:bg-green-100 text-green-600" title="Save">
                        <Check size={14} />
                      </button>
                      <button onClick={handleCancelEdit} className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground)" title="Cancel">
                        <X size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                <tr key={timer.name} className="border-b border-(--color-rule-soft) hover:bg-(--color-secondary)/30 transition-colors">
                  <td className="px-3 py-2 font-medium text-(--color-foreground)">{timer.name || "(unnamed)"}</td>
                  <td className="px-3 py-2 text-(--color-muted-foreground) font-mono">
                    <span className="inline-flex items-center gap-1">
                      <span className="text-[10px] px-1 py-0.5 rounded bg-(--color-secondary) text-(--color-ink-3)">
                        {timer.type === "at" ? "AT" : "INT"}
                      </span>
                      {formatTrigger(timer)}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-(--color-muted-foreground) max-w-[200px] truncate">{timer.hint || "—"}</td>
                  <td className="px-3 py-2">
                    <span className={cn(
                      "inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium",
                      timer.running
                        ? "bg-(--color-success)/10 text-(--color-success)"
                        : timer.enabled
                          ? "bg-(--color-warning)/10 text-(--color-warning)"
                          : "bg-(--color-secondary) text-(--color-ink-3)"
                    )}>
                      <span className={cn(
                        "w-1.5 h-1.5 rounded-full",
                        timer.running ? "bg-(--color-success)" : timer.enabled ? "bg-(--color-warning)" : "bg-(--color-ink-4)"
                      )} />
                      {timer.running ? "Running" : timer.enabled ? "Stopped" : "Disabled"}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => handleToggleRunning(timer)}
                        className={cn(
                          "p-1 rounded transition-colors",
                          timer.running
                            ? "hover:bg-red-100 text-red-500"
                            : "hover:bg-green-100 text-green-500"
                        )}
                        title={timer.running ? "Stop" : "Start"}
                      >
                        {timer.running ? <Square size={14} /> : <Play size={14} />}
                      </button>
                      <button
                        onClick={() => handleStartEdit(timer)}
                        className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground) transition-colors"
                        title="Edit"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        onClick={() => handleDelete(timer.name)}
                        className="p-1 rounded hover:bg-red-100 text-red-400 transition-colors"
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            ))}

            {isAdding && (
              <tr className="border-b border-(--color-rule-soft) bg-(--color-primary)/5">
                <td className="px-3 py-1.5">
                  <div>
                    <input
                      value={addRow.name}
                      onChange={(e) => setAddRow((r) => ({ ...r, name: e.target.value }))}
                      className={cn(
                        "w-full px-2 py-1 rounded border bg-white text-xs",
                        isDuplicateName
                          ? "border-red-400 focus:outline-red-400"
                          : "border-(--color-border)"
                      )}
                      placeholder="name (auto-generated if empty)"
                      autoFocus
                    />
                    {isDuplicateName && (
                      <span className="text-[10px] text-red-500 mt-0.5 block">Name already exists</span>
                    )}
                  </div>
                </td>
                <td className="px-3 py-1.5">
                  {renderTriggerCell(addRow, setAddRow)}
                </td>
                <td className="px-3 py-1.5">
                  <input
                    value={addRow.hint}
                    onChange={(e) => setAddRow((r) => ({ ...r, hint: e.target.value }))}
                    className="w-full px-2 py-1 rounded border border-(--color-border) bg-white text-xs"
                    placeholder="hint (optional)"
                  />
                </td>
                <td className="px-3 py-1.5">—</td>
                <td className="px-3 py-1.5 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={handleAdd}
                      disabled={isDuplicateName}
                      className={cn(
                        "p-1 rounded transition-colors",
                        isDuplicateName
                          ? "text-gray-300 cursor-not-allowed"
                          : "hover:bg-green-100 text-green-600"
                      )}
                      title="Save"
                    >
                      <Check size={14} />
                    </button>
                    <button onClick={handleCancelAdd} className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground)" title="Cancel">
                      <X size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            )}

            {timers.length === 0 && !isAdding && (
              <tr>
                <td colSpan={5} className="px-3 py-4 text-center text-(--color-muted-foreground)">
                  No timers configured
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-end px-3 py-2 border-t border-(--color-rule-soft)">
        <button
          onClick={() => setIsAdding(true)}
          className="flex items-center gap-1 px-2 py-1 text-xs text-(--color-primary) hover:bg-(--color-primary)/10 rounded transition-colors"
        >
          <Plus size={12} />
          Add Timer
        </button>
      </div>
    </div>
  );
}
