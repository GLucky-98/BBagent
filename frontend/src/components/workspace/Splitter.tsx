import { useCallback, useRef } from "react";

interface SplitterProps {
  containerRef: React.RefObject<HTMLDivElement | null>;
  ratio: number;
  onRatioChange: (ratio: number) => void;
  minRatio?: number;
  maxRatio?: number;
}

export function Splitter({
  containerRef,
  ratio,
  onRatioChange,
  minRatio = 0.1,
  maxRatio = 0.9,
}: SplitterProps) {
  const isDragging = useRef(false);

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
      className="h-1 bg-[--color-border] hover:bg-[--color-primary]/50 cursor-row-resize shrink-0 transition-colors relative group"
      onMouseDown={handleMouseDown}
    >
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-1 rounded-full bg-[--color-muted-foreground]/30 group-hover:bg-[--color-primary]/60 transition-colors" />
    </div>
  );
}
