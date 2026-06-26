import { useState, useEffect, useMemo } from "react";
import { X, ChevronDown, ChevronRight, Trash2, GitFork, ArrowRightLeft, Loader2, Inbox } from "lucide-react";
import { useAppStore } from "../../store";
import type { GlobalSessionIndex, TurnInfo } from "../../types";

// ── group by agent_id ──
function groupByAgent(sessions: GlobalSessionIndex[]) {
  const map = new Map<string, { agentId: string; agentName: string; sessions: GlobalSessionIndex[] }>();
  for (const s of sessions) {
    let group = map.get(s.agent_id);
    if (!group) {
      group = { agentId: s.agent_id, agentName: s.agent_name, sessions: [] };
      map.set(s.agent_id, group);
    }
    group.sessions.push(s);
  }
  // within each agent, sort by timestamp descending
  for (const g of map.values()) {
    g.sessions.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  }
  return Array.from(map.values());
}

// ── L3: Turn row ──
function TurnRow({
  turn,
  sessionId,
  currentAgentId,
}: {
  turn: TurnInfo;
  sessionId: string;
  currentAgentId: string | null;
}) {
  const forkSession = useAppStore((s) => s.forkSession);
  const [forking, setForking] = useState(false);

  const handleFork = async () => {
    setForking(true);
    try {
      await forkSession(sessionId, turn.index, currentAgentId || undefined);
    } finally {
      setForking(false);
    }
  };

  const ts = turn.startTimestamp
    ? new Date(turn.startTimestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 hover:bg-(--color-secondary)/60 transition-colors group">
      <span className="text-[11px] text-(--color-ink-3) font-mono w-5 shrink-0">#{turn.index}</span>
      <span className="text-[12px] text-(--color-foreground) truncate flex-1 min-w-0">
        {turn.userMessage}
      </span>
      {ts && <span className="text-[10px] text-(--color-ink-3) shrink-0">{ts}</span>}
      <button
        onClick={handleFork}
        disabled={forking}
        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-(--color-tint) text-(--color-primary) transition-opacity shrink-0"
        title="Fork from this turn"
      >
        {forking ? <Loader2 size={12} className="animate-spin" /> : <GitFork size={12} />}
      </button>
    </div>
  );
}

