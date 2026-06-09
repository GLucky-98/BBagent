import { useCallback, useRef, useEffect } from "react";

// ── Vertical splitter (top/bottom) for inside Panel A ──

interface SplitterProps {
  containerRef: React.RefObject<HTMLDivElement | null>;
  ratio: number;
  onRatioChange: (ratio: number) => void;
  minRatio?: number;
  maxRatio?: number;
}

export function Splitter({
  containerRef,
  onRatioChange,
  minRatio = 0.1,
  maxRatio = 0.9,
}: Omit<SplitterProps, 'ratio'>) {
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const container = containerRef.current;
      if (!container) return;

      const containerHeight = container.getBoundingClientRect().height;

      const handleMouseMove = (e: MouseEvent) => {
        const rect = container.getBoundingClientRect();
        const offsetY = e.clientY - rect.top;
        const newRatio = Math.max(
          minRatio,
          Math.min(maxRatio, offsetY / containerHeight)
        );
        onRatioChange(newRatio);
      };

      const handleMouseUp = () => {
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
      };

      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    },
    [containerRef, onRatioChange, minRatio, maxRatio]
  );

  return (
    <div
      className="group h-px bg-(--color-rule-soft) hover:bg-(--color-primary)/40 cursor-row-resize shrink-0 transition-colors relative py-1.5 -my-1.5"
      onMouseDown={handleMouseDown}
    >
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-1 rounded-full bg-(--color-ink-4)/40 group-hover:bg-(--color-primary)/50 transition-colors opacity-0 group-hover:opacity-100" />
    </div>
  );
}

// ── Horizontal splitter (left/right) for between panels ──

interface PanelSplitterProps {
  targetRef: React.RefObject<HTMLDivElement | null>;
  defaultWidth: number;
  minWidth: number;
  maxWidth: number;
  reverse?: boolean;
  onWidthChange: (width: number) => void;
}

export function PanelSplitter({
  targetRef,
  defaultWidth,
  minWidth,
  maxWidth,
  reverse = false,
  onWidthChange,
}: PanelSplitterProps) {
  const currentWidthRef = useRef(defaultWidth);

  useEffect(() => {
    currentWidthRef.current = defaultWidth;
  }, [defaultWidth]);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const target = targetRef.current;
      if (!target) return;

      const startX = e.clientX;
      const startWidth = target.getBoundingClientRect().width;
      const direction = reverse ? -1 : 1;

      const onMove = (clientX: number) => {
        const delta = (clientX - startX) * direction;
        const newWidth = Math.max(minWidth, Math.min(maxWidth, startWidth + delta));
        currentWidthRef.current = newWidth;
        target.style.width = `${newWidth}px`;
      };

      let rafId = 0;
      const handleMouseMove = (e: MouseEvent) => {
        if (rafId) return;
        rafId = requestAnimationFrame(() => {
          rafId = 0;
          onMove(e.clientX);
        });
      };

      const handleMouseUp = () => {
        if (rafId) cancelAnimationFrame(rafId);
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
        document.body.classList.remove("select-none", "cursor-col-resize");
        onWidthChange(currentWidthRef.current);
      };

      document.body.classList.add("select-none", "cursor-col-resize");
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    },
    [targetRef, minWidth, maxWidth, reverse, onWidthChange]
  );

  return (
    <div
      className="w-[3px] -mx-px hover:bg-(--color-primary)/30 cursor-col-resize shrink-0 transition-colors relative group"
      onMouseDown={handleMouseDown}
    >
      <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-px bg-(--color-rule-soft)" />
    </div>
  );
}
