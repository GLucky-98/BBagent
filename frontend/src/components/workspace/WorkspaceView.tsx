import { useRef, useState, useCallback } from "react";
import { Bot } from "lucide-react";
import { useAppStore } from "../../store";
import { ChatWindow } from "../ChatWindow";
import { TeamChatWindow } from "../TeamChatWindow";
import { PanelA_FilePanel } from "./PanelA_FilePanel";
import { PanelC_FilePreview } from "./PanelC_FilePreview";
import { PanelSplitter } from "./Splitter";

const PANEL_A_MIN = 200;
const PANEL_A_MAX = 500;
const PANEL_A_DEFAULT = 300;

const PANEL_C_MIN = 220;
const PANEL_C_MAX = 600;
const PANEL_C_DEFAULT = 360;

export function WorkspaceView() {
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const activeTeamMemberName = useAppStore((s) => s.activeTeamMemberName);
  const agents = useAppStore((s) => s.agents);
  const previewFile = useAppStore((s) => s.previewFile);
  const [panelAWidth, setPanelAWidth] = useState(PANEL_A_DEFAULT);
  const [panelCWidth, setPanelCWidth] = useState(PANEL_C_DEFAULT);
  const panelARef = useRef<HTMLDivElement>(null);
  const panelCRef = useRef<HTMLDivElement>(null);

  const handlePanelAChange = useCallback((width: number) => {
    setPanelAWidth(width);
  }, []);

  const handlePanelCChange = useCallback((width: number) => {
    setPanelCWidth(width);
  }, []);

  const activeAgent = agents.find((a) => a.id === activeAgentId);
  // Show TeamChatWindow only when team tab is active AND no specific member is selected.
  // When a teammate is selected, activeAgentId is the mate's UUID → ChatWindow handles it.
  const showTeamChat = activeAgent?.type === "team" && !activeTeamMemberName;

  if (!activeAgentId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-(--color-muted)/30">
        <div className="text-center">
          <Bot className="w-16 h-16 text-(--color-muted-foreground)/30 mx-auto mb-4" />
          <p className="text-lg font-medium text-(--color-muted-foreground)">
            Select an agent to start chatting
          </p>
          <p className="text-sm text-(--color-muted-foreground)/60 mt-1">
            Choose an agent from the tabs above, or create a new one
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      <PanelA_FilePanel ref={panelARef} width={panelAWidth} />
      <PanelSplitter
        targetRef={panelARef}
        defaultWidth={PANEL_A_DEFAULT}
        minWidth={PANEL_A_MIN}
        maxWidth={PANEL_A_MAX}
        onWidthChange={handlePanelAChange}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        {showTeamChat ? <TeamChatWindow /> : <ChatWindow />}
      </div>
      {previewFile && (
        <>
          <PanelSplitter
            targetRef={panelCRef}
            defaultWidth={PANEL_C_DEFAULT}
            minWidth={PANEL_C_MIN}
            maxWidth={PANEL_C_MAX}
            reverse
            onWidthChange={handlePanelCChange}
          />
          <PanelC_FilePreview ref={panelCRef} width={panelCWidth} />
        </>
      )}
    </div>
  );
}
