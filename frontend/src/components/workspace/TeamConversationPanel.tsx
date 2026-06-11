import { useEffect, useMemo, useState } from "react";
import { ArrowRightLeft, Check, Inbox, Loader2, MessageSquare, Trash2, X } from "lucide-react";
import { useAppStore } from "../../store";
import { cn } from "../../lib/utils";
import { isTeam, type TeamConversation } from "../../types";

interface Props {
  width: number;
}

function formatConversationTime(value: number) {
  if (!value) return "";
  return new Date(value * 1000).toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function shortSessionId(sessionId: string) {
  return sessionId ? sessionId.substring(0, 8) : "missing";
}

function ConversationRow({
  conversation,
  disabled,
  onLoad,
  onDelete,
  loading,
  deleting,
}: {
  conversation: TeamConversation;
  disabled: boolean;
  onLoad: () => void;
  onDelete: () => void;
  loading: boolean;
  deleting: boolean;
}) {
  const memberSessions = Object.entries(conversation.memberSessions || {});

  const handleDelete = (event: React.MouseEvent) => {
    event.stopPropagation();
    if (disabled || deleting) return;
    if (!confirm(`Delete conversation "${conversation.name}"?`)) return;
    onDelete();
  };

  return (
    <div
      onClick={() => {
        if (!conversation.active && !disabled && !loading) onLoad();
      }}
      className={cn(
        "group border-b border-(--color-rule-soft) px-3 py-3 transition-colors",
        conversation.active ? "bg-(--color-primary)/5" : "hover:bg-(--color-secondary)/60",
        disabled || conversation.active ? "cursor-default" : "cursor-pointer"
      )}
    >
      <div className="flex items-start gap-2">
        <div className={cn(
          "mt-0.5 w-6 h-6 rounded-md flex items-center justify-center shrink-0",
          conversation.active ? "bg-(--color-primary) text-white" : "bg-(--color-secondary) text-(--color-ink-2)"
        )}>
          {conversation.active ? <Check size={13} /> : <MessageSquare size={13} />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[12.5px] font-semibold text-(--color-foreground) truncate">
              {conversation.name}
            </span>
            {conversation.active && (
              <span className="text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-green-100 text-green-700 shrink-0">
                active
              </span>
            )}
          </div>
          <div className="mt-1 flex items-center gap-2 text-[10.5px] text-(--color-ink-3)">
            <span>{conversation.messageCount || 0} msgs</span>
            <span>{formatConversationTime(conversation.updatedAt)}</span>
          </div>
        </div>
        {!conversation.active && (
          <button
            onClick={(event) => {
              event.stopPropagation();
              if (!disabled && !loading) onLoad();
            }}
            disabled={disabled || loading}
            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-(--color-tint) text-(--color-primary) transition-opacity shrink-0 disabled:opacity-30 disabled:cursor-not-allowed"
            title={disabled ? "Team must be ready" : "Load conversation"}
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <ArrowRightLeft size={12} />}
          </button>
        )}
        <button
          onClick={handleDelete}
          disabled={disabled || deleting}
          className="p-1 rounded text-red-400 hover:bg-red-100 hover:text-red-600 transition-colors shrink-0 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-red-400"
          title={disabled ? "Team must be ready" : "Delete conversation"}
        >
          {deleting ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
        </button>
      </div>
      {memberSessions.length > 0 && (
        <div className="mt-2 ml-8 flex flex-wrap gap-1">
          {memberSessions.map(([memberName, sessionId]) => (
            <span
              key={memberName}
              className="max-w-full inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-(--color-tint) text-[10px] text-(--color-ink-2)"
              title={sessionId}
            >
              <span className="truncate max-w-[90px]">{memberName}</span>
              <span className="font-mono text-(--color-ink-3)">{shortSessionId(sessionId)}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function TeamConversationPanel({ width }: Props) {
  const agents = useAppStore((s) => s.agents);
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const agentStates = useAppStore((s) => s.agentStates);
  const conversationsByTeam = useAppStore((s) => s.teamConversations);
  const loadTeamConversations = useAppStore((s) => s.loadTeamConversations);
  const loadTeamConversation = useAppStore((s) => s.loadTeamConversation);
  const deleteTeamConversation = useAppStore((s) => s.deleteTeamConversation);
  const closeTeamConversationPanel = useAppStore((s) => s.closeTeamConversationPanel);

  const [loadingList, setLoadingList] = useState(false);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const team = agents.find((agent) => agent.id === activeAgentId && isTeam(agent));
  const conversations = useMemo(
    () => (team ? conversationsByTeam[team.id] || [] : []),
    [conversationsByTeam, team]
  );
  const teamState = team ? (agentStates[team.id] || team.state) : "ready";
  const disabled = teamState !== "ready";

  useEffect(() => {
    if (!team) return;
    setLoadingList(true);
    loadTeamConversations(team.id).finally(() => setLoadingList(false));
  }, [team?.id, loadTeamConversations]);

  const handleLoad = async (conversationId: string) => {
    if (!team) return;
    setLoadingId(conversationId);
    try {
      await loadTeamConversation(team.id, conversationId);
    } finally {
      setLoadingId(null);
    }
  };

  const handleDelete = async (conversationId: string) => {
    if (!team) return;
    setDeletingId(conversationId);
    try {
      await deleteTeamConversation(team.id, conversationId);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div
      className="shrink-0 border-l border-(--color-rule-soft) bg-(--color-background) flex flex-col overflow-hidden"
      style={{ width }}
    >
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-(--color-rule-soft) shrink-0">
        <div className="min-w-0">
          <span className="text-[13px] font-semibold text-(--color-foreground)">Team Conversations</span>
          {disabled && (
            <div className="text-[10.5px] text-(--color-ink-3) mt-0.5">
              Locked while team is {teamState}
            </div>
          )}
        </div>
        <button
          onClick={closeTeamConversationPanel}
          className="p-1 rounded hover:bg-(--color-secondary) text-(--color-ink-3) shrink-0"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loadingList ? (
          <div className="flex flex-col items-center justify-center py-12 text-(--color-ink-3)">
            <Loader2 className="w-5 h-5 animate-spin mb-2" />
            <span className="text-[12px]">Loading conversations...</span>
          </div>
        ) : conversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-(--color-ink-3)">
            <Inbox className="w-8 h-8 mb-2 opacity-40" />
            <span className="text-[12px]">No conversations found</span>
          </div>
        ) : (
          conversations.map((conversation) => (
            <ConversationRow
              key={conversation.id}
              conversation={conversation}
              disabled={disabled}
              loading={loadingId === conversation.id}
              deleting={deletingId === conversation.id}
              onLoad={() => handleLoad(conversation.id)}
              onDelete={() => handleDelete(conversation.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}
