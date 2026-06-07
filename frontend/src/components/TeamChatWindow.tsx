import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Bot, User, Radio, X, ChevronDown, Check } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import type { TeamChatMessage, Team } from "../types";
import { isTeam } from "../types";

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
    <div className="flex gap-3 mb-4">
      <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0" style={{ backgroundColor: isUser ? "var(--color-primary)" : color }}>
        {isUser ? <User size={14} className="text-white" /> : isBroadcast ? <Radio size={14} className="text-white" /> : <Bot size={14} className="text-white" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-medium" style={{ color }}>
            {label}
          </span>
          <span className="text-[10px] text-(--color-muted-foreground)">
            {new Date(msg.timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        </div>
        <div className="rounded-2xl rounded-tl-sm px-4 py-2.5 bg-(--color-secondary) inline-block max-w-[85%]">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
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

  const getAgentColor = (name: string) => {
    if (!agentColorMapRef.current[name]) {
      const idx = Object.keys(agentColorMapRef.current).length % AGENT_COLORS.length;
      agentColorMapRef.current[name] = AGENT_COLORS[idx];
    }
    return agentColorMapRef.current[name];
  };

  const scrollToBottom = () => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); };
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
      <div className="flex-1 flex items-center justify-center bg-(--color-background) text-(--color-muted-foreground)">
        <p>No team selected</p>
      </div>
    );
  }

  const canSend = input.trim().length > 0 && selectedAgents.length > 0;

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-(--color-background)">
      <header className="px-6 py-4 bg-white border-b border-(--color-border)">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-(--color-primary)/10 flex items-center justify-center">
            <Bot size={20} className="text-(--color-primary)" />
          </div>
          <div>
            <h2 className="font-semibold text-(--color-foreground)">{team.name} - Team Chat</h2>
            <p className="text-xs text-(--color-muted-foreground)">
              {members.length} members: {members.map((m) => m.name).join(", ")}
            </p>
          </div>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-(--color-muted-foreground)">
            <div className="w-16 h-16 rounded-full bg-(--color-secondary) flex items-center justify-center mb-4"><Bot size={28} /></div>
            <p className="text-sm">Team chat is ready</p>
            <p className="text-xs mt-1">Select agents to send messages to team members</p>
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
      <div className="p-4 bg-white border-t border-(--color-border)">
        {/* 已选 agent tags */}
        {selectedAgents.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 mb-2">
            {selectedAgents.map((name) => (
              <span
                key={name}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium text-white"
                style={{ backgroundColor: getAgentColor(name) }}
              >
                {name}
                <button
                  onClick={() => removeAgent(name)}
                  className="hover:opacity-70 ml-0.5"
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="flex items-end gap-2">
          {/* Agent 选择下拉 */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setShowDropdown(!showDropdown)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-3 rounded-xl border border-(--color-border)",
                "bg-(--color-background) text-sm hover:bg-(--color-secondary) transition-colors shrink-0",
                selectedAgents.length > 0 ? "text-(--color-foreground)" : "text-(--color-muted-foreground)"
              )}
            >
              <span className="max-w-[80px] truncate">
                {selectedAgents.length === 0
                  ? "Select..."
                  : selectedAgents.length === members.length
                    ? `All (${selectedAgents.length})`
                    : `${selectedAgents.length} agent${selectedAgents.length > 1 ? "s" : ""}`}
              </span>
              <ChevronDown size={14} />
            </button>
            {showDropdown && (
              <div className="absolute bottom-full left-0 mb-1 w-52 bg-white rounded-lg shadow-lg border border-(--color-border) z-50">
                {/* 全选 */}
                <button
                  onClick={selectAll}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-(--color-secondary) flex items-center gap-2 border-b border-(--color-border)"
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
                    className="w-full text-left px-3 py-2 text-sm hover:bg-(--color-secondary) flex items-center gap-2"
                  >
                    <div className={cn(
                      "w-4 h-4 rounded border flex items-center justify-center shrink-0",
                      selectedAgents.includes(m.name)
                        ? "bg-(--color-primary) border-(--color-primary)"
                        : "border-(--color-border)"
                    )}>
                      {selectedAgents.includes(m.name) && <Check size={12} className="text-white" />}
                    </div>
                    <div className="w-4 h-4 rounded-full shrink-0" style={{ backgroundColor: getAgentColor(m.name) }} />
                    {m.name}
                  </button>
                ))}
              </div>
            )}
          </div>
          {/* 输入框 */}
          <div className="flex-1">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={selectedAgents.length === 0 ? "Select agents to send message..." : "Type your message..."}
              rows={1}
              className={cn("w-full px-4 py-3 rounded-xl border border-(--color-border)", "bg-(--color-background) resize-none", "focus:outline-none focus:ring-2 focus:ring-(--color-ring) focus:border-transparent", "placeholder:text-(--color-muted-foreground)")}
              style={{ minHeight: "48px", maxHeight: "120px" }}
            />
          </div>
          <button onClick={handleSend} disabled={!canSend}
            className={cn("w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border border-(--color-border)", "bg-(--color-primary) text-(--color-primary-foreground)", "transition-all duration-200", "hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed")}>
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
