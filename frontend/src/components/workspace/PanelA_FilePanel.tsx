import { useState, useRef, forwardRef } from "react";
import { useAppStore } from "../../store";
import { WorkingDirView } from "./WorkingDirView";
import { BasedirTree } from "./BasedirTree";
import { Splitter } from "./Splitter";

interface Props {
  width: number;
}

export const PanelA_FilePanel = forwardRef<HTMLDivElement, Props>(
  ({ width }, ref) => {
    const activeAgentId = useAppStore((s) => s.activeAgentId);
    const [splitRatio, setSplitRatio] = useState(0.4);
    const innerRef = useRef<HTMLDivElement>(null);

    if (!activeAgentId) {
      return (
        <div
          ref={ref}
          className="shrink-0 border-r border-(--color-border) bg-white flex items-center justify-center text-sm text-(--color-muted-foreground)"
          style={{ width }}
        >
          Select an agent
        </div>
      );
    }

    return (
      <div
        ref={ref}
        className="shrink-0 border-r border-(--color-border) bg-white flex flex-col overflow-hidden"
        style={{ width }}
      >
        <div ref={innerRef} className="flex flex-col flex-1 min-h-0">
          <div
            style={{ height: `${splitRatio * 100}%` }}
            className="overflow-hidden"
          >
            <WorkingDirView />
          </div>

          <Splitter
            containerRef={innerRef}
            onRatioChange={setSplitRatio}
          />

          <div
            style={{ height: `${(1 - splitRatio) * 100}%` }}
            className="overflow-hidden"
          >
            <BasedirTree />
          </div>
        </div>
      </div>
    );
  }
);

PanelA_FilePanel.displayName = "PanelA_FilePanel";
