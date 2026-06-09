import { useState, useRef, useEffect, useCallback } from "react";
import { Bot, User, Radio, X, ChevronDown, Check, Sparkles, ArrowUp, Network } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import type { TeamChatMessage, Team } from "../types";
import { isTeam } from "../types";
import { MarkdownContent } from "./MarkdownContent";

const AGENT_COLORS = [
  "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
  "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
];

function TeamMessageBubble({ msg, color }: { msg: TeamChatMessage; color: string }) {
  const isUser = msg.type === "user";
  const isBroadcast = msg.type === "broadcast";

  let label: string;
  if (isUser) {
    label = `${msg.fromAgent} → ${msg.toAgent}`;
  } else if (isBroadcast) {
    label = `${msg.fromAgent} (broadcast)`;
  } else {
    label = `${msg.fromAgent} → ${msg.toAgent}`;
  }

  return (
    <div
      className="px-8 py-5 border-b border-(--color-rule-soft)"
      data-msg-ts={msg.timestamp}
      data-msg-from={msg.fromAgent}
      data-msg-to={msg.toAgent}
    >
      <div className="max-w-[720px] mx-auto flex gap-3">
        <div className="w-[22px] h-[22px] rounded-full flex items-center justify-center text-[10px] font-semibold shrink-0 mt-0.5 text-white"
          style={{ backgroundColor: color }}>
          {isUser ? <User size={11} /> : isBroadcast ? <Radio size={11} /> : <Bot size={11} />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 mb-1.5">
            <span className="text-[12.5px] font-semibold" style={{ color }}>
              {label}
            </span>
            <span className="text-[11px] text-(--color-ink-3) tabular-nums">
              {new Date(msg.timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
          <div className="text-[14.5px] leading-[1.6] tracking-[-0.005em] text-(--color-foreground)">
            <MarkdownContent content={msg.content} />
          </div>
        </div>
      </div>
    </div>
  );
}

export function TeamChatWindow() {
  const agents = useAppStore((s) => s.agents);
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const teamMessages = useAppStore((s) => s.teamMessages);
  const addTeamMessage = useAppStore((s) => s.addTeamMessage);
  const loadTeamMessages = useAppStore((s) => s.loadTeamMessages);
  const toggleTeamGraph = useAppStore((s) => s.toggleTeamGraph);
  const teamScrollTarget = useAppStore((s) => s.teamScrollTarget);
  const clearTeamScrollTarget = useAppStore((s) => s.clearTeamScrollTarget);

  const team = agents.find((a): a is Team => a.id === activeAgentId && isTeam(a));
  const members = team?.members || [];
  const messages = team ? (teamMessages[team.id] || []) : [];

  const [input, setInput] = useState("");
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const agentColorMapRef = useRef<Record<string, string>>({});
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Scroll to target message and highlight it
  useEffect(() => {
    if (!teamScrollTarget) return;
    const selector = `[data-msg-ts="${teamScrollTarget.timestamp}"][data-msg-from="${teamScrollTarget.fromAgent}"][data-msg-to="${teamScrollTarget.toAgent}"]`;
    // Small delay to let the messages render
    const timer = setTimeout(() => {
      const el = document.querySelector(selector);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.add("msg-highlight");
        setTimeout(() => {
          el.classList.remove("msg-highlight");
        }, 3000);
      }
      clearTeamScrollTarget();
    }, 150);
    return () => clearTimeout(timer);
  }, [teamScrollTarget, clearTeamScrollTarget]);

  const getAgentColor = (name: string) => {
    if (!agentColorMapRef.current[name]) {
      const idx = Object.keys(agentColorMapRef.current).length % AGENT_COLORS.length;
      agentColorMapRef.current[name] = AGENT_COLORS[idx];
    }
    return agentColorMapRef.current[name];
  };

  const scrollToBottom = () => { messagesEndRef.current?.scrollIntoView({ behavior: "instant" }); };
  useEffect(() => { scrollToBottom(); }, [messages]);

  // 点击外部关闭下拉
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // 加载历史消息
  useEffect(() => {
    if (team) {
      loadTeamMessages(team.id);
    }
  }, [team?.id]);

  const connectWs = useCallback((teamRef: string) => {
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.close();
    }
    const wsBase = (import.meta.env.VITE_API_BASE || "http://localhost:8000/api").replace(/^http/, "ws");
    const ws = new WebSocket(`${wsBase}/ws/team/${teamRef}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "team_message") {
          addTeamMessage(teamRef, {
            fromAgent: data.from_agent,
            toAgent: data.to_agent,
            content: typeof data.content === "string" ? data.content : JSON.stringify(data.content),
            type: data.msg_type || data.type,
            timestamp: data.timestamp,
          });
        }
      } catch {
        // ignore parse errors
      }
    };
  }, [addTeamMessage]);

  useEffect(() => {
    if (team) {
      connectWs(team.id);
    }
    return () => {
      wsRef.current?.close();
    };
  }, [team?.id, connectWs]);

  const toggleAgent = (name: string) => {
    setSelectedAgents((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );
  };

  const removeAgent = (name: string) => {
    setSelectedAgents((prev) => prev.filter((n) => n !== name));
  };

  const selectAll = () => {
    if (selectedAgents.length === members.length) {
      setSelectedAgents([]);
    } else {
      setSelectedAgents(members.map((m) => m.name));
    }
  };

  const handleSend = () => {
    if (!input.trim() || !team || selectedAgents.length === 0) return;

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: "user_message",
        content: input.trim(),
        mentions: selectedAgents,
      }));
    }
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Ignore Enter during IME composition (e.g. confirming Chinese characters).
    if (e.nativeEvent.isComposing) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!team) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-(--color-background) text-(--color-muted-foreground)">
        <div className="w-16 h-16 rounded-full bg-(--color-secondary) flex items-center justify-center mb-4">
          <Sparkles size={28} className="text-(--color-ink-3)" />
        </div>
        <p className="text-[15px] font-medium text-(--color-foreground)">No team selected</p>
      </div>
    );
  }

  const canSend = input.trim().length > 0 && selectedAgents.length > 0;

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-(--color-background)">
      <header className="px-8 py-4 bg-white/72 backdrop-blur-md border-b border-(--color-rule-soft)">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-(--color-primary) to-blue-500 flex items-center justify-center">
            <Sparkles size={16} className="text-white" />
          </div>
          <div className="flex-1">
            <h2 className="text-[15px] font-semibold text-(--color-foreground) tracking-[-0.01em]">{team.name} · Team Chat</h2>
            <p className="text-[12px] text-(--color-ink-2) mt-0.5">
              {members.length} members: {members.map((m) => m.name).join(", ")}
            </p>
          </div>
          <button
            onClick={toggleTeamGraph}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium
                       bg-(--color-secondary) hover:bg-(--color-secondary-hover)
                       text-(--color-foreground) transition-colors"
            title="Open Team View"
          >
            <Network className="w-4 h-4" />
            TeamView
          </button>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto overflow-x-clip">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-(--color-muted-foreground)">
            <div className="w-16 h-16 rounded-full bg-(--color-secondary) flex items-center justify-center mb-4">
              <Sparkles size={28} className="text-(--color-ink-3)" />
            </div>
            <p className="text-[14.5px]">Team chat is ready</p>
            <p className="text-[12px] text-(--color-ink-3) mt-1">Select agents to send messages to team members</p>
          </div>
        ) : (
          messages.map((msg, i) => (
            <TeamMessageBubble
              key={`${msg.timestamp}-${i}`}
              msg={msg}
              color={getAgentColor(msg.fromAgent)}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="px-8 py-4 border-t border-(--color-rule-soft) bg-(--color-background)">
        <div className="max-w-[720px] mx-auto">
          {/* 已选 agent tags */}
          {selectedAgents.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 mb-2">
              {selectedAgents.map((name) => (
                <span
                  key={name}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium text-white"
                  style={{ backgroundColor: getAgentColor(name) }}
                >
                  {name}
                  <button
                    onClick={() => removeAgent(name)}
                    className="hover:opacity-70 ml-0.5"
                  >
                    <X size={11} />
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="flex items-end gap-2 bg-(--color-tint) border border-(--color-border) rounded-xl p-2.5 transition-all focus-within:bg-white focus-within:border-(--color-primary) focus-within:shadow-[0_0_0_3px_rgba(0,102,204,0.12)]">
            {/* Agent 选择下拉 */}
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setShowDropdown(!showDropdown)}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[12px] transition-colors shrink-0",
                  selectedAgents.length > 0
                    ? "bg-(--color-primary)/10 text-(--color-primary)"
                    : "text-(--color-ink-2) hover:bg-(--color-secondary)"
                )}
              >
                <span className="max-w-[80px] truncate">
                  {selectedAgents.length === 0
                    ? "Select..."
                    : selectedAgents.length === members.length
                      ? `All (${selectedAgents.length})`
                      : `${selectedAgents.length} agent${selectedAgents.length > 1 ? "s" : ""}`}
                </span>
                <ChevronDown size={13} />
              </button>
              {showDropdown && (
                <div className="absolute bottom-full left-0 mb-1 w-52 bg-(--color-popover) rounded-xl shadow-[0_4px_16px_rgba(0,0,0,0.08)] border border-(--color-border) z-50">
                  {/* 全选 */}
                  <button
                    onClick={selectAll}
                    className="w-full text-left px-3 py-2 text-[13px] hover:bg-(--color-secondary) flex items-center gap-2 border-b border-(--color-rule-soft)"
                  >
                    <div className={cn(
                      "w-4 h-4 rounded border flex items-center justify-center shrink-0",
                      selectedAgents.length === members.length
                        ? "bg-(--color-primary) border-(--color-primary)"
                        : "border-(--color-border)"
                    )}>
                      {selectedAgents.length === members.length && <Check size={12} className="text-white" />}
                    </div>
                    All agents
                  </button>
                  {members.map((m) => (
                    <button
                      key={m.name}
                      onClick={() => toggleAgent(m.name)}
                      className="w-full text-left px-3 py-2 text-[13px] hover:bg-(--color-secondary) flex items-center gap-2"
                    >
                      <div className={cn(
                        "w-4 h-4 rounded border flex items-center justify-center shrink-0",
                        selectedAgents.includes(m.name)
                          ? "bg-(--color-primary) border-(--color-primary)"
                          : "border-(--color-border)"
                      )}>
                        {selectedAgents.includes(m.name) && <Check size={12} className="text-white" />}
                      </div>
                      <div className="w-3.5 h-3.5 rounded-full shrink-0" style={{ backgroundColor: getAgentColor(m.name) }} />
                      {m.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {/* 输入框 */}
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; }}
              onDrop={(e) => {
                e.preventDefault();
                const path = e.dataTransfer.getData("text/plain");
                if (path) {
                  setInput((prev) => prev ? prev + " " + path : path);
                }
              }}
              placeholder={selectedAgents.length === 0 ? "Select agents to send..." : "Type your message..."}
              rows={1}
              className="flex-1 bg-transparent border-0 outline-none resize-none text-[14.5px] leading-[1.5] text-(--color-foreground) placeholder:text-(--color-ink-3) px-2 py-1.5"
              style={{ minHeight: "24px", maxHeight: "120px" }}
            />
            <button onClick={handleSend} disabled={!canSend}
              className="w-8 h-8 rounded-full bg-(--color-foreground) hover:bg-black text-white flex items-center justify-center shrink-0 transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
              <ArrowUp size={16} strokeWidth={2.5} />
            </button>
          </div>
        </div>
      </div>
      <style>{`
        .msg-highlight {
          animation: msgHighlightFade 3s ease-out;
        }
        @keyframes msgHighlightFade {
          0% { background-color: #dbeafe; }
          100% { background-color: transparent; }
        }
      `}</style>
    </div>
  );
}
