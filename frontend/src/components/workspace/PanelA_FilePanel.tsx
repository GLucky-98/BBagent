import { useState, useRef } from "react";
import { useAppStore } from "../../store";
import { WorkingDirView } from "./WorkingDirView";
import { BasedirTree } from "./BasedirTree";
import { Splitter } from "./Splitter";

export function PanelA_FilePanel() {
  const activeAgentName = useAppStore((s) => s.activeAgentName);
  const [splitRatio, setSplitRatio] = useState(0.4);
  const containerRef = useRef<HTMLDivElement>(null);

  if (!activeAgentName) {
    return (
      <div className="w-[300px] shrink-0 border-r border-[--color-border] bg-white flex items-center justify-center text-sm text-[--color-muted-foreground]">
        Select an agent
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="w-[300px] shrink-0 border-r border-[--color-border] bg-white flex flex-col overflow-hidden"
    >
      <div
        style={{ height: `${splitRatio * 100}%` }}
        className="overflow-hidden"
      >
        <WorkingDirView />
      </div>

      <Splitter
        containerRef={containerRef}
        onRatioChange={setSplitRatio}
      />

      <div
        style={{ height: `${(1 - splitRatio) * 100}%` }}
        className="overflow-hidden"
      >
        <BasedirTree />
      </div>
    </div>
  );
}