// ── L2: Session row ──
function SessionRow({
  session,
  currentAgentId,
}: {
  session: GlobalSessionIndex;
  currentAgentId: string | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const sessionDetails = useAppStore((s) => s.sessionDetails);
  const loadSessionDetail = useAppStore((s) => s.loadSessionDetail);
  const deleteGlobalSession = useAppStore((s) => s.deleteGlobalSession);
  const switchSession = useAppStore((s) => s.switchSession);
  const agentState = useAppStore((s) => s.agentStates[session.agent_id]);
  const fallbackAgentState = useAppStore((s) => s.agents.find((agent) => agent.id === session.agent_id)?.state);
  const [deleting, setDeleting] = useState(false);
  const [switching, setSwitching] = useState(false);

  const detail = sessionDetails[session.session_id];
  const sessionActionsDisabled = agentState === "running"
    || fallbackAgentState === "running";

  const handleToggle = async () => {
    if (!expanded && !detail) {
      await loadSessionDetail(session.session_id);
    }
    setExpanded(!expanded);
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (session.is_active) return;
    if (!confirm(`Delete session ${session.session_id.substring(0, 16)}...?`)) return;
    setDeleting(true);
    try {
      await deleteGlobalSession(session.session_id);
    } finally {
      setDeleting(false);
    }
  };

  const handleSwitch = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!session.agent_id || session.is_active || sessionActionsDisabled) return;
    setSwitching(true);
    try {
      await switchSession(session.agent_id, session.session_id);
    } finally {
      setSwitching(false);
    }
  };

  const shortId = session.session_id.substring(0, 19);

  return (
    <div>
      <div
        onClick={handleToggle}
        className="flex items-center gap-1.5 px-3 py-1.5 cursor-pointer hover:bg-(--color-secondary)/60 transition-colors group"
      >
        {expanded ? <ChevronDown size={11} className="text-(--color-ink-3) shrink-0" /> : <ChevronRight size={11} className="text-(--color-ink-3) shrink-0" />}
        <span className="text-[11.5px] font-mono text-(--color-foreground) truncate flex-1 min-w-0">
          {shortId}
        </span>
        {session.is_active && (
          <span className="text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-green-100 text-green-700 shrink-0">active</span>
        )}
        <span className="text-[10px] text-(--color-ink-3) shrink-0">{session.turn_count}t</span>
        {!session.is_active && (
          <button
            onClick={handleSwitch}
            disabled={switching || sessionActionsDisabled}
            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-(--color-tint) text-(--color-primary) transition-opacity shrink-0 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent"
            title={sessionActionsDisabled ? "Cannot switch sessions while agent is running" : "Switch to this session"}
          >
            {switching ? <Loader2 size={11} className="animate-spin" /> : <ArrowRightLeft size={11} />}
          </button>
        )}
        <button
          onClick={handleDelete}
          disabled={deleting || session.is_active}
          className="p-1 rounded text-red-400 hover:bg-red-100 hover:text-red-600 transition-colors shrink-0 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-red-400"
          title={session.is_active ? "Cannot delete active session" : "Delete session"}
        >
          {deleting ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
        </button>
      </div>
      {expanded && (
        <div className="border-l-2 border-(--color-border) ml-5">
          {detail ? (
            detail.turns.length > 0 ? (
              detail.turns.map((turn) => (
                <TurnRow
                  key={turn.index}
                  turn={turn}
                  sessionId={session.session_id}
                  currentAgentId={currentAgentId}
                />
              ))
            ) : (
              <div className="px-3 py-2 text-[11px] text-(--color-ink-3)">No completed turns</div>
            )
          ) : (
            <div className="px-3 py-2 flex items-center gap-1.5 text-[11px] text-(--color-ink-3)">
              <Loader2 size={10} className="animate-spin" /> Loading...
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── L1: Agent group ──
function AgentGroup({
  agentName,
  sessions,
  currentAgentId,
  defaultExpanded,
}: {
  agentId: string;
  agentName: string;
  sessions: GlobalSessionIndex[];
  currentAgentId: string | null;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(!!defaultExpanded);

  return (
    <div>
      <div
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 px-3 py-2 cursor-pointer hover:bg-(--color-secondary)/60 transition-colors"
      >
        {expanded ? <ChevronDown size={12} className="text-(--color-ink-3) shrink-0" /> : <ChevronRight size={12} className="text-(--color-ink-3) shrink-0" />}
        <span className="text-[12.5px] font-semibold text-(--color-foreground) truncate">{agentName}</span>
        <span className="text-[10px] text-(--color-ink-3) shrink-0 ml-auto">{sessions.length}</span>
      </div>
      {expanded && (
        <div>
          {sessions.map((s) => (
            <SessionRow key={s.session_id} session={s} currentAgentId={currentAgentId} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── main panel ──
interface Props {
  width: number;
}

export function SessionManagerPanel({ width }: Props) {
  const globalSessions = useAppStore((s) => s.globalSessions);
  const loadGlobalSessions = useAppStore((s) => s.loadGlobalSessions);
  const toggleSessionPanel = useAppStore((s) => s.toggleSessionPanel);
  const activeAgentId = useAppStore((s) => s.activeAgentId);

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (globalSessions.length === 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Panel mount triggers an external session refresh with local loading state.
      setLoading(true);
      loadGlobalSessions().finally(() => setLoading(false));
    }
  }, [globalSessions.length, loadGlobalSessions]);

  const groups = useMemo(() => groupByAgent(globalSessions), [globalSessions]);

  return (
    <div
      className="shrink-0 border-l border-(--color-rule-soft) bg-(--color-background) flex flex-col overflow-hidden"
      style={{ width }}
    >
      {/* title bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-(--color-rule-soft) shrink-0">
        <span className="text-[13px] font-semibold text-(--color-foreground)">Sessions</span>
        <button
          onClick={toggleSessionPanel}
          className="p-1 rounded hover:bg-(--color-secondary) text-(--color-ink-3) shrink-0"
        >
          <X size={14} />
        </button>
      </div>

      {/* content area */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-12 text-(--color-ink-3)">
            <Loader2 className="w-5 h-5 animate-spin mb-2" />
            <span className="text-[12px]">Loading sessions...</span>
          </div>
        ) : groups.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-(--color-ink-3)">
            <Inbox className="w-8 h-8 mb-2 opacity-40" />
            <span className="text-[12px]">No sessions found</span>
          </div>
        ) : (
          groups.map((g) => (
            <AgentGroup
              key={g.agentId}
              agentId={g.agentId}
              agentName={g.agentName}
              sessions={g.sessions}
              currentAgentId={activeAgentId}
              defaultExpanded={g.agentId === activeAgentId}
            />
          ))
        )}
      </div>
    </div>
  );
}
