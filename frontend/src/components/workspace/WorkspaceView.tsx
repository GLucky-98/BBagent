import { useRef, useState, useCallback, lazy, Suspense } from "react";
import { Bot } from "lucide-react";
import { useAppStore } from "../../store";
import { isTeam } from "../../types";
import { ChatWindow } from "../ChatWindow";
import { TeamChatWindow } from "../TeamChatWindow";
import { PanelA_FilePanel } from "./PanelA_FilePanel";
import { PanelC_FilePreview } from "./PanelC_FilePreview";
import { SessionManagerPanel } from "./SessionManagerPanel";
import { TeamConversationPanel } from "./TeamConversationPanel";
import { PanelSplitter } from "./Splitter";

const TeamGraphView = lazy(() => import("./TeamGraphView").then(m => ({ default: m.TeamGraphView })));

const PANEL_A_MIN = 200;
const PANEL_A_MAX = 500;
const PANEL_A_DEFAULT = 300;

const PANEL_C_MIN = 220;
const PANEL_C_MAX = 600;
const PANEL_C_DEFAULT = 360;

export function WorkspaceView() {
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const activeTeamMemberName = useAppStore((s) => s.activeTeamMemberName);
  const activeAgent = useAppStore((s) => (
    s.activeAgentId ? s.agents.find((a) => a.id === s.activeAgentId) : undefined
  ));
  const previewFile = useAppStore((s) => s.previewFile);
  const sessionPanelOpen = useAppStore((s) => s.sessionPanelOpen);
  const teamGraphOpen = useAppStore((s) => s.teamGraphOpen);
  const teamConversationPanelOpen = useAppStore((s) => s.teamConversationPanelOpen);
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

  // Show TeamChatWindow only when team tab is active AND no specific member is selected.
  // When a teammate is selected, activeAgentId is the mate's UUID → ChatWindow handles it.
  const showTeamChat = activeAgent?.type === "team" && !activeTeamMemberName;

  // right panel: SessionManagerPanel / TeamConversationPanel / FilePreview / TeamGraphView displayed exclusively
  // when team selected and no member selected, show TeamGraphView based on teamGraphOpen state
  const isTeamTab = !!showTeamChat && isTeam(activeAgent) && activeAgent.members.length > 0;
  const showTeamGraph = isTeamTab && teamGraphOpen;
  const showTeamConversations = isTeamTab && teamConversationPanelOpen;
  const showRightPanel = sessionPanelOpen || showTeamConversations || !!previewFile || showTeamGraph;

  if (!activeAgentId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-(--color-background)">
        <div className="text-center">
          <div className="w-16 h-16 rounded-full bg-(--color-secondary) flex items-center justify-center mx-auto mb-4">
            <Bot className="w-8 h-8 text-(--color-ink-3)" />
          </div>
          <p className="text-[17px] font-semibold text-(--color-foreground)">
            Select an agent to start chatting
          </p>
          <p className="text-[13px] text-(--color-ink-2) mt-1">
            Choose an agent from the tabs above, or create a new one
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 overflow-hidden border-t border-(--color-rule-soft)">
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
      {showRightPanel && (
        <>
          <PanelSplitter
            targetRef={panelCRef}
            defaultWidth={PANEL_C_DEFAULT}
            minWidth={PANEL_C_MIN}
            maxWidth={PANEL_C_MAX}
            reverse
            onWidthChange={handlePanelCChange}
          />
          {sessionPanelOpen ? (
            <SessionManagerPanel width={panelCWidth} />
          ) : showTeamConversations ? (
            <TeamConversationPanel width={panelCWidth} />
          ) : previewFile ? (
            <PanelC_FilePreview ref={panelCRef} width={panelCWidth} />
          ) : showTeamGraph ? (
            <div ref={panelCRef} style={{ width: panelCWidth }} className="h-full border-l border-(--color-rule-soft)">
              <Suspense fallback={null}>
                <TeamGraphView width={panelCWidth} />
              </Suspense>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
